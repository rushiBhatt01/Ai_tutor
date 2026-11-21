from fastapi import FastAPI, HTTPException, Request, Depends, Header
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from functions.pipeline.cache_utils import find_cached_video, list_all_cached_videos
from functions.pipeline.checkpoint_manager import load_checkpoint, get_run_dir, acquire_lock, release_lock
from functions.pipeline.dag_evaluator import evaluate_run_dag
from media_store import stream_chunks
from bson import ObjectId
import os
import json
import asyncio
import uuid
import base64
import binascii
import secrets
import time
from starlette.concurrency import run_in_threadpool
from dotenv import load_dotenv

# Load environment variables
base_dir = os.path.dirname(__file__)
load_dotenv(os.path.join(base_dir, ".env"))

from deployment_settings import RuntimeSettings
from jobs_api import router as jobs_router, submit_lesson

settings = RuntimeSettings().validate()
app = FastAPI(title="AI Video Tutorial Generator API",
              openapi_url=None if settings.production else "/openapi.json")
app.include_router(jobs_router)
security = HTTPBasic()


async def video_main(*args, **kwargs):
    # Keep the API process light; torch/Manim load only in the rendering process.
    from functions.pipeline.video_main_function import video_main as generate
    return await generate(*args, **kwargs)


@app.middleware("http")
async def production_boundary(request: Request, call_next):
    if settings.production:
        if request.url.path.startswith("/api/dev/"):
            return JSONResponse({"detail": "Not found"}, status_code=404)
        if request.url.path not in {"/healthz", "/readyz"}:
            valid = False
            try:
                scheme, token = request.headers.get("authorization", "").split(" ", 1)
                username, password = base64.b64decode(token, validate=True).decode("utf-8").split(":", 1)
                valid = (scheme.lower() == "basic" and
                    secrets.compare_digest(username.encode(), settings.username.encode()) and
                    secrets.compare_digest(password.encode(), settings.password.encode()))
            except (ValueError, UnicodeError, binascii.Error):
                pass
            if not valid:
                return JSONResponse({"detail": "Authentication required"}, status_code=401,
                                    headers={"WWW-Authenticate": 'Basic realm="AI Tutor"'})
    return await call_next(request)


@app.get("/healthz")
def health():
    return {"status": "ok"}


@app.get("/readyz")
async def readiness():
    if not settings.queued:
        return {"status": "ok", "queue": "disabled"}
    try:
        heartbeat = settings.state_dir / "worker.heartbeat"
        if time.time() - heartbeat.stat().st_mtime > 30:
            raise RuntimeError("worker not ready")
        from db import get_db
        await get_db().command("ping")
        return {"status": "ok", "queue": "ready"}
    except Exception:
        return JSONResponse({"status": "unavailable"}, status_code=503)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[s.strip() for s in os.getenv("CORS_ORIGINS", "" if settings.production else "*").split(",") if s.strip()],
    allow_credentials=settings.production,
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
    if not x_dev_token or not secrets.compare_digest(x_dev_token, expected_token):
        raise HTTPException(status_code=403, detail="Developer access denied: invalid X-Dev-Token")
    return True

# ── Standard Pipeline Endpoint ───────────────────────────────────────────────

@app.post("/videoCreate")
async def create_insights(request: Request, credentials: HTTPBasicCredentials = Depends(security)):
    if (not secrets.compare_digest(credentials.username.encode(), settings.username.encode()) or
            not secrets.compare_digest(credentials.password.encode(), settings.password.encode())):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    data = await request.json()
    if settings.queued:
        result = await run_in_threadpool(submit_lesson, data, request.headers.get("Idempotency-Key"))
        return JSONResponse(result, status_code=202)
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
        cached = find_cached_video(topic_name)
        return cached
    except Exception as e:
        return {"exists": False, "error": str(e)}

@app.get("/prevVideos")
@app.get("/api/videos/list")
async def list_previous_videos():
    try:
        videos = list_all_cached_videos()
        return {"status": "SUCCESS", "count": len(videos), "videos": videos}
    except Exception as e:
        return {"status": "ERROR", "error": str(e), "videos": []}

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
    if settings.queued:
        from jobs_api import retry_job
        return JSONResponse(await run_in_threadpool(retry_job, run_id), status_code=202)
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
    from functions.script.create_script_function import create_script
    data = await request.json()
    topic = data.get("topic", "Quantum Computing")
    level = data.get("level", "intermediate")
    script = create_script(topic, level, 18, 8, 6, "Benjamin")
    return {"module": "script", "topic": topic, "output_script": script}

@app.post("/api/dev/modules/speech/test")
async def dev_test_speech(request: Request, authorized: bool = Depends(verify_dev_token)):
    from functions.audio.create_speech_function import create_speech
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
    from functions.image.get_image_function import get_image
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
    from functions.audio.create_speech_function import create_speech
    from functions.video.create_video_from_audio_function import create_video_from_audio
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


@app.post("/api/dev/modules/manim/test")
async def dev_test_manim(request: Request, authorized: bool = Depends(verify_dev_token)):
    from functions.video.manim_renderer import render_scene_manim
    data = await request.json() if request.headers.get("content-type") == "application/json" else {}
    topic_type = data.get("topic_type", "bfs")
    scene_title = data.get("scene_title", "BFS Traversal Demo")
    steps = data.get("steps", ["A", "B", "C", "D", "E"])

    temp_dir = os.path.join("runs", "dev_sandbox", f"manim_{uuid.uuid4().hex[:8]}")
    os.makedirs(os.path.join(temp_dir, "audio"), exist_ok=True)

    spec = {
        "topic_type": topic_type,
        "scene_title": scene_title,
        "steps": steps,
        "params": data.get("params", {})
    }

    video_path = render_scene_manim(spec, "seg_0", temp_dir)
    return {
        "module": "manim",
        "topic_type": topic_type,
        "video_path": video_path,
        "exists": os.path.exists(video_path),
        "file_size": os.path.getsize(video_path) if os.path.exists(video_path) else 0
    }


