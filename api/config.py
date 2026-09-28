"""Runtime settings. Everything comes from the environment; see .env.example."""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class Settings:
    database_url: str = "postgresql+psycopg://vibo:vibo@localhost:5432/vibo"
    redis_url: str = "redis://localhost:6379/0"
    storage: str = "local"                  # local | s3
    media_dir: str = "./media"              # local storage root
    api_base: str = "http://localhost:8000" # used to build presigned/public URLs for local storage
    upload_secret: str = "dev-upload-secret"
    upload_ttl_s: int = 15 * 60
    s3_bucket: str = ""
    s3_region: str = "us-east-1"
    cdn_base: str = ""                      # e.g. https://dxxxx.cloudfront.net
    candidates: int = 250                   # retrieval size handed to the ranker
    seed_sample_url: str = "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerBlazes.mp4"

    @classmethod
    def from_env(cls) -> "Settings":
        d = cls()
        for f in d.__dataclass_fields__:
            raw = os.environ.get(f.upper())
            if raw is not None:
                setattr(d, f, type(getattr(d, f))(raw))
        return d
