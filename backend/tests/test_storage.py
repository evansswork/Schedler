from pathlib import Path

import boto3
from botocore.stub import ANY, Stubber
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.storage import LocalPublicStorage, get_storage
from app.storage.r2 import R2Storage


def _file(tmp_path: Path) -> Path:
    f = tmp_path / "incoming.mp4"
    f.write_bytes(b"\x00\x00\x00\x18ftypmp42")
    return f


def test_local_public_put_serves_file_and_delete_removes_it(
    client: TestClient, tmp_path: Path
) -> None:
    storage = get_storage(get_settings())
    assert isinstance(storage, LocalPublicStorage)
    src = _file(tmp_path)
    url = storage.put(src, "tok123.mp4")
    assert url == "http://testserver/m/tok123.mp4"
    assert not src.exists()
    res = client.get("/m/tok123.mp4")
    assert res.status_code == 200
    assert res.headers["content-type"] == "video/mp4"
    storage.delete("tok123.mp4")
    assert client.get("/m/tok123.mp4").status_code == 404


def test_media_dir_listing_and_incoming_files_not_served(client: TestClient) -> None:
    incoming = get_settings().media_dir / "incoming"
    incoming.mkdir(parents=True)
    (incoming / "01ABC.mp4").write_bytes(b"x")
    assert client.get("/m/").status_code == 404
    assert client.get("/m/../incoming/01ABC.mp4").status_code == 404


def test_r2_put_uploads_with_content_type_and_returns_public_url(tmp_path: Path) -> None:
    s3 = boto3.client(
        "s3", region_name="auto", aws_access_key_id="k", aws_secret_access_key="s",
        endpoint_url="https://acc.r2.cloudflarestorage.com",
    )  # fmt: skip
    storage = R2Storage(s3, "schedler-media", "https://pub-abc.r2.dev/")
    src = _file(tmp_path)
    with Stubber(s3) as stub:
        stub.add_response(
            "put_object",
            {},
            {"Bucket": "schedler-media", "Key": "tok.mp4", "Body": ANY, "ContentType": "video/mp4"},
        )
        stub.add_response("delete_object", {}, {"Bucket": "schedler-media", "Key": "tok.mp4"})
        assert storage.put(src, "tok.mp4") == "https://pub-abc.r2.dev/tok.mp4"
        storage.delete("tok.mp4")
        stub.assert_no_pending_responses()
    assert not src.exists()
