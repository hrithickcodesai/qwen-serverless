FROM python:3.12-slim

# SERVICE selects which requirements/worker this image carries:
#   --build-arg SERVICE=stt  -> speech to text (qwen-asr)
#   --build-arg SERVICE=tts  -> voice design text to speech (qwen-tts)
ARG SERVICE=stt

ENV PYTHONUNBUFFERED=1 \
    HF_HOME=/app/hf \
    PIP_NO_CACHE_DIR=1 \
    WORKER=${SERVICE}

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg git build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements-${SERVICE}.txt .
RUN pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu128 \
    && pip install -r requirements-${SERVICE}.txt

ARG MODEL_DIR
COPY models/${MODEL_DIR}/ ./models/${MODEL_DIR}/

ENV HF_HUB_OFFLINE=1

COPY src/ ./src/

CMD ["python", "-u", "src/worker.py"]
