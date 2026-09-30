FROM python:3.11-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 \
    APP_ENV=production APP_DATA_DIR=/var/data/ip-sakti HF_HOME=/opt/models \
    ANONYMIZED_TELEMETRY=False TOKENIZERS_PARALLELISM=false OMP_NUM_THREADS=1
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends gosu libgomp1 libpango-1.0-0 libpangoft2-1.0-0 fonts-noto-core && rm -rf /var/lib/apt/lists/* \
    && groupadd -g 10001 app && useradd -u 10001 -g app -m app
COPY requirements.txt requirements.txt
RUN pip install --upgrade pip==26.2.1 setuptools==84.0.0 && pip install --index-url https://download.pytorch.org/whl/cpu torch==2.14.0 && pip install -r requirements.txt && pip check
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2', trust_remote_code=False)"
COPY app.py config.py ./
COPY embeddings/ embeddings/
COPY ingestion/ ingestion/
COPY loaders/ loaders/
COPY rag/ rag/
COPY security/ security/
COPY ui/ ui/
COPY utils/ utils/
COPY vectordb/ vectordb/
COPY deployment/ deployment/
COPY .streamlit/config.toml .streamlit/config.toml
COPY deploy_assets/ deploy_assets/
RUN mkdir -p dataset/source_registry && cp deploy_assets/curated.json dataset/source_registry/curated.json \
    && chmod -R a+rX /opt/models /app && chmod +x /app/deployment/entrypoint.sh
EXPOSE 8501
HEALTHCHECK --interval=30s --timeout=5s --start-period=120s CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:'+os.getenv('PORT','8501')+'/_stcore/health',timeout=4)"
ENTRYPOINT ["/bin/sh", "/app/deployment/entrypoint.sh"]
