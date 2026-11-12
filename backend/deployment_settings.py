"""Portable runtime settings. Reading settings never contacts a cloud provider."""

import os
from dataclasses import dataclass, field
from pathlib import Path


def enabled(name, default=False):
    return os.getenv(name, str(default)).lower() in {"1", "true", "yes"}


@dataclass(frozen=True)
class RuntimeSettings:
    production: bool = field(default_factory=lambda: os.getenv("ENVIRONMENT", "local") == "production")
    username: str = field(default_factory=lambda: os.getenv("API_USERNAME", "myusername"), repr=False)
    password: str = field(default_factory=lambda: os.getenv("API_PASSWORD", "mypassword"), repr=False)
    queued: bool = field(default_factory=lambda: enabled("JOB_QUEUE_ENABLED"))
    state_dir: Path = field(default_factory=lambda: Path(os.getenv("STATE_DIR", "./state")).resolve())
    artifact_dir: Path = field(default_factory=lambda: Path(os.getenv("ARTIFACT_DIR", "./artifacts")).resolve())
    capacity: int = field(default_factory=lambda: int(os.getenv("JOB_QUEUE_CAPACITY", "4")))
    job_timeout: int = field(default_factory=lambda: int(os.getenv("JOB_TIMEOUT_SECONDS", "1800")))
    max_attempts: int = field(default_factory=lambda: int(os.getenv("JOB_MAX_ATTEMPTS", "2")))

    def validate(self):
        if not 1 <= self.capacity <= 32 or not 30 <= self.job_timeout <= 7200 or not 1 <= self.max_attempts <= 3:
            raise ValueError("Invalid queue capacity, timeout or attempt limit")
        if self.production:
            required = ("API_USERNAME", "API_PASSWORD", "MONGO_URI", "CEREBRAS_API_KEY")
            missing = [key for key in required if not os.getenv(key, "").strip()]
            if missing:
                raise ValueError("Missing production settings: " + ", ".join(missing))
            if self.username == "myusername" or self.password == "mypassword" or len(self.password) < 20:
                raise ValueError("Production requires a non-default API username and password of at least 20 characters")
            if not self.queued:
                raise ValueError("Production requires JOB_QUEUE_ENABLED=true")
            if os.getenv("CUDA_VISIBLE_DEVICES", "") not in {"", "-1"}:
                raise ValueError("CPU deployment must hide CUDA devices")
            if os.getenv("AVATAR_MODE", "static") not in {"static", "wav2lip"}:
                raise ValueError("AVATAR_MODE must be static or wav2lip")
        backend = os.getenv("ARTIFACT_BACKEND", "local")
        if backend not in {"local", "oci"}:
            raise ValueError("ARTIFACT_BACKEND must be local or oci")
        if backend == "oci" and not enabled("OCI_STORAGE_APPROVED"):
            raise ValueError("OCI storage requires explicit eligibility verification and OCI_STORAGE_APPROVED=true")
        return self


def redact_secrets(value):
    """Remove runtime secret values before writing checkpoint errors/events."""
    text = str(value)
    for name, secret in os.environ.items():
        if any(part in name.upper() for part in ("PASSWORD", "TOKEN", "API_KEY", "MONGO_URI", "PRIVATE_KEY")) and len(secret) >= 4:
            text = text.replace(secret, "[redacted]")
    return text
