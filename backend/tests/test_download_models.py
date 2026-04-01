import importlib.util
from pathlib import Path


def _load_download_models_module():
    module_path = Path(__file__).resolve().parent.parent / "download_models.py"
    spec = importlib.util.spec_from_file_location("download_models_module", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class FakePaginator:
    def __init__(self, pages):
        self.pages = pages

    def paginate(self, **kwargs):
        return self.pages


class FakeS3Client:
    def __init__(self, pages):
        self.pages = pages
        self.downloaded = []

    def get_paginator(self, name):
        assert name == "list_objects_v2"
        return FakePaginator(self.pages)

    def download_file(self, bucket_name, key, local_path):
        Path(local_path).parent.mkdir(parents=True, exist_ok=True)
        Path(local_path).write_text(f"{bucket_name}:{key}")
        self.downloaded.append((bucket_name, key, local_path))


def test_download_models_skips_when_bundle_version_matches(monkeypatch, tmp_path):
    module = _load_download_models_module()

    model_dir = tmp_path / "models"
    model_dir.mkdir()
    (model_dir / ".models_version").write_text("2026-04-01-enduse-v1")

    monkeypatch.setenv("MODEL_DIR", str(model_dir))
    monkeypatch.setenv("MODEL_BUNDLE_VERSION", "2026-04-01-enduse-v1")
    monkeypatch.setenv("RAILWAY_STORAGE_BUCKET_NAME", "bucket")
    monkeypatch.setenv("RAILWAY_STORAGE_API_URL", "https://storage.example.com")
    monkeypatch.setenv("RAILWAY_STORAGE_ACCESS_KEY_ID", "key")
    monkeypatch.setenv("RAILWAY_STORAGE_ACCESS_KEY", "secret")

    called = False

    def fake_client(*args, **kwargs):
        nonlocal called
        called = True
        return FakeS3Client([])

    monkeypatch.setattr(module.boto3, "client", fake_client)

    module.download_models()

    assert called is False
    assert (model_dir / ".models_version").read_text() == "2026-04-01-enduse-v1"


def test_download_models_redownloads_when_bundle_version_changes(monkeypatch, tmp_path):
    module = _load_download_models_module()

    model_dir = tmp_path / "models"
    model_dir.mkdir()
    (model_dir / ".models_version").write_text("2026-03-20-baseline-v3")
    (model_dir / "stale.txt").write_text("stale")

    monkeypatch.setenv("MODEL_DIR", str(model_dir))
    monkeypatch.setenv("MODEL_BUNDLE_VERSION", "2026-04-01-enduse-v1")
    monkeypatch.setenv("RAILWAY_STORAGE_BUCKET_NAME", "bucket")
    monkeypatch.setenv("RAILWAY_STORAGE_API_URL", "https://storage.example.com")
    monkeypatch.setenv("RAILWAY_STORAGE_ACCESS_KEY_ID", "key")
    monkeypatch.setenv("RAILWAY_STORAGE_ACCESS_KEY", "secret")

    fake_s3 = FakeS3Client([
        {
            "Contents": [
                {"Key": "XGB_Models/ComStock_EndUse/XGB_enduse_heating.pkl"},
                {"Key": "XGB_Models/ComStock_EndUse/XGB_enduse_heating_encoders.pkl"},
                {"Key": "XGB_Models/ComStock_EndUse/XGB_enduse_heating_meta.json"},
            ]
        }
    ])
    monkeypatch.setattr(module.boto3, "client", lambda *args, **kwargs: fake_s3)

    module.download_models()

    assert (model_dir / ".models_version").read_text() == "2026-04-01-enduse-v1"
    assert not (model_dir / "stale.txt").exists()
    assert (model_dir / "ComStock_EndUse" / "XGB_enduse_heating.pkl").exists()
    assert len(fake_s3.downloaded) == 3
