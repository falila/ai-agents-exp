FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN pip install --upgrade pip setuptools wheel \
    && pip install \
        agno>=1.0.0 \
        openai>=1.30.0 \
        ollama>=0.2.0 \
        pandas>=2.2.0 \
        ddgs>=8.0.0 \
        duckduckgo-search>=6.0.0 \
        pillow>=10.3.0 \
        pydantic>=2.7.0 \
    && pip uninstall -y streamlit || true \
    && pip install --no-cache-dir --force-reinstall streamlit==1.37.1

COPY app.py ./

EXPOSE 8501

CMD ["python", "-m", "streamlit", "run", "app.py", "--server.address=0.0.0.0", "--server.port=8501"]