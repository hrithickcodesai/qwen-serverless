"""create/update runpod serverless templates and endpoints.

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


def ensure_template(service):
    template_name = f"{config.ENDPOINT_NAMES[service]}-template"
    resp = runpod.api.graphql.run_graphql_query("{ myself { podTemplates { id name } } }")
    for template in resp["data"]["myself"]["podTemplates"]:
        if template["name"] == template_name:
            print(f"template exists: {template['id']} ({template_name})")
            return template["id"]
    template = ctl.create_template(
        name=template_name,
        image_name=config.IMAGE_REPOS[service],
        container_disk_in_gb=config.settings.container_disk_gb,
        env={
            "WORKER": service,
            "HF_HOME": "/app/hf",
        },
        is_serverless=True,
    )
    print(f"template created: {template['id']} ({template_name})")
    return template["id"]


def ensure_endpoint(service, template_id):
    existing = {e["name"]: e["id"] for e in ctl.get_endpoints()}
    endpoint_name = config.ENDPOINT_NAMES[service]
    if endpoint_name in existing:
        endpoint_id = existing[endpoint_name]
        print(f"endpoint exists: {endpoint_id} ({endpoint_name})")
        update_endpoint(endpoint_id, endpoint_name)
    else:
        endpoint = ctl.create_endpoint(
            endpoint_name,
            template_id,
            gpu_ids=config.GPU_POOLS[service],
            idle_timeout=config.settings.idle_timeout,
            scaler_type=config.settings.scaler_type,
            scaler_value=config.settings.scaler_value,
            workers_min=config.settings.workers_min,
            workers_max=config.settings.workers_max,
            flashboot=config.settings.flashboot,
            gpu_count=config.settings.gpu_count,
        )
        endpoint_id = endpoint["id"]
        print(f"endpoint created: {endpoint_id} ({endpoint_name})")
    print(f"base url: https://api.runpod.ai/v2/{endpoint_id}")
    return endpoint_id


def update_endpoint(endpoint_id, endpoint_name):
    """push current scaling settings to an existing endpoint (sdk has no update call)."""
    query = (
        "mutation { saveEndpoint(input: {"
        f' id: "{endpoint_id}", name: "{endpoint_name}"'
        f", workersMin: {config.settings.workers_min}"
        f", workersMax: {config.settings.workers_max}"
        f", idleTimeout: {config.settings.idle_timeout}"
        f', scalerType: "{config.settings.scaler_type}"'
        f", scalerValue: {config.settings.scaler_value}"
        " }) { id workersMin workersMax idleTimeout } }"
    )
    resp = runpod.api.graphql.run_graphql_query(query)["data"]["saveEndpoint"]
    print(
        f"endpoint updated: min={resp['workersMin']} max={resp['workersMax']} "
        f"idle_timeout={resp['idleTimeout']}s"
    )


def deploy(service_name):
    print(f"--- deploying {service_name}: {config.IMAGE_REPOS[service_name]}")
    template_id = ensure_template(service_name)
    return ensure_endpoint(service_name, template_id)


def main():
    requested = sys.argv[1] if len(sys.argv) > 1 else "all"
    names = list(config.MODEL_DIRS) if requested == "all" else [requested]
    for name in names:
        if name not in config.MODEL_DIRS:
            sys.exit(f"unknown service '{name}', expected one of {list(config.MODEL_DIRS)}")
        endpoint_id = deploy(name)
        print(f"{name}_endpoint_id={endpoint_id}")


if __name__ == "__main__":
    main()
