# syntax=docker/dockerfile:1.7
ARG AIRFLOW_BASE_IMAGE=apache/airflow:slim-3.3.2-python3.11@sha256:63acdf77e25af684857e819fff0855b274cc58097cc7a1026e4d41151ddcefa8
FROM ${AIRFLOW_BASE_IMAGE}

ARG AIRFLOW_VERSION=3.3.2

COPY --chown=airflow:root orchestration/airflow/requirements.txt /opt/phase3/requirements.txt
RUN pip install --no-cache-dir "apache-airflow==${AIRFLOW_VERSION}" \
    -r /opt/phase3/requirements.txt

COPY --chown=airflow:root src /opt/phase3/project/src
ENV PYTHONPATH=/opt/phase3/project/src
