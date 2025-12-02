import os
import sys
import time
import logging
from typing import List, Set
from kubernetes import client, config
from kubernetes.config.config_exception import ConfigException
from kubernetes.client.rest import ApiException

# --- Logging ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logger = logging.getLogger("imagepullsecret-patcher")

# --- Config auto-detection ---
def load_kube_config_auto():
    in_cluster = os.path.exists("/var/run/secrets/kubernetes.io/serviceaccount/token")
    if in_cluster:
        config.load_incluster_config()
        logger.info("Using in-cluster Kubernetes config.")
    else:
        config.load_kube_config()
        logger.info("Using local kubeconfig.")

# --- Helper: get namespaces (respecting annotation-based exclusion) ---
def get_namespaces_to_process(v1: client.CoreV1Api) -> List[str]:
    try:
        namespaces = v1.list_namespace().items
    except ApiException as e:
        logger.error(f"Failed to list namespaces: {e}")
        sys.exit(1)

    result = []
    for ns in namespaces:
        name = ns.metadata.name
        annotations = ns.metadata.annotations or {}
        if annotations.get("k8s.titansoft.com/imagepullsecret-patcher-exclude") == "true":
            logger.debug(f"Skipping namespace {name} (excluded via annotation)")
            continue
        result.append(name)
    return result

# --- Helper: get service account names in namespace ---
def get_serviceaccounts_to_patch(v1: client.CoreV1Api, namespace: str, patch_all: bool) -> List[str]:
    if patch_all:
        try:
            sas = v1.list_namespaced_service_account(namespace).items
            return [sa.metadata.name for sa in sas]
        except ApiException as e:
            logger.warning(f"Failed to list ServiceAccounts in {namespace}: {e}")
            return []
    else:
        return ["default"]

# --- Main logic ---
def patch_serviceaccounts(
    v1: client.CoreV1Api,
    namespaces: List[str],
    secret_names: List[str],
    patch_all: bool,
    force: bool,
    managedonly: bool
) -> int:
    patched = 0
    secret_set = set(secret_names)
    image_pull_secrets = [{"name": name} for name in secret_names]

    for namespace in namespaces:
        sa_names = get_serviceaccounts_to_patch(v1, namespace, patch_all)
        for sa_name in sa_names:
            try:
                sa = v1.read_namespaced_service_account(sa_name, namespace)
            except ApiException as e:
                if e.status == 404:
                    continue  # might have been deleted
                logger.warning(f"Failed to read SA {namespace}/{sa_name}: {e}")
                continue

            current_secrets = {s.name for s in (sa.image_pull_secrets or [])}

            # managedonly: only patch if at least one of our secrets is already present
            if managedonly and not (current_secrets & secret_set):
                continue

            # If all required secrets are present → skip (unless force=true)
            if not force and secret_set.issubset(current_secrets):
                continue

            # Build updated list (avoid duplicates)
            updated = list(sa.image_pull_secrets or [])
            for ref in image_pull_secrets:
                if ref["name"] not in current_secrets:
                    updated.append(ref)

            try:
                patch = {"imagePullSecrets": updated}
                v1.patch_namespaced_service_account(sa_name, namespace, patch)
                logger.info(f"Patched {namespace}/{sa_name}")
                patched += 1
            except ApiException as e:
                logger.error(f"Failed to patch {namespace}/{sa_name}: {e}")

    return patched

def main():
    load_kube_config_auto()

    # --- Config from env ---
    secret_names_str = os.getenv("REGISTRY_SECRET_NAMES", "").strip()
    if not secret_names_str:
        logger.error("REGISTRY_SECRET_NAMES env var is required")
        sys.exit(1)
    REGISTRY_SECRET_NAMES = [n.strip() for n in secret_names_str.split(",") if n.strip()]

    RUN_ONCE = os.getenv("RUN_ONCE", "false").lower() in ("true", "1", "yes")
    LOOP_INTERVAL = int(os.getenv("LOOP_INTERVAL", "10"))
    PATCH_ALL_SERVICEACCOUNTS = os.getenv("PATCH_ALL_SERVICEACCOUNTS", "false").lower() in ("true", "1", "yes")
    FORCE = os.getenv("FORCE", "true").lower() in ("true", "1", "yes")
    MANAGEDONLY = os.getenv("MANAGEDONLY", "false").lower() in ("true", "1", "yes")

    logger.info(f"Config: secrets={REGISTRY_SECRET_NAMES}, all_sa={PATCH_ALL_SERVICEACCOUNTS}, "
                f"force={FORCE}, managedonly={MANAGEDONLY}, run_once={RUN_ONCE}, interval={LOOP_INTERVAL}s")

    v1 = client.CoreV1Api()

    while True:
        namespaces = get_namespaces_to_process(v1)
        logger.info(f"Processing {len(namespaces)} namespaces (excluding annotated ones)")

        patched = patch_serviceaccounts(
            v1=v1,
            namespaces=namespaces,
            secret_names=REGISTRY_SECRET_NAMES,
            patch_all=PATCH_ALL_SERVICEACCOUNTS,
            force=FORCE,
            managedonly=MANAGEDONLY
        )
        logger.info(f"Completed cycle: patched {patched} ServiceAccount(s)")

        if RUN_ONCE:
            break

        logger.info(f"Sleeping for {LOOP_INTERVAL} seconds...")
        time.sleep(LOOP_INTERVAL)

if __name__ == "__main__":
    main()