import os
from urllib.parse import urlsplit
from motor.motor_asyncio import AsyncIOMotorClient
from motor.motor_asyncio import AsyncIOMotorGridFSBucket

_client = None
_db = None
_bucket = None


def get_db():
    global _client, _db
    if _db is None:
        uri = os.getenv("MONGO_URI", "mongodb://localhost:27017/video_tutorials")
        _client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=2000)
        db_name = urlsplit(uri).path.strip("/") or os.getenv("MONGO_DATABASE", "video_tutorials")
        _db = _client[db_name]
    return _db


def get_bucket():
    global _bucket
    if _bucket is None:
        _bucket = AsyncIOMotorGridFSBucket(get_db())
    return _bucket



async def set_cached_video(topic: str, file_id):
    try:
        db = get_db()
        await db.video_cache.update_one(
            {"topic": topic},
            {"$set": {"topic": topic, "file_id": file_id}},
            upsert=True,
        )
    except Exception as e:
        print("MongoDB cache write unavailable")

