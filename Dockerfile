FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=7860 \
    INDEX_DIR=/data/index \
    UPLOADS_DIR=/data/uploads

RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 1000 docintel \
    && mkdir -p /data && chown docintel:docintel /data

WORKDIR /app
COPY docintel-rag-gemini/ui/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu 'torch==2.8.0' \
    && pip install --no-cache-dir -r /tmp/requirements.txt

COPY docintel-rag-gemini/backend/app docintel-rag-gemini/backend/app
COPY docintel-rag-gemini/ui/streamlit_app.py docintel-rag-gemini/ui/streamlit_app.py
COPY deploy/serve.py deploy/serve.py

USER docintel
EXPOSE 7860
HEALTHCHECK --interval=30s --timeout=8s --start-period=45s \
    CMD ["python", "deploy/serve.py", "--healthcheck"]
CMD ["python", "deploy/serve.py"]
