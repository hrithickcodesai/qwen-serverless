SHELL := /bin/bash

include .env
export

REGISTRY := hrithickcodes
IMAGE := hrithickcodes/qwen3-asr-1.7b-runpod:latest
export IMAGE

VENV := .venv
PYTHON := $(VENV)/bin/python

$(VENV):
	python3.12 -m venv $(VENV) \
		&& $(VENV)/bin/pip install -U pip \
		&& $(VENV)/bin/pip install runpod requests ruff "huggingface_hub[hf_transfer]"

venv: $(VENV)

HF_BASE := https://huggingface.co/Qwen/Qwen3-ASR-1.7B/resolve/main

models/Qwen3-ASR-1.7B/model-00001-of-00002.safetensors:
	$(PYTHON) scripts/fast_download.py $(HF_BASE)/model-00001-of-00002.safetensors $@

models/Qwen3-ASR-1.7B/model-00002-of-00002.safetensors:
	$(PYTHON) scripts/fast_download.py $(HF_BASE)/model-00002-of-00002.safetensors $@

models/Qwen3-ASR-1.7B/.complete: models/Qwen3-ASR-1.7B/model-00001-of-00002.safetensors models/Qwen3-ASR-1.7B/model-00002-of-00002.safetensors
	rm -rf models/Qwen3-ASR-1.7B/.cache
	@touch $@

download-model: models/Qwen3-ASR-1.7B/.complete

auth-runpod: venv
	@$(PYTHON) -c "import os, sys; sys.exit(0 if os.environ.get('RUNPOD_API_KEY') else print('RUNPOD_API_KEY missing in .env') or 1)"
	@$(PYTHON) -c "import os, requests; r = requests.post('https://api.runpod.io/graphql?api_key=' + os.environ['RUNPOD_API_KEY'], json={'query': '{ myself { id } }'}, timeout=30); r.raise_for_status(); print('runpod auth ok:', r.json()['data']['myself']['id'])"

auth-docker:
	@docker info >/dev/null 2>&1 || { echo 'docker is not running'; exit 1; }
	@docker info 2>/dev/null | grep -q Username || echo 'warning: docker hub login not detected, push may fail'

build: download-model
	docker build --platform linux/amd64 -t $(IMAGE) .

push: auth-docker
	docker push $(IMAGE)

deploy: venv
	$(PYTHON) scripts/create_endpoint.py

test: venv
	@if [ -z "$(ENDPOINT_ID)" ]; then echo 'usage: make test ENDPOINT_ID=<id>'; exit 1; fi
	$(PYTHON) scripts/test_endpoint.py $(ENDPOINT_ID)

format: venv
	$(VENV)/bin/ruff format .
	$(VENV)/bin/ruff check --fix .

clean:
	rm -rf $(VENV) .ruff_cache

.PHONY: venv download-model auth-runpod auth-docker build push deploy test format clean
