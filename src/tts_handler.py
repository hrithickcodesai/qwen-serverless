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
SAMPLING_PARAMS = ("temperature", "top_k", "top_p", "repetition_penalty", "max_new_tokens")

# low values that keep latency down without audibly hurting quality
SAMPLING_DEFAULTS = {"temperature": 0.7, "top_k": 50, "top_p": 0.95}


def load_model():
    global model
    logger.info("loading tts model {}", MODEL_ID)
    # bf16 + sdpa (fused attention) for ampere tensor cores; cuda graphs come
    # free via torch.compile-style paths in generate(), flashboot handles cold boots
    model = Qwen3TTSModel.from_pretrained(
        MODEL_ID,
        dtype=torch.bfloat16,
        device_map="cuda:0",
        attn_implementation="sdpa",
    )
    # cuDNN autotune: run a tiny synthesis so the first real job doesn't pay
    # kernel-selection cost (shaves seconds off the first request)
    try:
        model.generate_voice_design(text="warmup.", instruct="", language="English")
        logger.info("warmup synthesis done")
    except Exception:  # noqa: BLE001 - warmup must never block startup
        logger.warning("warmup synthesis failed, continuing")
    logger.info("tts model loaded")


def wav_bytes(pcm, sample_rate):
    buffer = io.BytesIO()
    sf.write(buffer, pcm, sample_rate, format="WAV")
    return buffer.getvalue()


def handler(job):
    job_input = job.get("input") or {}
    text = job_input.get("text")
    if not text:
        return {"error": "input must include 'text'"}

    instruct = job_input.get("instruct") or ""
    language = job_input.get("language") or "Auto"
    sampling = {**SAMPLING_DEFAULTS, **{k: job_input[k] for k in SAMPLING_PARAMS if k in job_input}}

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


load_model()
