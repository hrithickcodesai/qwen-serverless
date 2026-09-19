"""synthesize speech via the runpod tts endpoint and save the wav.

examples:
  python scripts/tts.py "Welcome to the future" --instruct "an excited young woman, fast pace"
  python scripts/tts.py "こんにちは" --language Japanese --out hello.wav
"""

import argparse
import base64
import os
import sys
import time
from pathlib import Path

import requests

API_BASE = "https://api.runpod.ai/v2"


def load_dotenv(path=".env"):
    if not Path(path).exists():
        return
    for line in Path(path).read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())


def main():
    load_dotenv()
    parser = argparse.ArgumentParser(description="text to speech via runpod voice-design tts")
    parser.add_argument("text", help="text to synthesize")
    parser.add_argument(
        "--instruct",
        default="",
        help="voice description, e.g. 'deep male narrator, calm and slow'",
    )
    parser.add_argument(
        "--language",
        default="Auto",
        help="Auto, or one of: Chinese, English, Japanese, Korean, German, "
        "French, Russian, Portuguese, Spanish, Italian",
    )
    parser.add_argument("--out", default="output_tts.wav", help="path to save the wav")
    parser.add_argument("--temperature", type=float, default=None)
    parser.add_argument("--top-k", type=int, default=None)
    parser.add_argument("--top-p", type=float, default=None)
    parser.add_argument("--endpoint", default=os.environ.get("TTS_ENDPOINT_ID"))
    parser.add_argument("--timeout", type=int, default=600, help="request timeout in seconds")
    args = parser.parse_args()

    if not args.endpoint:
        sys.exit("endpoint id required: pass --endpoint or set TTS_ENDPOINT_ID in .env")
    api_key = os.environ.get("RUNPOD_API_KEY")
    if not api_key:
        sys.exit("RUNPOD_API_KEY missing in .env")

    payload_input = {
        "text": args.text,
        "instruct": args.instruct,
        "language": args.language,
    }
    for key in ("temperature", "top_k", "top_p"):
        value = getattr(args, key)
        if value is not None:
            payload_input[key] = value

    start = time.time()
    resp = requests.post(
        f"{API_BASE}/{args.endpoint}/runsync",
        headers={"Authorization": f"Bearer {api_key}"},
        json={"input": payload_input},
        timeout=args.timeout,
    )
    elapsed = time.time() - start
    resp.raise_for_status()
    result = resp.json()
    output = result.get("output") or {}
    if output.get("error"):
        sys.exit(f"synthesis failed: {output['error']}")

    Path(args.out).write_bytes(base64.b64decode(output["audio"]))
    print(
        f"saved {args.out} ({output['duration_seconds']}s audio, "
        f"{output['sample_rate']}Hz, {elapsed:.1f}s round trip)"
    )


if __name__ == "__main__":
    main()
