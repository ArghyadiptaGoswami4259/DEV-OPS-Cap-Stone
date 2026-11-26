# syntax=docker/dockerfile:1.7
FROM python:3.12-slim-bookworm AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
WORKDIR /build
COPY requirements.txt ./
RUN pip install --require-hashes=false -r requirements.txt

FROM python:3.12-slim-bookworm AS runtime

ARG VERSION=dev
ARG GIT_SHA=unknown
ARG CREATED
LABEL org.opencontainers.image.title="TaskFlow" \
      org.opencontainers.image.description="Reference application for the DevOps automation capstone" \
      org.opencontainers.image.source="https://github.com/ArghyadiptaGoswami4259/DEV-OPS-Cap-Stone" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.revision="${GIT_SHA}" \
      org.opencontainers.image.created="${CREATED}" \
      org.opencontainers.image.licenses="MIT"

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_VERSION="${VERSION}" \
    APP_GIT_SHA="${GIT_SHA}" \
    HOST=0.0.0.0 \
    FORWARDED_ALLOW_IPS=127.0.0.1 \
    PORT=8080

RUN groupadd --gid 10001 app && useradd --uid 10001 --gid app --no-create-home --shell /usr/sbin/nologin app
COPY --from=builder /opt/venv /opt/venv
WORKDIR /app
COPY --chown=10001:10001 app ./app
COPY --chown=10001:10001 migrations ./migrations
COPY --chown=10001:10001 alembic.ini ./alembic.ini
USER 10001:10001
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/healthz', timeout=2).read()"]
ENTRYPOINT ["python", "-m", "app"]
