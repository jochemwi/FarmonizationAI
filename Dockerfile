FROM python:3.14-slim

WORKDIR /app

COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip pip install -r requirements.txt
ENV HF_HOME=/opt/hf-cache
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('avsolatorio/GIST-all-MiniLM-L6-v2')"
ENV HF_HUB_OFFLINE=1

COPY . .

ENV PYTHONPATH=/app

CMD ["python", "src/main.py"]