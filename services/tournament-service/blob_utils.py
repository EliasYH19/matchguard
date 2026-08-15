"""
Tiny helper around Azure Blob Storage.

Why is this duplicated in both services instead of a shared package? Because
each microservice is meant to be independently deployable/buildable (own
Dockerfile, own requirements.txt) - that was the whole point of the
monolithic -> microservice lab. Copy-pasting ~40 lines is a fair trade-off
for that independence at this project size.

Local dev note: if AZURE_STORAGE_CONNECTION_STRING isn't set (e.g. you're
just running this on your laptop without an Azure account yet), we fall
back to writing files to a local folder so the app still works end to end.
Swap in your real connection string (from Access keys -> Connection string
in the Azure portal, same as the Lab 06 blob storage exercise) via the
azure-secret.yaml in k8s/ or a .env file for local Docker Compose.
"""

import os
import pathlib

try:
    from azure.storage.blob import BlobServiceClient, ContentSettings
except ImportError:  # pragma: no cover - azure sdk always installed via requirements.txt
    BlobServiceClient = None
    ContentSettings = None

CONNECTION_STRING = os.environ.get("AZURE_STORAGE_CONNECTION_STRING", "")
LOCAL_FALLBACK_DIR = os.environ.get(
    "LOCAL_BLOB_FALLBACK_DIR", os.path.join(os.path.dirname(__file__), "local_blob_storage")
)


def is_blob_configured():
    return bool(CONNECTION_STRING) and BlobServiceClient is not None


def _get_client():
    return BlobServiceClient.from_connection_string(CONNECTION_STRING)


def upload_bytes(container_name, blob_name, data, content_type=None):
    """Uploads bytes and returns a URL/path you can hand back to the frontend.

    Falls back to local disk storage (and a /local-blob/ served path) when no
    Azure Storage account has been wired up yet, so `docker compose up` and
    the pytest suite both work without an Azure subscription.
    """
    if is_blob_configured():
        client = _get_client()
        try:
            client.create_container(container_name)
        except Exception:
            pass  # container already exists - fine
        blob_client = client.get_blob_client(container=container_name, blob=blob_name)
        settings = ContentSettings(content_type=content_type) if content_type else None
        blob_client.upload_blob(data, overwrite=True, content_settings=settings)
        return blob_client.url

    # --- local fallback ---
    target_dir = pathlib.Path(LOCAL_FALLBACK_DIR) / container_name
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / blob_name
    with open(target_path, "wb") as f:
        f.write(data)
    return f"/local-blob/{container_name}/{blob_name}"
