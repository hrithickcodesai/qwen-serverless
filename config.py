"""single source of truth for non-secret deploy config.

secrets (RUNPOD_API_KEY etc.) live in .env; everything deployable lives here.
makefile and scripts both read from this module.
"""

import pathlib

DOCKERHUB_NAMESPACE = "hrithickcodes"
HF_HOME_IN_CONTAINER = "/app/hf"

MODELS_DIR = pathlib.Path(__file__).parent / "models"


class Service:
    name: str
    image_repo: str
    endpoint_name: str
    gpu_pool: str
    container_disk_gb: int

    def __init__(
        self,
        name,
        model_repo_id,
        local_model_dir,
        image_repo,
        endpoint_name,
        gpu_pool,
        container_disk_gb=25,
    ):
        self.name = name
        self.model_repo_id = model_repo_id
        self.local_model_dir = local_model_dir
        self.image_repo = image_repo
        self.endpoint_name = endpoint_name
        self.gpu_pool = gpu_pool
        self.container_disk_gb = container_disk_gb

    @property
    def image(self):
        return f"{DOCKERHUB_NAMESPACE}/{self.image_repo}:latest"


# gpu pool ids come from runpod's ctl API (see pick_gpu in scripts/create_endpoint.py)
GPU_POOLS = {
    "A4000": "AMPERE_16",
    "4090": "ADA_24",
    "A5000": "AMPERE_24",
    "A6000": "AMPERE_48",
}

SERVICES = {
    # ampere 24GB (A5000): headroom for the 2B tts model plus codec decode
    "stt": Service(
        name="stt",
        model_repo_id="Qwen/Qwen3-ASR-1.7B",
        local_model_dir="Qwen3-ASR-1.7B",
        image_repo="qwen3-asr-1.7b-runpod",
        endpoint_name="qwen3-asr-1.7b",
        gpu_pool=GPU_POOLS["A4000"],
    ),
    "tts": Service(
        name="tts",
        model_repo_id="Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign",
        local_model_dir="Qwen3-TTS-12Hz-1.7B-VoiceDesign",
        image_repo="qwen3-tts-voicedesign-runpod",
        endpoint_name="qwen3-tts-voicedesign",
        gpu_pool=GPU_POOLS["A5000"],
    ),
}

# shared endpoint scaling behaviour
IDLE_TIMEOUT = 10
SCALER_TYPE = "QUEUE_DELAY"
SCALER_VALUE = 4
WORKERS_MIN = 0
WORKERS_MAX = 2


def _main():
    """print config values for the makefile: python3 config.py <service> <attr>"""
    import sys

    service_name, attr = sys.argv[1], sys.argv[2]
    print(getattr(SERVICES[service_name], attr))


if __name__ == "__main__":
    _main()
