FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /workspace

COPY backend/requirements.txt /tmp/biotech-requirements.txt
RUN python -m pip install --requirement /tmp/biotech-requirements.txt

ENTRYPOINT ["python", "-B", "/workspace/tools/local_db/cli.py"]
