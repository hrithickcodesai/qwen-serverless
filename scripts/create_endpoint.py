"""create/update runpod serverless templates and endpoints.

usage: python scripts/create_endpoint.py stt|tts|llm|llm-stream|stt-stream|all
"""

import os
import sys
from pathlib import Path

import runpod
import runpod.api.ctl_commands as ctl

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config

runpod.api_key = os.environ["RUNPOD_API_KEY"]


def resolve_service(service_name):
    """map a service name to its deploy config; stream variants inherit gpu/disk
    from the base service but use their own image tag, endpoint name and
    worker count."""
    if service_name.endswith("-stream"):
        base = service_name.replace("-stream", "")
        return {
            "image": config.STREAM_IMAGE_REPOS[base],
            "endpoint": config.STREAM_ENDPOINT_NAMES[base],
            "workers_max": config.WORKERS_MAX_STREAM[base],
            "gpu": config.GPU_POOLS[base],
            "disk": config.DISK_GB[base],
            "env": {"WORKER": service_name, "HF_HOME": "/app/hf"},
        }
    return {
        "image": config.IMAGE_REPOS[service_name],
        "endpoint": config.ENDPOINT_NAMES[service_name],
        "workers_max": config.WORKERS_MAX[service_name],
        "gpu": config.GPU_POOLS[service_name],
        "disk": config.DISK_GB[service_name],
        "env": {"WORKER": service_name, "HF_HOME": "/app/hf"},
    }


def ensure_template(service_name, svc):
    template_name = f"{svc['endpoint']}-template"
    resp = runpod.api.graphql.run_graphql_query("{ myself { podTemplates { id name } } }")
    for template in resp["data"]["myself"]["podTemplates"]:
        if template["name"] == template_name:
            print(f"template exists: {template['id']} ({template_name})")
            return template["id"]
    template = ctl.create_template(
        name=template_name,
        image_name=svc["image"],
        container_disk_in_gb=svc["disk"],
        env=svc["env"],
        is_serverless=True,
    )
    print(f"template created: {template['id']} ({template_name})")
    return template["id"]


def ensure_endpoint(service_name, svc, template_id):
    existing = {e["name"]: e["id"] for e in ctl.get_endpoints()}
    endpoint_name = svc["endpoint"]
    if endpoint_name in existing:
        endpoint_id = existing[endpoint_name]
        print(f"endpoint exists: {endpoint_id} ({endpoint_name})")
        update_endpoint(service_name, svc, endpoint_id, endpoint_name)
    else:
        endpoint = ctl.create_endpoint(
            endpoint_name,
            template_id,
            gpu_ids=svc["gpu"],
            idle_timeout=config.settings.idle_timeout,
            scaler_type=config.settings.scaler_type,
            scaler_value=config.settings.scaler_value,
            workers_min=config.settings.workers_min,
            workers_max=svc["workers_max"],
            flashboot=config.settings.flashboot,
            gpu_count=config.settings.gpu_count,
        )
        endpoint_id = endpoint["id"]
        print(f"endpoint created: {endpoint_id} ({endpoint_name})")
    print(f"base url: https://api.runpod.ai/v2/{endpoint_id}")
    return endpoint_id


def update_endpoint(service_name, svc, endpoint_id, endpoint_name):
    """push current scaling settings to an existing endpoint (sdk has no update call)."""
    query = (
        "mutation { saveEndpoint(input: {"
        f' id: "{endpoint_id}", name: "{endpoint_name}"'
        f", workersMin: {config.settings.workers_min}"
        f", workersMax: {svc['workers_max']}"
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
    svc = resolve_service(service_name)
    print(f"--- deploying {service_name}: {svc['image']}")
    template_id = ensure_template(service_name, svc)
    return ensure_endpoint(service_name, svc, template_id)


def main():
    requested = sys.argv[1] if len(sys.argv) > 1 else "all"
    if requested == "all":
        names = list(config.MODEL_DIRS)
    elif requested == "all-stream":
        names = [f"{s}-stream" for s in config.STREAM_SERVICES]
    else:
        valid = list(config.MODEL_DIRS) + [f"{s}-stream" for s in config.STREAM_SERVICES]
        if requested not in valid:
            sys.exit(f"unknown service '{requested}', expected one of {valid}")
        names = [requested]
    for name in names:
        endpoint_id = deploy(name)
        print(f"{name}_endpoint_id={endpoint_id}")


if __name__ == "__main__":
    main()
