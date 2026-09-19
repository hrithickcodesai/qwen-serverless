import os

import runpod

# docker build sets WORKER=stt|tts to pick which model this container serves
worker = os.environ.get("WORKER", "stt")

if worker == "tts":
    from tts_handler import handler
else:
    from stt_handler import handler

runpod.serverless.start({"handler": handler})
