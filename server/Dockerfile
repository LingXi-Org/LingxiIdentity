FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app
COPY sdk/python /app/sdk/python
COPY server /app/server
COPY tests /app/tests

RUN python -m pip install --no-cache-dir /app/sdk/python \
    && python -m pip install --no-cache-dir /app/server

RUN useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app
USER appuser

WORKDIR /app/server
EXPOSE 8080
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn lingxi_bff.main:app --host ${BFF_HOST:-0.0.0.0} --port ${BFF_PORT:-8080}"]
