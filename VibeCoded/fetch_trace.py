"""Fetch one Langfuse trace (all its observations) and save it as a JSON list.

The output has the same shape as a Langfuse "events export", so the report
scripts can read either one.

Keys come from the environment (the same names the Langfuse SDK uses):
    LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_HOST

Examples:
    python fetch_trace.py --latest -o run.json
    python fetch_trace.py --trace-id 7ae9478a64708857abd5d08e2e9d6d28 -o run.json
"""
import argparse
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

FIELDS = "core,basic,usage,io,metadata,time"


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")


class Api:
    def __init__(self, host, public_key, secret_key):
        self.base = host.rstrip("/") + "/api/public"
        token = base64.b64encode(f"{public_key}:{secret_key}".encode()).decode()
        self.headers = {"Authorization": "Basic " + token, "Accept": "application/json"}

    def get(self, path, params):
        query = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
        req = urllib.request.Request(f"{self.base}{path}?{query}", headers=self.headers)
        for attempt in range(6):
            try:
                with urllib.request.urlopen(req, timeout=120) as resp:
                    return json.load(resp)
            except urllib.error.HTTPError as err:
                if err.code != 429 or attempt == 5:
                    raise
                try:
                    wait = json.loads(err.read())["details"]["retryAfterSeconds"]
                except (ValueError, KeyError, TypeError):
                    wait = err.headers.get("Retry-After") or 30
                wait = float(wait) + 1
                print(f"rate limited, waiting {wait:.0f} s", file=sys.stderr)
                time.sleep(wait)


def v2_pages(api, params):
    """Yield rows from GET /v2/observations, following the cursor."""
    cursor = None
    while True:
        page = api.get("/v2/observations", {**params, "cursor": cursor})
        yield from page.get("data", [])
        cursor = (page.get("meta") or {}).get("cursor")
        if not cursor:
            return


def v1_pages(api, params):
    """Fallback for self-hosted Langfuse v3: GET /observations with page numbers."""
    page_no = 1
    while True:
        page = api.get("/observations", {"traceId": params["traceId"], "limit": 100, "page": page_no})
        yield from page.get("data", [])
        if page_no >= (page.get("meta") or {}).get("totalPages", 1):
            return
        page_no += 1


def latest_trace_id(api, name, since):
    rows = list(v2_pages(api, {"name": name, "fromStartTime": iso(since), "fields": "core,basic", "limit": 5}))
    rows = [r for r in rows if r.get("traceId")]
    if not rows:
        raise SystemExit(f"No observation named '{name}' since {iso(since)}. Try --days or --name.")
    rows.sort(key=lambda r: r["startTime"], reverse=True)
    return rows[0]["traceId"]


def normalize(row):
    """Make API rows look like export rows (v1 calls the cost calculatedTotalCost)."""
    if "totalCost" not in row:
        row["totalCost"] = row.get("calculatedTotalCost") or 0
    return row


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--trace-id", help="Trace to fetch")
    ap.add_argument("--latest", action="store_true", help="Fetch the newest trace (by root observation name)")
    ap.add_argument("--name", default="harmonization-run", help="Root observation name used by --latest")
    ap.add_argument("--days", type=int, default=30, help="How far back to look (default 30)")
    ap.add_argument("-o", "--out", default="run.json")
    args = ap.parse_args()
    if bool(args.trace_id) == bool(args.latest):
        ap.error("give exactly one of --trace-id or --latest")

    host = os.getenv("LANGFUSE_HOST") or os.getenv("LANGFUSE_BASE_URL") or "https://cloud.langfuse.com"
    pk, sk = os.getenv("LANGFUSE_PUBLIC_KEY"), os.getenv("LANGFUSE_SECRET_KEY")
    if not pk or not sk:
        raise SystemExit("Set LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY in your environment.")
    api = Api(host, pk, sk)
    since = datetime.now(timezone.utc) - timedelta(days=args.days)

    try:
        trace_id = args.trace_id or latest_trace_id(api, args.name, since)
        params = {"traceId": trace_id, "fromStartTime": iso(since), "fields": FIELDS, "limit": 1000}
        rows = list(v2_pages(api, params))
    except urllib.error.HTTPError as err:
        if err.code != 404:
            raise SystemExit(f"Langfuse answered {err.code} {err.reason}: {err.read()[:300]!r}")
        print("v2 endpoint not found, falling back to the v1 endpoint", file=sys.stderr)
        trace_id = args.trace_id
        if not trace_id:
            raise SystemExit("--latest needs the v2 endpoint; pass --trace-id instead.")
        rows = list(v1_pages(api, {"traceId": trace_id}))

    rows = [normalize(r) for r in rows]
    rows.sort(key=lambda r: r["startTime"])
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False)

    kinds = {}
    for r in rows:
        kinds[r["type"]] = kinds.get(r["type"], 0) + 1
    print(f"trace {trace_id}: {len(rows)} observations {kinds}")
    if rows:
        print(f"from {rows[0]['startTime']} to {max(r.get('endTime') or r['startTime'] for r in rows)}")
    print(f"saved {args.out}")


if __name__ == "__main__":
    main()
