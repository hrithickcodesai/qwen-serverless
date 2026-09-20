"""download model weights for a service from huggingface into models/.

usage: python scripts/download_model.py stt|tts|llm|all
"""

import sys
from pathlib import Path

from huggingface_hub import snapshot_download

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config

MODELS_DIR = Path(__file__).resolve().parents[1] / "models"


def download(service_name):
    target = MODELS_DIR / config.MODEL_DIRS[service_name]
    print(f"downloading {config.HF_REPO_IDS[service_name]} -> {target}")
    snapshot_download(config.HF_REPO_IDS[service_name], local_dir=target)
    print(f"done: {target}")


def main():
    requested = sys.argv[1] if len(sys.argv) > 1 else "all"
    names = list(config.MODEL_DIRS) if requested == "all" else [requested]
    for name in names:
        if name not in config.MODEL_DIRS:
            sys.exit(f"unknown service '{name}', expected one of {list(config.MODEL_DIRS)}")
        download(name)


if __name__ == "__main__":
    main()
