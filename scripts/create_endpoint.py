import os

import runpod
import runpod.api.ctl_commands as ctl

runpod.api_key = os.environ["RUNPOD_API_KEY"]

IMAGE = os.environ.get("IMAGE", "hrithickcodes/qwen3-asr-1.7b-runpod:latest")
ENDPOINT_NAME = os.environ.get("ENDPOINT_NAME", "qwen3-asr-1.7b")


GPU_POOL_IDS = {
    "A4000": "AMPERE_16",
    "4090": "ADA_24",
    "A5000": "AMPERE_24",
    "A6000": "AMPERE_48",
}


def pick_gpu():
    gpus = ctl.get_gpus()
    for gpu_name, pool_id in GPU_POOL_IDS.items():
        for gpu in gpus:
            if gpu_name in gpu["displayName"]:
                print(
                    f"using gpu: {gpu['displayName']} ({pool_id}, {gpu['memoryInGb']}GB)"
                )
                return pool_id
    print("no preferred gpu found, falling back to AMPERE_16")
    return "AMPERE_16"


def set_endpoint_gpu(endpoint_id, pool_id):
    query = (
        'mutation { saveEndpoint(input: { id: "'
        + endpoint_id
        + '", name: "'
        + ENDPOINT_NAME
        + '", gpuIds: "'
        + pool_id
        + '" }) { id gpuIds } }'
    )
    runpod.api.graphql.run_graphql_query(query)


def find_template_id(name):
    resp = runpod.api.graphql.run_graphql_query(
        "{ myself { podTemplates { id name } } }"
    )
    for template in resp["data"]["myself"]["podTemplates"]:
        if template["name"] == name:
            return template["id"]
    return None


def main():
    gpu_id = pick_gpu()

    existing = {e["name"]: e["id"] for e in ctl.get_endpoints()}
    if ENDPOINT_NAME in existing:
        endpoint_id = existing[ENDPOINT_NAME]
        set_endpoint_gpu(endpoint_id, gpu_id)
        print(f"endpoint already exists: {endpoint_id}")
        print(f"base url: https://api.runpod.io/v2/{endpoint_id}")
        return

    template_id = find_template_id(f"{ENDPOINT_NAME}-template")
    if template_id:
        print(f"template exists: {template_id}")
    else:
        template = ctl.create_template(
            name=f"{ENDPOINT_NAME}-template",
            image_name=IMAGE,
            container_disk_in_gb=25,
            env={"HF_HOME": "/app/hf"},
            is_serverless=True,
        )
        template_id = template["id"]
        print(f"template created: {template_id}")

    endpoint = ctl.create_endpoint(
        ENDPOINT_NAME,
        template_id,
        gpu_ids=gpu_id,
        idle_timeout=10,
        scaler_type="QUEUE_DELAY",
        scaler_value=4,
        workers_min=0,
        workers_max=2,
    )
    print(f"endpoint created: {endpoint['id']} ({endpoint['name']})")
    print(f"base url: https://api.runpod.io/v2/{endpoint['id']}")


if __name__ == "__main__":
    main()
