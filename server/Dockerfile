FROM python:3.13-slim

ARG PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app
COPY sdk/python /app/sdk/python
COPY server /app/server
COPY tests /app/tests

RUN python -m pip install --no-cache-dir --index-url "${PIP_INDEX_URL}" /app/sdk/python \
    && python -m pip install --no-cache-dir --index-url "${PIP_INDEX_URL}" /app/server

RUN useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app
USER appuser

WORKDIR /app/server
EXPOSE 8080
# The container port is intentionally fixed. deployment/compose.yaml may publish
# it on another host port (for example 8081), but BFF_PORT from a host .env must
# never move Uvicorn away from the container's healthcheck/target port 8080.
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn lingxi_bff.main:app --host ${BFF_HOST:-0.0.0.0} --port 8080"]
