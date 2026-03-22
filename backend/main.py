from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from functions.video_main_function import video_main
from media_store import stream_chunks
from bson import ObjectId

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
    file_id = await video_main(message, level, age, creative, humour, characterName)
    
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
