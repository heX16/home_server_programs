from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from system_info import get_system_status, get_disk_info

app = FastAPI()

app.mount("/static", StaticFiles(directory="."), name="static")

@app.get("/")
async def read_index():
    return FileResponse("index.html")

@app.get("/api/system_status")
def system_status():
    return get_system_status()

@app.get("/api/disk")
def disk_info():
    return get_disk_info()
