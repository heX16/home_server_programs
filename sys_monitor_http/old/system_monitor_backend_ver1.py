import psutil
import time
from fastapi import FastAPI

# Create an instance of FastAPI
app = FastAPI()

# Start time to calculate service uptime
service_start_time = time.time()

@app.get('/')
def read_root():
    return {'message': 'System Stats API'}

@app.get('/system_status')
def get_system_status():
    # Get memory info
    memory = psutil.virtual_memory()
    memory_info = {
        'total_memory': memory.total,
        'available_memory': memory.available,
        'used_memory': memory.used,
        'memory_percent': memory.percent
    }

    # Get CPU info
    cpu_info = {
        'cpu_percent': psutil.cpu_percent(interval=1),
        'cpu_count': psutil.cpu_count()
    }

    # Get service uptime
    current_time = time.time()
    service_uptime = current_time - service_start_time

    # Get system (Linux) uptime
    system_uptime = time.time() - psutil.boot_time()

    return {
        'cpu_info': cpu_info,
        'memory_info': memory_info,
        'service_uptime': service_uptime,
        'system_uptime': system_uptime
    }

@app.get('/disk')
def get_disk_info():
    disks_info = []
    partitions = psutil.disk_partitions()

    # Collect information for each disk partition
    for partition in partitions:
        usage = psutil.disk_usage(partition.mountpoint)
        disks_info.append({
            'device': partition.device,
            'mount_point': partition.mountpoint,
            'file_system_type': partition.fstype,
            'total_size': usage.total,
            'free_space': usage.free,
            'used_space': usage.used,
            'percent_used': usage.percent
        })

    return disks_info
