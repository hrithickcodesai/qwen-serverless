"""all deploy config in one place, read by the makefile, deploy script and handlers.

secrets (RUNPOD_API_KEY, endpoint ids) live in .env, loaded into env vars.
everything else lives here. run `python config.py` to see the effective values.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict

MODEL_DIRS = {
    "stt": "Qwen3-ASR-1.7B",
    "tts": "Qwen3-TTS-12Hz-1.7B-VoiceDesign",
    "llm": "Qwen3-14B",
}

# model repo ids on huggingface
HF_REPO_IDS = {
    "stt": "Qwen/Qwen3-ASR-1.7B",
    "tts": "Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign",
    "llm": "Qwen/Qwen3-14B",
}

# docker hub repos; one image per service because qwen-asr, qwen-tts and
# vllm pin different exact versions of transformers
IMAGE_REPOS = {
    "stt": "hrithickcodes/qwen3-asr-1.7b-runpod:latest",
    "tts": "hrithickcodes/qwen3-tts-voicedesign-runpod:latest",
    "llm": "hrithickcodes/qwen3-14b-runpod:latest",
}

ENDPOINT_NAMES = {
    "stt": "qwen3-asr-1.7b",
    "tts": "qwen3-tts-voicedesign",
    "llm": "qwen3-14b",
}

# runpod gpu pool ids, all ampere
GPU_POOLS = {
    "stt": "AMPERE_16",  # rtx a4000 16GB
    "tts": "AMPERE_24",  # rtx a5000 24GB, headroom for the 2B tts model
    "llm": "AMPERE_48",  # rtx a6000 48GB, single gpu fits 14B bf16 (~28GB) + kv cache
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
