FROM python:3.11-alpine AS builder
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
WORKDIR /app
RUN apk add --no-cache gcc musl-dev libffi-dev openssl-dev cargo \
    && python3 -m pip install --no-cache-dir uv
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --no-install-project --no-dev

FROM python:3.11-alpine
WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY src /app/src
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH="/app/src"
# Expose both dashboard user spaces and machine communication lines
EXPOSE 8501 8502 8000

CMD ["streamlit", "run", "src/merchant_app.py", "--server.port=8501", "--server.address=0.0.0.0"]
