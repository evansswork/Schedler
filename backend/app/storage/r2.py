from pathlib import Path
from typing import Any, Self

import boto3
from botocore.config import Config

from app.core.config import Settings


class R2Storage:
    """Cloudflare R2 (S3-compatible). Objects are public through the bucket's public URL."""

    def __init__(self, client: Any, bucket: str, public_base_url: str) -> None:
        self.client = client
        self.bucket = bucket
        self.public_base_url = public_base_url.rstrip("/")

    @classmethod
    def from_settings(cls, s: Settings) -> Self:
        client = boto3.client(
            "s3",
            endpoint_url=f"https://{s.r2_account_id}.r2.cloudflarestorage.com",
            aws_access_key_id=s.r2_access_key_id,
            aws_secret_access_key=s.r2_secret_access_key,
            region_name="auto",
            # Cloudflare's guidance for boto3 >= 1.36: only send checksums when required.
            config=Config(
                request_checksum_calculation="when_required",
                response_checksum_validation="when_required",
                retries={"max_attempts": 3, "mode": "standard"},
            ),
        )
        return cls(client, s.r2_bucket, s.r2_public_base_url)

    def put(self, local_path: Path, key: str) -> str:
        with local_path.open("rb") as body:
            self.client.put_object(Bucket=self.bucket, Key=key, Body=body, ContentType="video/mp4")
        local_path.unlink()
        return f"{self.public_base_url}/{key}"

    def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=key)
