import os
from typing import Dict, Optional
from bson import ObjectId
from db import get_bucket, get_db


async def upload_file(path: str, filename: Optional[str] = None, metadata: Optional[Dict] = None) -> ObjectId:
    bucket = get_bucket()
    fname = filename or os.path.basename(path)
    meta = metadata or {}
    with open(path, "rb") as f:
        file_id = await bucket.upload_from_stream(fname, f, metadata=meta)
    return file_id


async def upload_bytes(data: bytes, filename: str, metadata: Optional[Dict] = None) -> ObjectId:
    bucket = get_bucket()
    meta = metadata or {}
    file_id = await bucket.upload_from_stream(filename, data, metadata=meta)
    return file_id


async def list_files_by_meta(query: Dict):
    db = get_db()
    return db.fs.files.find(query)


async def open_download_stream(file_id: ObjectId):
    bucket = get_bucket()
    return await bucket.open_download_stream(file_id)


async def stream_chunks(file_id: ObjectId, chunk_size: int = 1024 * 256):
    grid_out = await open_download_stream(file_id)
    while True:
        chunk = await grid_out.readchunk()
        if not chunk:
            break
        yield chunk
