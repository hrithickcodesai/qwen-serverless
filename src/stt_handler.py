import base64
import os
import pathlib
import urllib.parse
import urllib.request

from loguru import logger
from qwen_asr import Qwen3ASRModel
from qwen_asr.inference.utils import normalize_audio_input

MODEL_ID = os.environ.get("STT_MODEL_ID", "Qwen/Qwen3-ASR-1.7B")
DATA_URI_PREFIX = "data:audio"

# 2s decode cadence: balance between partial freshness and the o(n) re-encode
# of accumulated audio the streaming decoder does per chunk
CHUNK_SIZE_SEC = 2.0

model = None


def load_model():
    global model
    logger.info("loading model {} (vllm backend)", MODEL_ID)
    # vllm backend: paged kv cache + flash attention on ampere. prefix caching
    # reuses the identical text prompt prefix across streaming chunks, so each
    # incremental decode only pays for the newly added audio tokens.
    # 0.90 gpu util leaves headroom for activation spikes without oom.
    model = Qwen3ASRModel.LLM(
        MODEL_ID,
        max_new_tokens=512,
        gpu_memory_utilization=0.90,
        enable_prefix_caching=True,
    )
    logger.info("model loaded")


def download_audio(url, path):
    req = urllib.request.Request(url, headers={"User-Agent": "runpod-asr-worker"})
    with urllib.request.urlopen(req, timeout=120) as resp, open(path, "wb") as fh:
        fh.write(resp.read())


def resolve_audio(audio):
    if isinstance(audio, str) and audio.startswith(("http://", "https://")):
        suffix = pathlib.Path(urllib.parse.urlparse(audio).path).suffix or ".wav"
        path = "/tmp/input_audio" + suffix
        download_audio(audio, path)
        return path
    if isinstance(audio, str):
        if audio.startswith(DATA_URI_PREFIX):
            audio = audio.split(",", 1)[1]
        # qwen_asr's base64 sniffing fails when the string contains '/', so
        # decode to a file ourselves instead of passing the string through
        raw = base64.b64decode(audio, validate=False)
        path = "/tmp/input_audio_b64.wav"
        with open(path, "wb") as fh:
            fh.write(raw)
        return path
    raise ValueError("'audio' must be an http(s) url or base64 string")


def handler(job):
    """plain handler: one-shot transcription, dict result (production contract)."""
    job_input = job.get("input") or {}
    audio = job_input.get("audio")
    if not audio:
        return {"error": "input must include 'audio': an http(s) url or base64 string"}

    language = job_input.get("language")
    try:
        path = resolve_audio(audio)
        result = model.transcribe(audio=path, language=language)[0]
        return {"text": result.text, "language": result.language}
    except Exception as exc:  # noqa: BLE001 - serverless caller needs an error payload
        logger.exception("transcription failed")
        return {"error": f"{type(exc).__name__}: {exc}"}


def handler_stream(job):
    """generator handler: rolling partial transcript of a complete recording.

    feeds 16k mono pcm through the library's streaming decoder (re-decodes
    accumulated audio every chunk with prefix rollback), yielding the updated
    partial text after each chunk; final yield is the settled transcript.
    """
    job_input = job.get("input") or {}
    audio = job_input.get("audio")
    if not audio:
        yield {"error": "input must include 'audio': an http(s) url or base64 string"}
        return

    language = job_input.get("language")
    try:
        path = resolve_audio(audio)
        pcm = normalize_audio_input(path)
        logger.info("streaming decode: {:.1f}s of audio", len(pcm) / 16000)

        state = model.init_streaming_state(language=language, chunk_size_sec=CHUNK_SIZE_SEC)
        step = state.chunk_size_samples
        for start in range(0, len(pcm), step):
            state = model.streaming_transcribe(pcm[start : start + step], state)
            yield {"partial": state.text}
        state = model.finish_streaming_transcribe(state)
        logger.info("streaming decode done: {} chars", len(state.text))
        yield {"text": state.text, "language": state.language}
    except Exception as exc:  # noqa: BLE001 - serverless caller needs an error payload
        logger.exception("transcription failed")
        yield {"error": f"{type(exc).__name__}: {exc}"}


load_model()
