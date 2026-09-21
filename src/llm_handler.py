import asyncio
import json
import os
import queue
import threading
import time
import uuid

from loguru import logger
from transformers import AutoTokenizer
from vllm import AsyncEngineArgs, AsyncLLMEngine, SamplingParams

MODEL_ID = os.environ.get("LLM_MODEL_ID", "Qwen/Qwen3.5-9B")

engine = None
tokenizer = None

# async engine must live on a dedicated, always-running event loop; handlers
# then bridge engine outputs into sync returns/yields via a queue
_loop = asyncio.new_event_loop()


def _run_loop():
    asyncio.set_event_loop(_loop)
    _loop.run_forever()


threading.Thread(target=_run_loop, daemon=True).start()


def load_model():
    global engine, tokenizer
    logger.info("loading llm {}", MODEL_ID)
    # vllm v1 engine: paged kv cache + continuous batching, flash attention
    # backend selected automatically on ampere. prefix caching reuses the
    # shared prompt prefix across requests. 0.90 gpu util leaves headroom for
    # activation spikes without oom; max_model_len keeps kv memory bounded.
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
    # engine (and its output-handler task) must be created on the engine loop
    engine = asyncio.run_coroutine_threadsafe(_create_engine(engine_kwargs), _loop).result()
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
    logger.info("llm loaded")


async def _create_engine(engine_kwargs):
    return AsyncLLMEngine.from_engine_args(AsyncEngineArgs(**engine_kwargs))


def _prepare(job_input):
    """shared validation + prompt/sampling construction for both handlers."""
    messages = job_input.get("messages")
    prompt = job_input.get("prompt")
    if not prompt and not messages:
        return None
    sampling = SamplingParams(
        temperature=job_input.get("temperature", 0.7),
        top_p=job_input.get("top_p", 0.8),
        top_k=job_input.get("top_k", 20),
        max_tokens=job_input.get("max_tokens", 512),
    )
    if messages:
        text = tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
            enable_thinking=job_input.get("enable_thinking", False),
        )
    else:
        text = prompt
    return text, sampling


def _iter_engine(text, sampling):
    """submit to the engine loop; yield (kind, payload) items via a queue."""
    chunks = queue.Queue()
    request_id = uuid.uuid4().hex
    t0 = time.perf_counter()
    first_logged = False

    async def _stream():
        nonlocal first_logged
        try:
            async for out in engine.generate(text, sampling, request_id):
                if not first_logged:
                    first_logged = True
                    logger.info(
                        "llm ttft (engine): first output after {:.2f}s",
                        time.perf_counter() - t0,
                    )
                chunks.put(("out", out))
            chunks.put(("done", None))
        except BaseException as exc:  # noqa: BLE001 - caller needs an error payload
            chunks.put(("error", exc))

    asyncio.run_coroutine_threadsafe(_stream(), _loop)
    while True:
        yield chunks.get()


def handler(job):
    """plain handler: full result in one dict (production contract)."""
    prepared = _prepare(job.get("input") or {})
    if prepared is None:
        return {"error": "input must include 'messages' (chat) or 'prompt' (raw)"}
    text, sampling = prepared

    # engine yields cumulative text, so keep the latest full text
    final_text = ""
    finish_reason = None
    try:
        for kind, payload in _iter_engine(text, sampling):
            if kind == "done":
                break
            if kind == "error":
                raise payload
            completion = payload.outputs[0]
            final_text = completion.text
            finish_reason = completion.finish_reason or finish_reason
    except Exception as exc:  # noqa: BLE001 - serverless caller needs an error payload
        logger.exception("generation failed")
        return {"error": f"{type(exc).__name__}: {exc}"}

    logger.info("generated {} chars, finish_reason={}", len(final_text), finish_reason)
    return {
        "text": final_text,
        "finish_reason": finish_reason,
        "prompt_tokens": len(tokenizer.encode(text)) if text else 0,
        "completion_tokens": len(tokenizer.encode(final_text)) if final_text else 0,
    }


def handler_stream(job):
    """generator handler: one yield per output step, final yield with stats."""
    prepared = _prepare(job.get("input") or {})
    if prepared is None:
        yield {"error": "input must include 'messages' (chat) or 'prompt' (raw)"}
        return
    text, sampling = prepared

    prev_text = ""
    finish_reason = None
    try:
        for kind, payload in _iter_engine(text, sampling):
            if kind == "done":
                break
            if kind == "error":
                raise payload
            completion = payload.outputs[0]
            finish_reason = completion.finish_reason or finish_reason
            cur_text = completion.text
            if not cur_text.startswith(prev_text):
                raise ValueError(f"non-monotonic engine output: {prev_text!r} -> {cur_text!r}")
            delta = cur_text[len(prev_text) :]
            prev_text = cur_text
            if not delta:
                continue
            yield {"delta": delta}
    except Exception as exc:  # noqa: BLE001 - serverless caller needs an error payload
        logger.exception("generation failed")
        yield {"error": f"{type(exc).__name__}: {exc}"}
        return

    logger.info("streamed {} chars, finish_reason={}", len(prev_text), finish_reason)
    yield {
        "text": prev_text,
        "finish_reason": finish_reason,
        "prompt_tokens": len(tokenizer.encode(text)) if text else 0,
        "completion_tokens": len(tokenizer.encode(prev_text)) if prev_text else 0,
    }


load_model()
