import os
import sys

import requests

API_KEY = os.environ.get("RUNPOD_API_KEY")
if not API_KEY:
    sys.exit("RUNPOD_API_KEY is not set, source .env first")

IMAGE = os.environ.get("IMAGE", "ghcr.io/hrithickcodesai/qwen3-asr-1.7b-runpod:latest")
ENDPOINT_NAME = os.environ.get("ENDPOINT_NAME", "qwen3-asr-1.7b")
GRAPHQL_URL = f"https://api.runpod.io/graphql?api_key={API_KEY}"


def graphql(query, variables=None):
    resp = requests.post(
        GRAPHQL_URL, json={"query": query, "variables": variables or {}}, timeout=60
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("errors"):
        sys.exit(f"graphql error: {data['errors']}")
    return data["data"]


def pick_gpu():
    data = graphql(
        """
        query GpuTypes {
          gpuTypes {
            id
            displayName
            memoryInGb
          }
        }
        """
    )
    types = data["gpuTypes"]
    for gpu in types:
        if "A4000" in gpu["displayName"]:
            print(
                f"using gpu: {gpu['displayName']} ({gpu['id']}, {gpu['memoryInGb']}GB)"
            )
            return gpu["id"]
    for gpu in sorted(types, key=lambda g: g["memoryInGb"]):
        if gpu["memoryInGb"] >= 16:
            print(
                f"no A4000 found, falling back to: {gpu['displayName']} ({gpu['id']})"
            )
            return gpu["id"]
    sys.exit("no suitable gpu type found")


def main():
    gpu_id = pick_gpu()
    data = graphql(
        """
        mutation CreateEndpoint($input: EndpointInput!) {
          createEndpoint(input: $input) {
            id
            name
            gpuIds
          }
        }
        """,
        {
            "input": {
                "name": ENDPOINT_NAME,
                "image": IMAGE,
                "gpuIds": gpu_id,
                "workersMin": 0,
                "workersMax": 2,
                "idleTimeout": 10,
                "executionTimeout": 600,
                "containerDiskInGb": 25,
                "scalerType": "QUEUE_DELAY",
                "scalerValue": 4,
                "env": [{"key": "HF_HOME", "value": "/app/hf"}],
            }
        },
    )
    endpoint = data["createEndpoint"]
    print(f"endpoint created: {endpoint['id']} ({endpoint['name']})")
    print(f"base url: https://api.runpod.io/v2/{endpoint['id']}")


if __name__ == "__main__":
    main()
