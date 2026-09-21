import os

import runpod

# docker build sets WORKER=<service> or <service>-stream to pick the model
# this container serves; stream variants route to the generator handler
worker = os.environ.get("WORKER", "stt")

modules = {
    "stt": "stt_handler",
    "stt-stream": "stt_handler",
    "tts": "tts_handler",
    "llm": "llm_handler",
    "llm-stream": "llm_handler",
}
if worker not in modules:
    raise ValueError(f"unknown WORKER '{worker}', expected one of {list(modules)}")

module = __import__(modules[worker])
handler = module.handler_stream if worker.endswith("-stream") else module.handler

# generator handlers stream partials to the client via the /stream endpoint;
# return_aggregate_stream makes the final job output the list of all yielded
# chunks (no-op for plain dict returns from the production handlers)
runpod.serverless.start({"handler": handler, "return_aggregate_stream": True})
