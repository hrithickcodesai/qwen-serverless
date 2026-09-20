SHELL := /bin/bash

include .env
export

# single source of truth is config.py; makefile reads images through uv
# (uv run bootstraps the venv on demand, no shell python needed)
STT_IMAGE := $(shell uv run --no-sync python -c "import config; print(config.IMAGE_REPOS['stt'])")
TTS_IMAGE := $(shell uv run --no-sync python -c "import config; print(config.IMAGE_REPOS['tts'])")
LLM_IMAGE := $(shell uv run --no-sync python -c "import config; print(config.IMAGE_REPOS['llm'])")

.PHONY: sync download-models build-stt build-tts build-llm push-stt push-tts push-llm deploy deploy-stt deploy-tts deploy-llm deploy-config format clean

# uv replaces pip + manual venv: creates .venv and installs from pyproject.lock
sync:
	uv sync --extra client

download-models: sync
	uv run python scripts/download_model.py all

build-stt:
	docker build --platform linux/amd64 --build-arg SERVICE=stt --build-arg MODEL_DIR=Qwen3-ASR-1.7B -t $(STT_IMAGE) .

build-tts:
	docker build --platform linux/amd64 --build-arg SERVICE=tts --build-arg MODEL_DIR=Qwen3-TTS-12Hz-1.7B-VoiceDesign -t $(TTS_IMAGE) .

build-llm:
	docker build --platform linux/amd64 --build-arg SERVICE=llm --build-arg MODEL_DIR=Qwen3-14B -t $(LLM_IMAGE) .

push-stt: build-stt
	docker push $(STT_IMAGE)

push-tts: build-tts
	docker push $(TTS_IMAGE)

push-llm: build-llm
	docker push $(LLM_IMAGE)

deploy-stt: sync
	uv run python scripts/create_endpoint.py stt

deploy-tts: sync
	uv run python scripts/create_endpoint.py tts

deploy-llm: sync
	uv run python scripts/create_endpoint.py llm

deploy: deploy-stt deploy-tts deploy-llm

# print effective deploy config (images, gpu pools, scaling) without deploying
deploy-config:
	@uv run --no-sync python config.py

format:
	uv run ruff format .
	uv run ruff check --fix .

clean:
	rm -rf .venv .ruff_cache uv.lock
	find . -name __pycache__ -type d -exec rm -rf {} +
