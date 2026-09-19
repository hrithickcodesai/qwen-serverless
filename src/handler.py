import base64
import os
import urllib.request

import runpod
import torch
from loguru import logger
from qwen_asr import Qwen3ASRModel

MODEL_ID = os.environ.get("MODEL_ID", "/app/models/Qwen3-ASR-1.7B")
DATA_URI_PREFIX = "data:audio"

model = None


def load_model():
    global model
    logger.info("loading model {}", MODEL_ID)
    model = Qwen3ASRModel.from_pretrained(
        MODEL_ID,
        dtype=torch.bfloat16,
        device_map="cuda:0",
        max_inference_batch_size=8,
        max_new_tokens=512,
    )
    logger.info("model loaded")


def download_audio(url, path):
    req = urllib.request.Request(url, headers={"User-Agent": "runpod-asr-worker"})
    with urllib.request.urlopen(req, timeout=120) as resp, open(path, "wb") as fh:
        fh.write(resp.read())


def resolve_audio(audio):
    if isinstance(audio, str) and audio.startswith(("http://", "https://")):
        path = "/tmp/input_audio"
        download_audio(audio, path)
        return path
    if isinstance(audio, str):
        if audio.startswith(DATA_URI_PREFIX):
            audio = audio.split(",", 1)[1]
        return base64.b64decode(audio)
    raise ValueError("'audio' must be an http(s) url or base64 string")


def handler(job):
    job_input = job.get("input") or {}
    audio = job_input.get("audio")
    if not audio:
        return {"error": "input must include 'audio': an http(s) url or base64 string"}

    language = job_input.get("language")
    try:
        audio_input = resolve_audio(audio)
        result = model.transcribe(audio=audio_input, language=language)[0]
        return {"text": result.text, "language": result.language}
    except Exception:  # noqa: BLE001 - serverless caller needs an error payload, not a stack trace
        logger.exception("transcription failed")
        return {"error": "transcription failed, check worker logs"}


load_model()
runpod.serverless.start({"handler": handler})
