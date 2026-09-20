import json
import os

from loguru import logger
from transformers import AutoTokenizer
from vllm import LLM, SamplingParams

MODEL_ID = os.environ.get("LLM_MODEL_ID", "/app/models/Qwen3-14B")

llm = None
tokenizer = None


def load_model():
    global llm, tokenizer
    logger.info("loading llm {}", MODEL_ID)
    # vllm: paged kv cache + continuous batching + fused flashattention
    # kernels by default on ampere. prefix caching reuses the shared prompt
    # prefix across requests. 0.90 gpu util leaves headroom for activation
    # spikes without oom; max_model_len keeps kv memory bounded.
    engine_kwargs = dict(
        model=MODEL_ID,
        dtype="bfloat16",
        gpu_memory_utilization=0.90,
        max_model_len=8192,
        enable_prefix_caching=True,
        enforce_eager=False,
    )
    # optional speculative decoding via env, e.g.
    # VLLM_SPEC_DECODE='{"method": "ngram", "prompt_lookup_num_tokens": 5}'
    spec = os.environ.get("VLLM_SPEC_DECODE")
    if spec:
        engine_kwargs["speculative_config"] = json.loads(spec)
    llm = LLM(**engine_kwargs)
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
    logger.info("llm loaded")


def handler(job):
    job_input = job.get("input") or {}
    messages = job_input.get("messages")
    prompt = job_input.get("prompt")
    if not prompt and not messages:
        return {"error": "input must include 'messages' (chat) or 'prompt' (raw)"}

    sampling = SamplingParams(
        temperature=job_input.get("temperature", 0.7),
        top_p=job_input.get("top_p", 0.95),
        top_k=job_input.get("top_k", 20),
        max_tokens=job_input.get("max_tokens", 512),
    )

    try:
        if messages:
            prompt_text = tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True,
                enable_thinking=job_input.get("enable_thinking", False),
            )
            completions = llm.generate([prompt_text], sampling)
        else:
            completions = llm.generate([prompt], sampling)
        completion = completions[0]
        return {
            "text": completion.outputs[0].text,
            "finish_reason": completion.outputs[0].finish_reason,
            "prompt_tokens": len(completion.prompt_token_ids),
            "completion_tokens": len(completion.outputs[0].token_ids),
        }
    except Exception as exc:  # noqa: BLE001 - serverless caller needs an error payload
        logger.exception("generation failed")
        return {"error": f"{type(exc).__name__}: {exc}"}


load_model()
