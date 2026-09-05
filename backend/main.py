from fastapi import FastAPI, HTTPException, Request, Depends, Header
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from functions.video_main_function import video_main
from functions.checkpoint_manager import load_checkpoint, get_run_dir, acquire_lock, release_lock
from functions.dag_evaluator import evaluate_run_dag
from functions.create_script_function import create_script
from functions.create_speech_function import create_speech
from functions.get_image_function import get_image
from functions.generate_queries_function import generate_image_queries
from functions.create_video_from_audio_function import create_video_from_audio
from functions.create_image_videos_function import create_image_videos
from functions.combine_videos_function import combine_videos
from media_store import stream_chunks
from bson import ObjectId
import os
import json
import asyncio
import uuid
from dotenv import load_dotenv

# Load environment variables
base_dir = os.path.dirname(__file__)
load_dotenv(os.path.join(base_dir, ".env"))

app = FastAPI(title="AI Video Tutorial Generator API")
security = HTTPBasic()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def verify_dev_token(x_dev_token: str = Header(None)):
    """Simple RBAC check for developer sandbox endpoints."""
    # In local dev environment, allow access if token matches or dev mode enabled
    expected_token = os.getenv("DEV_API_TOKEN", "dev-secret-token")
    env = os.getenv("ENVIRONMENT", "local")
    if env == "local":
        return True
    if x_dev_token != expected_token:
        raise HTTPException(status_code=403, detail="Developer access denied: invalid X-Dev-Token")
    return True

# ── Standard Pipeline Endpoint ───────────────────────────────────────────────

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
    pipeline_delay_ms = data.get("pipelineDelayMs")
    run_id = data.get("runId")
    
    file_id = await video_main(message, level, age, creative, humour, characterName, pipeline_delay_ms, run_id=run_id)
    
    headers = {"Content-Disposition": f"inline; filename={message}.mp4"}

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
        return {"exists": False, "error": str(e)}

# ── Universal Pipeline Recovery API ───────────────────────────────────────────

@app.get("/api/pipeline/runs/{run_id}/status")
async def get_run_status(run_id: str):
    cp = load_checkpoint(run_id)
    if not cp:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    
    earliest_stage, report = evaluate_run_dag(run_id)
    return {
        "checkpoint": cp,
        "earliest_recovery_stage": earliest_stage,
        "integrity_report": report
    }

@app.post("/api/pipeline/runs/{run_id}/resume")
async def resume_pipeline_run(run_id: str, request: Request):
    cp = load_checkpoint(run_id)
    if not cp:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    
    data = await request.json() if request.headers.get("content-type") == "application/json" else {}
    force_cpu = data.get("force_cpu", False)
    
    if not acquire_lock(run_id):
        raise HTTPException(status_code=409, detail="Run is currently locked/executing. Please wait.")
    
    release_lock(run_id)  # Lock re-acquired inside video_main execution
    
    earliest_stage, report = evaluate_run_dag(run_id)
    topic = cp.get("topic", "Tutorial")
    
    file_id = await video_main(
        topic_name=topic,
        level_of_explanation="Intermediate",
        age="18",
        creativity_level="High",
        humour_level="Medium",
        character_name="Benjamin",
        run_id=run_id,
        start_stage=earliest_stage,
        force_cpu=force_cpu
    )
    
    return {"status": "SUCCESS", "run_id": run_id, "file_id": str(file_id)}

@app.get("/api/pipeline/runs/{run_id}/events")
async def stream_run_events(run_id: str):
    """Server-Sent Events (SSE) telemetry stream for real-time logs & progress."""
    run_dir = get_run_dir(run_id)
    log_file = os.path.join(run_dir, "logs", "events.jsonl")
    
    async def event_generator():
        last_pos = 0
        while True:
            if os.path.exists(log_file):
                with open(log_file, "r", encoding="utf-8") as f:
                    f.seek(last_pos)
                    lines = f.readlines()
                    last_pos = f.tell()
                    for line in lines:
                        if line.strip():
                            yield f"event: pipeline_event\ndata: {line.strip()}\n\n"
            await asyncio.sleep(1)
            
    return StreamingResponse(event_generator(), media_type="text/event-stream")

# ── Developer Sandbox Module Testing APIs ──────────────────────────────────────

@app.post("/api/dev/modules/script/test")
async def dev_test_script(request: Request, authorized: bool = Depends(verify_dev_token)):
    data = await request.json()
    topic = data.get("topic", "Quantum Computing")
    level = data.get("level", "intermediate")
    script = create_script(topic, level, 18, 8, 6, "Benjamin")
    return {"module": "script", "topic": topic, "output_script": script}

@app.post("/api/dev/modules/speech/test")
async def dev_test_speech(request: Request, authorized: bool = Depends(verify_dev_token)):
    data = await request.json()
    text = data.get("text", "Hello, welcome to this tutorial.")
    character = data.get("character", "Benjamin")
    
    temp_dir = os.path.join("runs", "dev_sandbox", uuid.uuid4().hex[:8])
    os.makedirs(temp_dir, exist_ok=True)
    audio_path = os.path.join(temp_dir, "sample.wav")
    
    voice_map = {'Benjamin': "en-IE-ConnorNeural", 'Sophia': 'ar-SA-ZariyahNeural'}
    create_speech(text, audio_path, voice_map.get(character, "en-IE-ConnorNeural"))
    
    return {"module": "speech", "text": text, "audio_file": audio_path, "size_bytes": os.path.getsize(audio_path)}

@app.post("/api/dev/modules/scrapling/test")
async def dev_test_scrapling(request: Request, authorized: bool = Depends(verify_dev_token)):
    data = await request.json()
    query = data.get("query", "Python Programming Logo")
    
    temp_dir = os.path.join("runs", "dev_sandbox", uuid.uuid4().hex[:8])
    os.makedirs(temp_dir, exist_ok=True)
    
    chunk_queries = [{"chunk_id": "seg_dev", "query": query}]
    saved_images = get_image(chunk_queries, temp_dir)
    
    return {"module": "scrapling", "query": query, "output_images": saved_images}

@app.post("/api/dev/modules/wav2lip/test")
@app.post("/api/dev/modules/sadtalker/test")
async def dev_test_wav2lip(request: Request, authorized: bool = Depends(verify_dev_token)):
    data = await request.json()
    character = data.get("character", "Benjamin")
    force_cpu = data.get("force_cpu", False)
    
    # Run test on dev sandbox directory
    dev_dir = os.path.join("runs", "dev_sandbox", "sample_run")
    if not os.path.exists(os.path.join(dev_dir, "audio", "seg_000.wav")):
        os.makedirs(os.path.join(dev_dir, "audio"), exist_ok=True)
        create_speech("This is a developer sandbox test for Wav2Lip lip sync animation.", os.path.join(dev_dir, "audio", "seg_000.wav"), "en-IE-ConnorNeural")
        
    results = create_video_from_audio(dev_dir, character, cpu_mode=force_cpu)
    return {"module": "wav2lip", "results": results, "force_cpu": force_cpu}

