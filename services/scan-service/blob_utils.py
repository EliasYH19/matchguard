"""
Same Azure Blob helper as tournament-service/blob_utils.py - see the
docstring over there for why it's duplicated instead of shared.

Author: Elias
"""

import os
import pathlib

try:
    from azure.storage.blob import BlobServiceClient, ContentSettings
except ImportError:  # pragma: no cover
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
    if is_blob_configured():
        client = _get_client()
        try:
            client.create_container(container_name)
        except Exception:
            pass
        blob_client = client.get_blob_client(container=container_name, blob=blob_name)
        settings = ContentSettings(content_type=content_type) if content_type else None
        blob_client.upload_blob(data, overwrite=True, content_settings=settings)
        return blob_client.url

    target_dir = pathlib.Path(LOCAL_FALLBACK_DIR) / container_name
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / blob_name
    with open(target_path, "wb") as f:
        f.write(data)
    return f"/local-blob/{container_name}/{blob_name}"
