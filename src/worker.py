import os

import runpod

# docker build sets WORKER=<service> or <service>-stream to pick the model
# and handler variant this container serves
worker = os.environ.get("WORKER", "stt")

handlers = {
    "stt": "stt_handler",
    "stt-stream": "stt_handler",
    "tts": "tts_handler",
    "llm": "llm_handler",
    "llm-stream": "llm_handler",
}
if worker not in handlers:
    raise ValueError(f"unknown WORKER '{worker}', expected one of {list(handlers)}")

handler = __import__(handlers[worker]).handler

# generator handlers stream partials to the client via the /stream endpoint;
# return_aggregate_stream also makes the final job output the list of all
# yielded chunks (no-op for plain dict returns from tts)
runpod.serverless.start({"handler": handler, "return_aggregate_stream": True})
