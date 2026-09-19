FROM python:3.12-slim

# SERVICE selects the dependency extra and worker module:
#   --build-arg SERVICE=stt  -> speech to text (qwen-asr)
#   --build-arg SERVICE=tts  -> voice design text to speech (qwen-tts)
ARG SERVICE=stt

ENV PYTHONUNBUFFERED=1 \
    HF_HOME=/app/hf \
    UV_PYTHON_DOWNLOADS=never \
    UV_PYTHON=/usr/local/bin/python \
    WORKER=${SERVICE}

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg git build-essential sox \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

# deps come from pyproject.toml extras, pinned in uv.lock; cache lives in the
# layer (same fs -> hardlinks) and is cleaned so it never ships in the image
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project --extra ${SERVICE} \
    && uv cache clean

ARG MODEL_DIR
COPY models/${MODEL_DIR}/ ./models/${MODEL_DIR}/

ENV HF_HUB_OFFLINE=1 \
    PATH="/app/.venv/bin:$PATH"

COPY src/ ./src/

CMD ["python", "-u", "src/worker.py"]
