FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app
COPY sdk/python /app/sdk/python
COPY bootstrap /app/bootstrap

RUN python -m pip install --no-cache-dir /app/sdk/python \
    && python -m pip install --no-cache-dir /app/bootstrap

CMD ["python", "-m", "bootstrap.cli"]
