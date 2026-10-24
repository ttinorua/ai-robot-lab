# Staging candidate only. Build does NOT download or redistribute robot assets.
FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends git libgl1 libglib2.0-0 && rm -rf /var/lib/apt/lists/*
WORKDIR /opt/tduck
COPY tools/t-duck-cloud/requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY tools/t-duck-bridge/bridge.py tools/t-duck-bridge/integration-lock.json bridge/
COPY tools/t-duck-cloud/start.py start.py
RUN useradd --create-home --uid 10001 duck && mkdir /sources && chown duck /sources
USER duck
ENV OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PORT=10000
CMD ["python", "start.py"]
