import argparse
import base64
import os
import sys
import time
from pathlib import Path

import requests

DEFAULT_RATE = 16000
API_BASE = "https://api.runpod.ai/v2"


def load_dotenv(path=".env"):
    if not Path(path).exists():
        return
    for line in Path(path).read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())


def record_audio(seconds, rate):
    import sounddevice as sd
    import soundfile as sf

    print(f"recording {seconds}s at {rate}Hz from mic... speak now")
    audio = sd.rec(int(seconds * rate), samplerate=rate, channels=1, dtype="int16")
    sd.wait()
    wav_path = Path("/tmp/stt_recording.wav")
    sf.write(wav_path, audio, rate)
    print(f"saved {wav_path}")
    return wav_path.read_bytes()


def transcribe(api_key, endpoint_id, audio_bytes, language, timeout):
    payload = {"input": {"audio": base64.b64encode(audio_bytes).decode()}}
    if language:
        payload["input"]["language"] = language
    start = time.time()
    resp = requests.post(
        f"{API_BASE}/{endpoint_id}/runsync",
        headers={"Authorization": f"Bearer {api_key}"},
        json=payload,
        timeout=timeout,
    )
    elapsed = time.time() - start
    resp.raise_for_status()
    result = resp.json()
    if result.get("error"):
        sys.exit(f"transcription failed: {result['error']}")
    return result["output"], elapsed


def main():
    load_dotenv()
    parser = argparse.ArgumentParser(
        description="record or transcribe audio via runpod stt"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    rec = sub.add_parser("record", help="record from mic and transcribe")
    rec.add_argument("--seconds", type=float, default=10, help="recording length")
    rec.add_argument("--rate", type=int, default=DEFAULT_RATE, help="sample rate")
    rec.add_argument(
        "--playback", action="store_true", help="play back recording before sending"
    )

    file_cmd = sub.add_parser("file", help="transcribe an existing audio file")
    file_cmd.add_argument("path")

    for cmd in (rec, file_cmd):
        cmd.add_argument(
            "--language", default=None, help='language hint, e.g. "English"'
        )
        cmd.add_argument(
            "--endpoint",
            default=os.environ.get("STT_ENDPOINT_ID") or os.environ.get("ENDPOINT_ID"),
            help="runpod endpoint id",
        )
        cmd.add_argument(
            "--timeout", type=int, default=300, help="request timeout in seconds"
        )

    args = parser.parse_args()
    if not args.endpoint:
        sys.exit("endpoint id required: pass --endpoint or set ENDPOINT_ID in .env")
    api_key = os.environ.get("RUNPOD_API_KEY")
    if not api_key:
        sys.exit("RUNPOD_API_KEY missing in .env")

    if args.command == "record":
        audio_bytes = record_audio(args.seconds, args.rate)
        if args.playback:
            import sounddevice as sd
            import soundfile as sf

            data, rate = sf.read("/tmp/stt_recording.wav")
            sd.play(data, rate)
            sd.wait()
    else:
        audio_bytes = Path(args.path).read_bytes()

    print(f"sending {len(audio_bytes)} bytes to endpoint {args.endpoint}...")
    output, elapsed = transcribe(
        api_key, args.endpoint, audio_bytes, args.language, args.timeout
    )
    print(f"language: {output['language']} ({elapsed:.1f}s round trip)")
    print(f"text: {output['text']}")


if __name__ == "__main__":
    main()
