import hashlib
import shutil
from pathlib import Path
from typing import BinaryIO, Protocol
from uuid import uuid4

from fastapi import HTTPException, UploadFile
from minio import Minio

from slidemind_api.config import Settings


class ObjectStore(Protocol):
    def put(self, key: str, stream: BinaryIO, size: int) -> None: ...
    def delete(self, key: str) -> None: ...
    def get(self, key: str) -> bytes: ...


class LocalStore:
    def __init__(self, root: Path):
        self.root = root.resolve()

    def path(self, key: str) -> Path:
        path = (self.root / key).resolve()
        if not path.is_relative_to(self.root):
            raise ValueError("Storage key escapes root")
        return path

    def put(self, key: str, stream: BinaryIO, size: int) -> None:
        path = self.path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with path.open("xb") as target:
                shutil.copyfileobj(stream, target)
        except Exception:
            path.unlink(missing_ok=True)
            raise

    def delete(self, key: str) -> None:
        self.path(key).unlink(missing_ok=True)

    def get(self, key: str) -> bytes:
        return self.path(key).read_bytes()


class MinioStore:
    def __init__(self, settings: Settings):
        self.bucket = settings.minio_bucket
        self.client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )

    def put(self, key: str, stream: BinaryIO, size: int) -> None:
        # The bucket is provisioned by Compose or by the operator.
        self.client.put_object(self.bucket, key, stream, size)

    def delete(self, key: str) -> None:
        self.client.remove_object(self.bucket, key)

    def get(self, key: str) -> bytes:
        response = self.client.get_object(self.bucket, key)
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()


def inspect_upload(file: UploadFile, extensions: set[str], limit_mb: int) -> dict:
    name = (file.filename or "").replace("\\", "/").rsplit("/", 1)[-1]
    extension = Path(name).suffix.lower().lstrip(".")
    if not name or len(name) > 255 or any(ord(char) < 32 for char in name):
        raise HTTPException(422, "文件名无效")
    if extension not in extensions:
        raise HTTPException(415, "暂不支持此文件类型")
    size = 0
    digest = hashlib.sha256()
    while chunk := file.file.read(1024 * 1024):
        size += len(chunk)
        if size > limit_mb * 1024 * 1024:
            raise HTTPException(413, f"文件不能超过 {limit_mb} MB")
        digest.update(chunk)
    if size == 0:
        raise HTTPException(422, "不能上传空文件")
    file.file.seek(0)
    return dict(file_name=name, file_type=extension, size_bytes=size, sha256=digest.hexdigest())


def object_key(prefix: str, extension: str) -> str:
    return f"{prefix}/{uuid4().hex}.{extension}"
