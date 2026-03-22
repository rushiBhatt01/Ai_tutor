import os
from motor.motor_asyncio import AsyncIOMotorClient
from motor.motor_asyncio import AsyncIOMotorGridFSBucket

_client = None
_db = None
_bucket = None


def get_db():
    global _client, _db
    if _db is None:
        uri = os.getenv("MONGO_URI", "mongodb://localhost:27017/video_tutorials")
        _client = AsyncIOMotorClient(uri)
        db_name = uri.rsplit("/", 1)[-1]
        _db = _client[db_name]
    return _db


def get_bucket():
    global _bucket
    if _bucket is None:
        _bucket = AsyncIOMotorGridFSBucket(get_db())
    return _bucket


async def get_cached_video(topic: str):
    db = get_db()
    doc = await db.video_cache.find_one({"topic": topic})
    return doc["file_id"] if doc else None


async def set_cached_video(topic: str, file_id):
    db = get_db()
    await db.video_cache.update_one(
        {"topic": topic},
        {"$set": {"topic": topic, "file_id": file_id}},
        upsert=True,
    )
