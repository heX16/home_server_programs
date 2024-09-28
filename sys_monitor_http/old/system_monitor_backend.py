import psutil
import time
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI()

# Serve static files
app.mount("/static", StaticFiles(directory="."), name="static")

@app.get("/")
async def read_index():
    return FileResponse("index.html")

@app.get("/api/system_status")
def get_system_status():
    memory = psutil.virtual_memory()
    cpu_percent = psutil.cpu_percent(interval=1)

    return {
        'cpu': {
            'usage': cpu_percent,
            'cores': psutil.cpu_count()
        },
        'memory': {
            'total': memory.total,
            'available': memory.available,
            'used': memory.used,
            'percent': memory.percent
        },
        'uptime': {
            'system': time.time() - psutil.boot_time()
        }
    }

@app.get("/api/disk")
def get_disk_info():
    partitions = psutil.disk_partitions()
    return [{
        'device': partition.device,
        'mountpoint': partition.mountpoint,
        'fstype': partition.fstype,
        # usage: {
        #    total: 21378641920,
        #    used: 4809781248,
        #    free: 15482871808,
        #    percent: 22.5 }
        'usage': psutil.disk_usage(partition.mountpoint)._asdict()
    } for partition in partitions]
