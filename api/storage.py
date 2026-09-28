"""Object storage behind one interface. LocalStorage for dev (a folder served by the API), S3Storage for prod."""
from __future__ import annotations

import hashlib
import hmac
import time
from pathlib import Path
from typing import Protocol


class Storage(Protocol):
    def presigned_upload(self, key: str, content_type: str) -> str: ...
    def public_url(self, key: str) -> str: ...


class LocalStorage:
    """Files live under `root`. The 'presigned URL' is a PUT to this API with an HMAC token."""

    def __init__(self, root: str | Path, api_base: str, secret: str, ttl_s: int = 900):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.api_base = api_base.rstrip("/")
        self.secret = secret.encode()
        self.ttl_s = ttl_s

    def _sign(self, key: str, expires: int) -> str:
        return hmac.new(self.secret, f"{key}:{expires}".encode(), hashlib.sha256).hexdigest()[:32]

    def presigned_upload(self, key: str, content_type: str) -> str:
        expires = int(time.time()) + self.ttl_s
        return f"{self.api_base}/uploads/{key}?token={self._sign(key, expires)}&expires={expires}"

    def public_url(self, key: str) -> str:
        return f"{self.api_base}/media/{key}"

    def verify(self, key: str, token: str, expires: int) -> bool:
        return expires > time.time() and hmac.compare_digest(token, self._sign(key, expires))

    def put(self, key: str, data: bytes) -> Path:
        path = (self.root / key).resolve()
        if self.root.resolve() not in path.parents:
            raise ValueError("key escapes storage root")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path


class S3Storage:
    def __init__(self, bucket: str, region: str, cdn_base: str = "", ttl_s: int = 900):
        import boto3  # only needed when STORAGE=s3

        self.bucket, self.region, self.cdn_base, self.ttl_s = bucket, region, cdn_base.rstrip("/"), ttl_s
        self.client = boto3.client("s3", region_name=region)

    def presigned_upload(self, key: str, content_type: str) -> str:
        return self.client.generate_presigned_url(
            "put_object",
            Params={"Bucket": self.bucket, "Key": key, "ContentType": content_type},
            ExpiresIn=self.ttl_s,
        )

    def public_url(self, key: str) -> str:
        if self.cdn_base:
            return f"{self.cdn_base}/{key}"
        return f"https://{self.bucket}.s3.{self.region}.amazonaws.com/{key}"
