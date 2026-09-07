FROM python:3.11.14-slim-bookworm@sha256:65a93d69fa75478d554f4ad27c85c1e69fa184956261b4301ebaf6dbb0a3543d

ARG RELEASE_ID

LABEL org.opencontainers.image.title="FD001 research inference"
LABEL org.opencontainers.image.description="Loopback-only Phase 6 staging image"
LABEL org.opencontainers.image.release-id="${RELEASE_ID}"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/opt/app/src \
    APP_ENV=staging \
    PM_RELEASE_DIR=/opt/release \
    PM_RELEASE_ID=${RELEASE_ID}

RUN groupadd --system --gid 10001 inference \
    && useradd --system --uid 10001 --gid inference --home-dir /nonexistent inference

WORKDIR /opt/app
COPY deployment/inference/runtime-requirements.txt /tmp/runtime-requirements.txt
RUN python -m pip install --disable-pip-version-check --no-cache-dir \
        -r /tmp/runtime-requirements.txt \
    && rm /tmp/runtime-requirements.txt

COPY --chown=10001:10001 src/ /opt/app/src/
COPY --chown=10001:10001 artifacts/inference-release/ /opt/release/

USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=5s --timeout=3s --start-period=10s --retries=12 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/ready', timeout=2).read()"]

CMD ["python", "-m", "uvicorn", "predictive_maintenance.serving.app:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
