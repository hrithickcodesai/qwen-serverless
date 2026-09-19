FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    HF_HOME=/app/hf \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY models/ ./models/

ENV HF_HUB_OFFLINE=1

COPY src/handler.py ./src/handler.py

CMD ["python", "-u", "src/handler.py"]
