"""create/update runpod serverless templates and endpoints for the services in config.py.

usage: python scripts/create_endpoint.py stt|tts|all
"""

import os
import sys
from pathlib import Path

import runpod
import runpod.api.ctl_commands as ctl

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config

runpod.api_key = os.environ["RUNPOD_API_KEY"]


def pick_gpu(gpu_pool_id):
    for gpu in ctl.get_gpus():
        if gpu.get("id") == gpu_pool_id:
            print(
                f"using gpu pool: {gpu_pool_id} ({gpu['displayName']} {gpu['memoryInGb']}GB)"
            )
            return
    print(f"using gpu pool: {gpu_pool_id}")


def ensure_template(service):
    template_name = f"{service.endpoint_name}-template"
    resp = runpod.api.graphql.run_graphql_query(
        "{ myself { podTemplates { id name } } }"
    )
    for template in resp["data"]["myself"]["podTemplates"]:
        if template["name"] == template_name:
            print(f"template exists: {template['id']} ({template_name})")
            return template["id"]
    template = ctl.create_template(
        name=template_name,
        image_name=service.image,
        container_disk_in_gb=service.container_disk_gb,
        env={
            "WORKER": service.name,
            "HF_HOME": config.HF_HOME_IN_CONTAINER,
        },
        is_serverless=True,
    )
    print(f"template created: {template['id']} ({template_name})")
    return template["id"]


def ensure_endpoint(service, template_id):
    existing = {e["name"]: e["id"] for e in ctl.get_endpoints()}
    if service.endpoint_name in existing:
        endpoint_id = existing[service.endpoint_name]
        print(f"endpoint exists: {endpoint_id} ({service.endpoint_name})")
    else:
        endpoint = ctl.create_endpoint(
            service.endpoint_name,
            template_id,
            gpu_ids=service.gpu_pool,
            idle_timeout=config.IDLE_TIMEOUT,
            scaler_type=config.SCALER_TYPE,
            scaler_value=config.SCALER_VALUE,
            workers_min=config.WORKERS_MIN,
            workers_max=config.WORKERS_MAX,
        )
        endpoint_id = endpoint["id"]
        print(f"endpoint created: {endpoint_id} ({service.endpoint_name})")
    print(f"base url: https://api.runpod.ai/v2/{endpoint_id}")
    return endpoint_id


def deploy(service_name):
    service = config.SERVICES[service_name]
    print(f"--- deploying {service.name}: {service.image}")
    pick_gpu(service.gpu_pool)
    template_id = ensure_template(service)
    return ensure_endpoint(service, template_id)


def main():
    requested = sys.argv[1] if len(sys.argv) > 1 else "all"
    names = list(config.SERVICES) if requested == "all" else [requested]
    for name in names:
        if name not in config.SERVICES:
            sys.exit(
                f"unknown service '{name}', expected one of {list(config.SERVICES)}"
            )
        endpoint_id = deploy(name)
        print(f"{name}_endpoint_id={endpoint_id}")


if __name__ == "__main__":
    main()
