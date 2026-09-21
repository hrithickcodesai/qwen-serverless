"""all deploy config in one place, read by the makefile, deploy script and handlers.

secrets (RUNPOD_API_KEY, endpoint ids) live in .env, loaded into env vars.
everything else lives here. run `python config.py` to see the effective values.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict

MODEL_DIRS = {
    "stt": "Qwen3-ASR-0.6B",
    "tts": "Qwen3-TTS-12Hz-1.7B-VoiceDesign",
    "llm": "Qwen3.5-9B",
}

# model repo ids on huggingface
HF_REPO_IDS = {
    "stt": "Qwen/Qwen3-ASR-0.6B",
    "tts": "Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign",
    "llm": "Qwen/Qwen3.5-9B",
}

# forced aligner loaded alongside the stt model (word-level timestamps)
HF_ALIGNER_ID = "Qwen/Qwen3-ForcedAligner-0.6B"

# docker image repos on ghcr (avoids docker hub pull stalls); one image per
# service because qwen-asr, qwen-tts and vllm pin different exact versions of
# transformers. weights are not baked in - workers download from huggingface
# on boot (see Dockerfile)
GHCR_ORG = "hrithickcodesai"
IMAGE_REPOS = {
    "stt": f"ghcr.io/{GHCR_ORG}/qwen3-asr-0.6b-runpod:fast",
    "tts": f"ghcr.io/{GHCR_ORG}/qwen3-tts-voicedesign-runpod:fast",
    "llm": f"ghcr.io/{GHCR_ORG}/qwen3.5-9b-runpod:fast",
}

ENDPOINT_NAMES = {
    "stt": "qwen3-asr-0.6b",
    "tts": "qwen3-tts-voicedesign",
    "llm": "qwen3.5-9b",
}

# runpod gpu pool ids
GPU_POOLS = {
    "stt": "AMPERE_16",  # rtx a4000 16gb, plenty for the 0.6b asr + aligner
    "tts": "ADA_24",  # rtx 4090 24gb, ~1.5x a5000 decode bandwidth, cheaper
    "llm": "BLACKWELL_32",  # rtx 5090 32gb, ~1.8 tb/s fits the 9b with kv headroom
}

# container disk in gb; model weights + torch wheels need the room
DISK_GB = {
    "stt": 25,
    "tts": 25,
    "llm": 50,
}


class DeploySettings(BaseSettings):
    """shared endpoint scaling + performance settings."""

    model_config = SettingsConfigDict(env_prefix="", env_file=".env", extra="ignore")

    # workers scale 0..max; with workers_min=0 nothing runs while idle.
    # idle_timeout keeps a busy worker alive 2 min after its last job, so
    # bursts within that window skip the cold start (image pull + model load)
    workers_min: int = 0
    workers_max: int = 2

    # seconds a worker stays up after its last job
    idle_timeout: int = 120

    # flashboot: runpod's faster cold-boot path for serverless workers
    flashboot: bool = True

    # scaler: runpod adds a worker when queue delay exceeds scaler_value seconds
    scaler_type: str = "QUEUE_DELAY"
    scaler_value: int = 4

    # gpu count per worker (all services run on a single gpu)
    gpu_count: int = 1


# runpod caps summed workers_max across endpoints (quota = 5); llm gets the
# remaining slot since it's the heaviest and rarest workload
WORKERS_MAX = {
    "stt": 2,
    "tts": 2,
    "llm": 1,
}

# ---------------------------------------------------------------------------
# streaming experiment variants (branch: streaming)
#
# separate image tags (:stream) and endpoint names (-stream) so the live
# endpoints above keep pulling :latest and are never touched by this branch.
# gpu pool + disk inherit from the base service; workers stay at 1 to fit
# inside the same 5-worker quota.
# ---------------------------------------------------------------------------

STREAM_SERVICES = ("llm", "stt")

STREAM_IMAGE_REPOS = {
    "llm": IMAGE_REPOS["llm"],
    "stt": IMAGE_REPOS["stt"],
}

STREAM_ENDPOINT_NAMES = {
    "llm": "qwen3.5-9b-stream",
    "stt": "qwen3-asr-0.6b-stream",
}

WORKERS_MAX_STREAM = {
    "llm": 1,
    "stt": 1,
}


settings = DeploySettings()


def _main():
    for name in ("stt", "tts", "llm"):
        print(
            f"{name}: image={IMAGE_REPOS[name]} endpoint={ENDPOINT_NAMES[name]} "
            f"gpu={GPU_POOLS[name]} disk={DISK_GB[name]}gb"
        )
    print(
        f"scaling: min={settings.workers_min} max={settings.workers_max} "
        f"idle_timeout={settings.idle_timeout}s flashboot={settings.flashboot} "
        f"scaler={settings.scaler_type}:{settings.scaler_value}s"
    )


if __name__ == "__main__":
    _main()
