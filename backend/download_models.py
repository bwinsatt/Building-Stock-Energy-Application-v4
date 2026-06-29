"""Download XGBoost models from Azure Blob Storage to local volume.

Runs on container startup. By default, it behaves like a one-time cache fill.
If MODEL_BUNDLE_VERSION is set, that version string is compared against a local
cache file so operators can force a full re-download by bumping the env var.

Supports both Azure Blob Storage (primary) and Railway S3 (legacy fallback).
Set AZURE_STORAGE_CONNECTION_STRING to use Azure, or RAILWAY_STORAGE_* vars for S3.
"""

import os
import sys
import shutil


def _clear_model_dir(model_dir: str) -> None:
    """Remove all cached files from *model_dir* without removing the mount root."""
    if not os.path.isdir(model_dir):
        return

    for name in os.listdir(model_dir):
        path = os.path.join(model_dir, name)
        if os.path.isdir(path) and not os.path.islink(path):
            shutil.rmtree(path)
        else:
            os.unlink(path)


def _check_disk_space(model_dir: str, min_gb: float = 2.0) -> None:
    """Fail fast if insufficient disk space for model download."""
    try:
        stat = shutil.disk_usage(model_dir)
        free_gb = stat.free / (1024**3)
        if free_gb < min_gb:
            print(
                f"[download_models] ERROR: Only {free_gb:.1f} GB free at {model_dir}, "
                f"need at least {min_gb} GB. Aborting download."
            )
            sys.exit(1)
    except OSError:
        pass


def _download_from_azure(model_dir: str, connection_string: str, container_name: str) -> int:
    """Download models from Azure Blob Storage. Returns file count."""
    from azure.storage.blob import ContainerClient

    client = ContainerClient.from_connection_string(connection_string, container_name)
    total = 0

    blob_list = list(client.list_blobs())
    print(f"[download_models] Found {len(blob_list)} blobs in container '{container_name}'")

    for blob in blob_list:
        rel_path = blob.name
        if not rel_path or rel_path.endswith("/"):
            continue
        local_path = os.path.join(model_dir, rel_path)
        os.makedirs(os.path.dirname(local_path), exist_ok=True)

        blob_client = client.get_blob_client(blob.name)
        with open(local_path, "wb") as f:
            stream = blob_client.download_blob()
            stream.readinto(f)

        total += 1
        if total % 100 == 0:
            print(f"[download_models] Downloaded {total}/{len(blob_list)} files...")

    return total


def _download_from_s3(model_dir: str) -> int:
    """Legacy Railway S3 download. Returns file count."""
    import boto3
    from botocore.config import Config

    bucket_name = os.environ["RAILWAY_STORAGE_BUCKET_NAME"]
    endpoint = os.environ["RAILWAY_STORAGE_API_URL"]
    access_key = os.environ["RAILWAY_STORAGE_ACCESS_KEY_ID"]
    secret_key = os.environ["RAILWAY_STORAGE_ACCESS_KEY"]

    s3 = boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        config=Config(signature_version="s3v4"),
        region_name="auto",
    )

    paginator = s3.get_paginator("list_objects_v2")
    prefix = "XGB_Models/"
    total = 0

    for page in paginator.paginate(Bucket=bucket_name, Prefix=prefix):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            rel_path = key[len(prefix):]
            if not rel_path:
                continue
            local_path = os.path.join(model_dir, rel_path)
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            s3.download_file(bucket_name, key, local_path)
            total += 1
            if total % 100 == 0:
                print(f"[download_models] Downloaded {total} files...")

    return total


def download_models():
    model_dir = os.environ.get("MODEL_DIR", "/models")
    bundle_version = os.environ.get("MODEL_BUNDLE_VERSION")

    azure_conn_str = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
    azure_container = os.environ.get("AZURE_STORAGE_CONTAINER_NAME", "xgb-models")

    railway_bucket = os.environ.get("RAILWAY_STORAGE_BUCKET_NAME")
    railway_endpoint = os.environ.get("RAILWAY_STORAGE_API_URL")
    railway_access = os.environ.get("RAILWAY_STORAGE_ACCESS_KEY_ID")
    railway_secret = os.environ.get("RAILWAY_STORAGE_ACCESS_KEY")

    use_azure = bool(azure_conn_str)
    use_railway = all([railway_bucket, railway_endpoint, railway_access, railway_secret])

    if not use_azure and not use_railway:
        if os.environ.get("WEBSITE_SITE_NAME"):
            print("[download_models] ERROR: Running on Azure but no storage credentials set!")
            sys.exit(1)
        print("[download_models] No storage credentials set, skipping download.")
        return

    marker = os.path.join(model_dir, ".models_downloaded")
    version_file = os.path.join(model_dir, ".models_version")
    current_version = None
    if os.path.exists(version_file):
        with open(version_file) as f:
            current_version = f.read().strip() or None

    if bundle_version:
        if current_version == bundle_version:
            print(
                "[download_models] Models already present at "
                f"{model_dir} for version '{bundle_version}', skipping."
            )
            return
    elif os.path.exists(marker):
        print(f"[download_models] Models already present at {model_dir}, skipping.")
        return

    os.makedirs(model_dir, exist_ok=True)
    _check_disk_space(model_dir)

    if bundle_version:
        print(
            "[download_models] Local model version "
            f"{current_version or 'missing'} != desired {bundle_version}; "
            "clearing cache before full download."
        )
        _clear_model_dir(model_dir)

    source = "Azure Blob Storage" if use_azure else "Railway S3"
    print(f"[download_models] Downloading models from {source} to {model_dir}...")

    if use_azure:
        total = _download_from_azure(model_dir, azure_conn_str, azure_container)
    else:
        total = _download_from_s3(model_dir)

    if total < 100:
        print(
            f"[download_models] WARNING: Only downloaded {total} files. "
            "Expected ~4000+. Model set may be incomplete."
        )

    with open(marker, "w") as f:
        f.write("ok")
    if bundle_version:
        with open(version_file, "w") as f:
            f.write(bundle_version)

    print(f"[download_models] Done. Downloaded {total} files from {source}.")


if __name__ == "__main__":
    download_models()
