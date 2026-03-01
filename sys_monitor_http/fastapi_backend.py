from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from system_info import get_system_status, get_disk_info, get_rpi_vcgencmd_available, get_rpi_temperature, get_rpi_throttled

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


@app.get("/api/rpi/vcgencmd_available")
def rpi_vcgencmd_available():
    return get_rpi_vcgencmd_available()


@app.get("/api/rpi/temperature")
def rpi_temperature():
    return get_rpi_temperature()


@app.get("/api/rpi/throttled")
def rpi_throttled():
    return get_rpi_throttled()
