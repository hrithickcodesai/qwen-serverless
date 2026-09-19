# qwen-speech-serverless

Serverless speech endpoints on RunPod, powered by Qwen3 speech models. Two independent services, each a RunPod serverless endpoint that scales to zero:

| service | model | endpoint name | gpu pool | input | output |
| --- | --- | --- | --- | --- | --- |
| **stt** | [Qwen3-ASR-1.7B](https://huggingface.co/Qwen/Qwen3-ASR-1.7B) | `qwen3-asr-1.7b` | A4000 (AMPERE_16) | audio (url or base64 wav) | transcript + language |
| **tts** | [Qwen3-TTS-12Hz-1.7B-VoiceDesign](https://huggingface.co/Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign) | `qwen3-tts-voicedesign` | A5000 (AMPERE_24) | text + voice description | base64 wav |

Both endpoints autoscale (0 to 2 workers, queue-delay scaler) and cost nothing while idle.

## layout

```
config.py                    single source of truth: images, gpu pools, scaling
src/
  worker.py                  container entrypoint; WORKER=stt|tts picks the handler
  stt_handler.py             qwen-asr transcription handler
  tts_handler.py             voice-design tts handler
scripts/
  stt.py                     stt client: mic recording or audio file -> transcript
  tts.py                     tts client: text + instruct -> wav file
  create_endpoint.py         create/update runpod templates + endpoints
  download_model.py          pull model weights from huggingface
requirements-stt.txt         asr deps (transformers 4.57.6)
requirements-tts.txt         tts deps (transformers 4.57.3)
Dockerfile                   one image per service via --build-arg SERVICE=stt|tts
Makefile                     everything: build, push, deploy, test, format
```

the asr and tts packages pin different exact versions of transformers, so they ship as separate images rather than fighting over one environment.

## setup

```bash
make venv                      # python 3.12 virtualenv
make download-models           # ~7GB of weights into models/
docker login                   # docker hub (images push to hrithickcodes/*)
echo 'RUNPOD_API_KEY=...' >> .env
```

## deploy

```bash
make deploy                    # creates/updates both runpod endpoints
# or one at a time
make deploy-stt
make deploy-tts
```

endpoint ids are printed; put them in `.env`:

```
STT_ENDPOINT_ID=...
TTS_ENDPOINT_ID=...
```

changing images: edit `config.py`, then `make push-stt` / `make push-tts`. runpod re-pulls `:latest` on the next cold start; to force a warm worker to refresh, scale the endpoint to 0 workers and back in the runpod console.

## use

speech to text (mic or file):

```bash
.venv/bin/python scripts/stt.py record --seconds 10
.venv/bin/python scripts/stt.py file speech.wav --language English
```

text to speech with a designed voice:

```bash
.venv/bin/python scripts/tts.py "Welcome aboard" \
  --instruct "warm confident narrator, medium pace" \
  --language English --out welcome.wav
```

raw http (both endpoints):

```bash
curl -X POST https://api.runpod.ai/v2/$ENDPOINT_ID/runsync \
  -H "Authorization: Bearer $RUNPOD_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"input": {...}}'
```

### stt request

```json
{
  "audio": "https://example.com/speech.wav",   // http(s) url, base64, or data:audio/...;base64 uri
  "language": "English"                        // optional language hint
}
```

response: `{"text": "...", "language": "English"}`

### tts request

```json
{
  "text": "Text to synthesize",
  "instruct": "voice description: timbre, emotion, pace, accent",  // natural language, may be ""
  "language": "Auto",            // Auto, Chinese, English, Japanese, Korean, German, French, Russian, Portuguese, Spanish, Italian
  "temperature": 0.7,            // optional sampling knobs
  "top_k": 50,
  "top_p": 0.95
}
```

response: `{"audio": "<base64 wav>", "content_type": "audio/wav", "sample_rate": 24000, "duration_seconds": 2.08}`

the `instruct` field is the voice control: describe the speaker and delivery in plain language ("elderly man, gravelly voice, slow", "excited teenage girl, very fast"), and the model designs the voice. on errors the endpoint returns `{"error": "..."}` instead of raising.

## make targets

| target | what it does |
| --- | --- |
| `make venv` | create local virtualenv |
| `make download-models` | fetch stt + tts weights into `models/` |
| `make build-stt` / `build-tts` | docker build the service image |
| `make push-stt` / `push-tts` | build + push to docker hub |
| `make deploy` (or `deploy-stt`/`deploy-tts`) | create/update runpod endpoints |
| `make test-stt WAV=file` | transcribe a file through the live endpoint |
| `make test-tts` | synthesize a sample through the live endpoint |
| `make format` | ruff format + lint fix |
| `make clean` | remove venv, caches, `__pycache__` |

secrets live only in `.env` (gitignored): `RUNPOD_API_KEY`, `STT_ENDPOINT_ID`, `TTS_ENDPOINT_ID`.
