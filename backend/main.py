from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from functions.video_main_function import video_main
from media_store import stream_chunks
from bson import ObjectId
import os
from dotenv import load_dotenv

# Load environment variables from backend/.env at startup
base_dir = os.path.dirname(__file__)
load_dotenv(os.path.join(base_dir, ".env"))

app = FastAPI()
security = HTTPBasic()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/videoCreate")
async def create_insights(request: Request, credentials: HTTPBasicCredentials = Depends(security)):
    if credentials.username != "myusername" or credentials.password != "mypassword":
        raise HTTPException(status_code=401, detail="Invalid credentials")
    data = await request.json()
    message = data['message']
    level = data['level']
    age = data['age']
    creative = data['creative']
    humour = data['humour']
    characterName = data['characterName']
    # Optional pipeline delay (ms) sent by frontend: sum of pipeline durations + buffer
    pipeline_delay_ms = data.get("pipelineDelayMs")
    file_id = await video_main(message, level, age, creative, humour, characterName, pipeline_delay_ms)
    
    headers = {
        "Content-Disposition": f"inline; filename={message}.mp4"
    }

    if isinstance(file_id, str) and file_id.startswith("local:"):
        local_path = file_id.split("local:")[1]
        def file_generator():
            with open(local_path, "rb") as f:
                while chunk := f.read(1024 * 256):
                    yield chunk
        return StreamingResponse(file_generator(), media_type="video/mp4", headers=headers)

    oid = ObjectId(str(file_id))
    async def generator():
        async for chunk in stream_chunks(oid):
            yield chunk

    return StreamingResponse(generator(), media_type="video/mp4", headers=headers)


@app.get("/checkVideoCache/{topic_name}")
async def check_video_cache(topic_name: str):
    """
    Check if a cached video exists for the given topic in frontend/public/prev_videos
    Returns: {exists: bool, filename: str}
    """
    try:
        frontend_cache_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../frontend/topic2explanation/public/prev_videos"))
        file_path = os.path.join(frontend_cache_dir, f"{topic_name}.mp4")
        exists = os.path.exists(file_path)
        return {
            "exists": exists,
            "filename": f"{topic_name}.mp4" if exists else None,
            "path": file_path if exists else None
        }
    except Exception as e:
        print(f"Error checking cache for topic '{topic_name}': {e}")
        return {
            "exists": False,
            "error": str(e)
        }
