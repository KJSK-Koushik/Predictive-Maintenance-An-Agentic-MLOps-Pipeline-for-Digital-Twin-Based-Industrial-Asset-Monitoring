# syntax=docker/dockerfile:1.7
ARG AIRFLOW_BASE_IMAGE=apache/airflow:3.3.0-python3.11@sha256:7c7eda27057370576b845ced1269ec539e50588fb43ad0d3d9d20eff5f629fb6
FROM ${AIRFLOW_BASE_IMAGE}

ARG AIRFLOW_VERSION=3.3.0

COPY --chown=airflow:root orchestration/airflow/requirements.txt /opt/phase3/requirements.txt
RUN pip install --no-cache-dir "apache-airflow==${AIRFLOW_VERSION}" \
    -r /opt/phase3/requirements.txt

COPY --chown=airflow:root pyproject.toml README.md /opt/phase3/project/
COPY --chown=airflow:root src /opt/phase3/project/src
RUN pip install --no-cache-dir --no-deps /opt/phase3/project
