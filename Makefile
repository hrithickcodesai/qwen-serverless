SHELL := /bin/bash

include .env
export

VENV := .venv
PYTHON := $(VENV)/bin/python

# config.py is the single source of truth; makefile reads values through its cli
STT_IMAGE := $(shell python3 config.py stt image)
TTS_IMAGE := $(shell python3 config.py tts image)

.PHONY: venv download-models auth-runpod auth-docker build-stt build-tts push-stt push-tts deploy-stt deploy-tts deploy test-stt test-tts format clean

$(VENV):
	python3.12 -m venv $(VENV) \
		&& $(VENV)/bin/pip install -U pip \
		&& $(VENV)/bin/pip install runpod requests ruff sounddevice soundfile "huggingface_hub[hf_transfer,hf-xet]"

venv: $(VENV)

download-models: venv
	$(PYTHON) scripts/download_model.py all

auth-runpod: venv
	@$(PYTHON) -c "import os, sys; sys.exit(0 if os.environ.get('RUNPOD_API_KEY') else print('RUNPOD_API_KEY missing in .env') or 1)"
	@$(PYTHON) -c "import os, requests; r = requests.post('https://api.runpod.io/graphql?api_key=' + os.environ['RUNPOD_API_KEY'], json={'query': '{ myself { id } }'}, timeout=30); r.raise_for_status(); print('runpod auth ok:', r.json()['data']['myself']['id'])"

auth-docker:
	@docker info >/dev/null 2>&1 || { echo 'docker is not running'; exit 1; }
	@docker info 2>/dev/null | grep -q Username || echo 'warning: docker hub login not detected, push may fail'

build-stt:
	docker build --platform linux/amd64 --build-arg SERVICE=stt --build-arg MODEL_DIR=Qwen3-ASR-1.7B -t $(STT_IMAGE) .

build-tts:
	docker build --platform linux/amd64 --build-arg SERVICE=tts --build-arg MODEL_DIR=Qwen3-TTS-12Hz-1.7B-VoiceDesign -t $(TTS_IMAGE) .

push-stt: auth-docker build-stt
	docker push $(STT_IMAGE)

push-tts: auth-docker build-tts
	docker push $(TTS_IMAGE)

deploy-stt: venv
	$(PYTHON) scripts/create_endpoint.py stt

deploy-tts: venv
	$(PYTHON) scripts/create_endpoint.py tts

deploy: deploy-stt deploy-tts

test-stt: venv
	@if [ -z "$(WAV)" ]; then echo 'usage: make test-stt WAV=path/to/audio.wav'; exit 1; fi
	$(PYTHON) scripts/stt.py file $(WAV)

test-tts: venv
	$(PYTHON) scripts/tts.py "This voice was designed on demand." --instruct "warm confident narrator, medium pace" --out /tmp/test_tts.wav

format: venv
	$(VENV)/bin/ruff format .
	$(VENV)/bin/ruff check --fix .

clean:
	rm -rf $(VENV) .ruff_cache
	find . -name __pycache__ -type d -exec rm -rf {} +
