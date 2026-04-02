#!/usr/bin/env python3
"""Upload XGBoost model directories to Railway Storage Bucket.

Mirrors the local XGB_Models/{dir}/ structure into the bucket under the
same XGB_Models/ prefix that download_models.py expects.

Usage:
    # Upload specific directories (most common)
    python3 scripts/upload_models.py ComStock_EndUse ResStock_EndUse

    # Upload everything
    python3 scripts/upload_models.py --all

    # Dry run (list what would be uploaded)
    python3 scripts/upload_models.py ComStock_EndUse --dry-run

Reads credentials from backend/.env (RAILWAY_STORAGE_*).
"""
import os
import sys
import argparse
from pathlib import Path

import boto3
from botocore.config import Config
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MODELS_ROOT = PROJECT_ROOT / "XGB_Models"


def load_credentials():
    load_dotenv(PROJECT_ROOT / "backend" / ".env")
    creds = {
        "endpoint": os.environ.get("RAILWAY_STORAGE_API_URL"),
        "bucket": os.environ.get("RAILWAY_STORAGE_BUCKET_NAME"),
        "access_key": os.environ.get("RAILWAY_STORAGE_ACCESS_KEY_ID"),
        "secret_key": os.environ.get("RAILWAY_STORAGE_ACCESS_KEY"),
    }
    missing = [k for k, v in creds.items() if not v]
    if missing:
        print(f"ERROR: Missing env vars: {missing}", file=sys.stderr)
        sys.exit(1)
    return creds


def get_s3_client(creds):
    return boto3.client(
        "s3",
        endpoint_url=creds["endpoint"],
        aws_access_key_id=creds["access_key"],
        aws_secret_access_key=creds["secret_key"],
        config=Config(signature_version="s3v4"),
        region_name="auto",
    )


def upload_directory(s3, bucket, local_dir, dry_run=False):
    """Upload all files in local_dir to bucket under XGB_Models/{dir_name}/."""
    local_path = Path(local_dir)
    dir_name = local_path.name
    uploaded = 0
    skipped_dirs = {"__pycache__", ".DS_Store"}

    for file_path in sorted(local_path.rglob("*")):
        if file_path.is_dir():
            continue
        if file_path.name in skipped_dirs or file_path.name.startswith("."):
            continue

        rel = file_path.relative_to(local_path)
        s3_key = f"XGB_Models/{dir_name}/{rel}"

        if dry_run:
            size_kb = file_path.stat().st_size / 1024
            print(f"  [dry-run] {s3_key} ({size_kb:.0f} KB)")
        else:
            s3.upload_file(str(file_path), bucket, s3_key)
            uploaded += 1
            if uploaded % 20 == 0:
                print(f"  Uploaded {uploaded} files...")

    return uploaded


def main():
    parser = argparse.ArgumentParser(description="Upload model directories to Railway bucket")
    parser.add_argument("dirs", nargs="*", help="Directory names under XGB_Models/ to upload")
    parser.add_argument("--all", action="store_true", help="Upload all model directories")
    parser.add_argument("--dry-run", action="store_true", help="List files without uploading")
    args = parser.parse_args()

    if not args.dirs and not args.all:
        parser.error("Specify directory names or --all")

    if args.all:
        dirs = [d for d in MODELS_ROOT.iterdir()
                if d.is_dir() and not d.name.startswith((".", "archive"))]
    else:
        dirs = []
        for name in args.dirs:
            d = MODELS_ROOT / name
            if not d.is_dir():
                print(f"ERROR: {d} is not a directory", file=sys.stderr)
                sys.exit(1)
            dirs.append(d)

    creds = load_credentials()
    s3 = get_s3_client(creds)

    total = 0
    for d in sorted(dirs):
        print(f"\n{'[dry-run] ' if args.dry_run else ''}Uploading {d.name}/...")
        count = upload_directory(s3, creds["bucket"], d, dry_run=args.dry_run)
        total += count
        if not args.dry_run:
            print(f"  {d.name}: {count} files uploaded")

    if args.dry_run:
        print(f"\nDry run complete. Would upload files from {len(dirs)} directories.")
    else:
        print(f"\nDone. Uploaded {total} files from {len(dirs)} directories.")


if __name__ == "__main__":
    main()
