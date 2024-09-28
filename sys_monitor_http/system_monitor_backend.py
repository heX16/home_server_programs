import psutil
import time
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

app = FastAPI()

# Allow CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

service_start_time = time.time()

app.mount('/static', StaticFiles(directory='static'), name='static')

@app.get('/')
def get_index():
    index_path = Path('static/index.html')
    return index_path.read_text()

@app.get('/api/system_status')
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
            'service': time.time() - service_start_time,
            'system': time.time() - psutil.boot_time()
        }
    }

@app.get('/api/disk')
def get_disk_info():
    partitions = psutil.disk_partitions()
    return [{
        'device': partition.device,
        'mountpoint': partition.mountpoint,
        'fstype': partition.fstype,
        'usage': psutil.disk_usage(partition.mountpoint)._asdict()
    } for partition in partitions]
