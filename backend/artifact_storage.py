"""Generic artifact storage with local and opt-in private OCI adapters."""

import os
import shutil
from abc import ABC, abstractmethod
from pathlib import Path, PurePosixPath
from tempfile import NamedTemporaryFile


def checked_key(key):
    path = PurePosixPath(key)
    if not key or path.is_absolute() or "\\" in key or any(part in {"", ".", ".."} for part in key.split("/")):
        raise ValueError("Invalid artifact object key")
    return str(path)


class ArtifactStorage(ABC):
    @abstractmethod
    def upload_file(self, local_path: str, object_key: str) -> str: ...

    @abstractmethod
    def download_file(self, object_key: str, local_path: str) -> None: ...

    @abstractmethod
    def delete_file(self, object_key: str) -> None: ...


def atomic_copy(source, target):
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(dir=target.parent, delete=False) as stream:
        temp = Path(stream.name)
    try:
        shutil.copyfile(source, temp)
        os.replace(temp, target)
    finally:
        temp.unlink(missing_ok=True)


class LocalArtifactStorage(ArtifactStorage):
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def path(self, key):
        result = (self.root / checked_key(key)).resolve()
        if not result.is_relative_to(self.root):
            raise ValueError("Artifact escapes storage root")
        return result

    def upload_file(self, local_path, object_key):
        destination = self.path(object_key)
        atomic_copy(local_path, destination)
        return destination.as_uri()

    def download_file(self, object_key, local_path):
        atomic_copy(self.path(object_key), local_path)

    def delete_file(self, object_key):
        self.path(object_key).unlink(missing_ok=True)


class OCIArtifactStorage(ArtifactStorage):
    """All OCI SDK types remain inside this adapter; no public buckets/PARs."""

    def __init__(self, client, namespace, bucket):
        self.client, self.namespace, self.bucket = client, namespace, bucket

    def upload_file(self, local_path, object_key):
        key = checked_key(object_key)
        with open(local_path, "rb") as stream:
            self.client.put_object(self.namespace, self.bucket, key, stream)
        return f"oci://{self.namespace}/{self.bucket}/{key}"

    def download_file(self, object_key, local_path):
        response = self.client.get_object(self.namespace, self.bucket, checked_key(object_key))
        target = Path(local_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile(dir=target.parent, delete=False) as stream:
            temp = Path(stream.name)
            try:
                for chunk in response.data.raw.stream(1024 * 1024, decode_content=False):
                    stream.write(chunk)
            except BaseException:
                stream.close()
                temp.unlink(missing_ok=True)
                raise
            finally:
                response.data.close()
        try:
            os.replace(temp, target)
        finally:
            temp.unlink(missing_ok=True)

    def delete_file(self, object_key):
        self.client.delete_object(self.namespace, self.bucket, checked_key(object_key))


def get_artifact_storage():
    from deployment_settings import RuntimeSettings, enabled
    settings = RuntimeSettings().validate()
    if os.getenv("ARTIFACT_BACKEND", "local") == "local":
        return LocalArtifactStorage(settings.artifact_dir)
    if not enabled("OCI_STORAGE_APPROVED"):
        raise ValueError("OCI storage is not approved")
    # Imported only for explicit OCI use. Local operation needs no OCI SDK.
    import oci
    namespace, bucket = os.getenv("OCI_STORAGE_NAMESPACE"), os.getenv("OCI_STORAGE_BUCKET")
    if not namespace or not bucket:
        raise ValueError("OCI_STORAGE_NAMESPACE and OCI_STORAGE_BUCKET are required")
    signer = oci.auth.signers.InstancePrincipalsSecurityTokenSigner()
    client = oci.object_storage.ObjectStorageClient({}, signer=signer, timeout=(10, 60),
        retry_strategy=oci.retry.RetryStrategyBuilder(max_attempts=3, total_elapsed_time_seconds=120).get_retry_strategy())
    return OCIArtifactStorage(client, namespace, bucket)
