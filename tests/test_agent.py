import pytest
import json

def test_bash_runs_command_and_returns_output():
    from src.tools.tools import bash

    result = bash.invoke({"command": "echo hello", "description": "print hello"})

    assert "hello" in result


def test_bash_returns_error_on_bad_command():
    from src.tools.tools import bash

    result = bash.invoke({"command": "cat nonexistent_file.txt", "description": "read missing file"})

    assert "exit code" in result


def test_bash_truncates_large_output():
    from src.tools.tools import bash

    # generate output larger than MAX_OUTPUT (4000 chars)
    result = bash.invoke({"command": "python3 -c \"print('a' * 10000)\"", "description": "generate large output"})

    assert "truncated" in result
    assert len(result) < 10000

@pytest.mark.slow
def test_bash_timeout():
    from src.tools.tools import bash

    result = bash.invoke({"command": "sleep 120", "description": "sleep forever"})

    assert "timed out" in result

def test_log_question_appends_entries(tmp_path, monkeypatch):
    from src.tools.tools import log_question

    f = tmp_path / "questions.json"
    monkeypatch.setenv("QUESTIONS_FILE", str(f))
    monkeypatch.setenv("RUN_ID", "run123")

    args = {"question": "Is SLLB in cm?", "context": "SYN09 / Soil / SLLB", "assumed_answer": "cm, convert to m"}
    first = log_question.invoke(args)
    log_question.invoke({**args, "question": "Second question"})

    entries = json.loads(f.read_text())
    assert [e["id"] for e in entries] == ["q001", "q002"]
    assert entries[0]["run_id"] == "run123"
    assert entries[0]["assumed_answer"] == "cm, convert to m"
    assert "No answer will come" in first