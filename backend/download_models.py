"""Download XGBoost models from Railway Storage Bucket to local volume.

Runs once on container startup. Skips if models are already present.
"""

import os
import sys
import boto3
from botocore.config import Config


def download_models():
    model_dir = os.environ.get("MODEL_DIR", "/models")
    bucket_name = os.environ.get("RAILWAY_STORAGE_BUCKET_NAME")
    endpoint = os.environ.get("RAILWAY_STORAGE_API_URL")
    access_key = os.environ.get("RAILWAY_STORAGE_ACCESS_KEY_ID")
    secret_key = os.environ.get("RAILWAY_STORAGE_ACCESS_KEY")

    if not all([bucket_name, endpoint, access_key, secret_key]):
        print("[download_models] Bucket credentials not set, skipping download.")
        return

    # Check if models already exist on the volume
    marker = os.path.join(model_dir, ".models_downloaded")
    if os.path.exists(marker):
        print(f"[download_models] Models already present at {model_dir}, skipping.")
        return

    os.makedirs(model_dir, exist_ok=True)

    print(f"[download_models] Downloading models from bucket '{bucket_name}' to {model_dir}...")

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
            # Strip the bucket prefix to get relative path
            rel_path = key[len(prefix):]
            if not rel_path:
                continue
            local_path = os.path.join(model_dir, rel_path)
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            s3.download_file(bucket_name, key, local_path)
            total += 1
            if total % 100 == 0:
                print(f"[download_models] Downloaded {total} files...")

    # Write marker so we skip on next restart
    with open(marker, "w") as f:
        f.write("ok")

    print(f"[download_models] Done. Downloaded {total} files.")


if __name__ == "__main__":
    download_models()
