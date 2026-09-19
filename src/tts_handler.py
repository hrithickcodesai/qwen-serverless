import base64
import io
import os

import soundfile as sf
import torch
from loguru import logger
from qwen_tts import Qwen3TTSModel

MODEL_ID = os.environ.get("TTS_MODEL_ID", "/app/models/Qwen3-TTS-12Hz-1.7B-VoiceDesign")

model = None

# optional generate() knobs exposed to the caller
SAMPLING_PARAMS = (
    "temperature",
    "top_k",
    "top_p",
    "repetition_penalty",
    "max_new_tokens",
)


def load_model():
    global model
    logger.info("loading tts model {}", MODEL_ID)
    model = Qwen3TTSModel.from_pretrained(
        MODEL_ID,
        dtype=torch.bfloat16,
        device_map="cuda:0",
        attn_implementation="sdpa",
    )
    logger.info("tts model loaded")


def wav_bytes(pcm, sample_rate):
    buffer = io.BytesIO()
    sf.write(buffer, pcm, sample_rate, format="WAV")
    return buffer.getvalue()


load_model()


def handler(job):
    job_input = job.get("input") or {}
    text = job_input.get("text")
    if not text:
        return {"error": "input must include 'text'"}

    instruct = job_input.get("instruct") or ""
    language = job_input.get("language") or "Auto"
    sampling = {k: job_input[k] for k in SAMPLING_PARAMS if k in job_input}

    try:
        wavs, sample_rate = model.generate_voice_design(
            text=text,
            instruct=instruct,
            language=language,
            **sampling,
        )
        audio = wav_bytes(wavs[0], sample_rate)
        return {
            "audio": base64.b64encode(audio).decode(),
            "content_type": "audio/wav",
            "sample_rate": sample_rate,
            "duration_seconds": round(len(wavs[0]) / sample_rate, 2),
        }
    except Exception as exc:  # noqa: BLE001 - serverless caller needs an error payload
        logger.exception("synthesis failed")
        return {"error": f"{type(exc).__name__}: {exc}"}
