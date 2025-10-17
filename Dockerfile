# ---- Étape 1 : récupérer l'exécutable Ollama
FROM ollama/ollama:0.12.3 AS ollama

# ---- Étape 2 : image finale Python
FROM python:3.10-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      curl git procps iproute2 netcat-openbsd && \
    rm -rf /var/lib/apt/lists/*

COPY --from=ollama /bin/ollama /bin/ollama

WORKDIR /app
COPY . /app

RUN mkdir -p /app/chroma
COPY Research /app/Research

ENV OLLAMA_HOST=http://ollama:11434
ENV PYTHONUNBUFFERED=1

RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir \
      streamlit \
      langchain \
      langchain_community \
      langchain_core \
      langchain_ollama \
      chromadb \
      pypdf \
      sentence-transformers \
      google-generativeai \
      mysql-connector-python

# Donner les droits d'exécution au script
RUN chmod +x /app/entrypoint.sh

EXPOSE 8501 11434

# Démarrage : attend la BD, crée les tables, puis lance Streamlit
CMD ["bash", "/app/entrypoint.sh"]
