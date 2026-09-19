"""download model weights for a service from huggingface into models/.

usage: python scripts/download_model.py stt|tts|all
"""

import sys
from pathlib import Path

from huggingface_hub import snapshot_download

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config


def download(service_name):
    service = config.SERVICES[service_name]
    target = config.MODELS_DIR / service.local_model_dir
    print(f"downloading {service.model_repo_id} -> {target}")
    snapshot_download(service.model_repo_id, local_dir=target)
    print(f"done: {target}")


def main():
    requested = sys.argv[1] if len(sys.argv) > 1 else "all"
    names = list(config.SERVICES) if requested == "all" else [requested]
    for name in names:
        if name not in config.SERVICES:
            sys.exit(
                f"unknown service '{name}', expected one of {list(config.SERVICES)}"
            )
        download(name)


if __name__ == "__main__":
    main()
