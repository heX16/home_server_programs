import psutil
import time

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

def get_disk_info():
    partitions = psutil.disk_partitions()
    consolidated_info = {}

    # Consolidate partitions by device
    for partition in partitions:
        if partition.device in consolidated_info:
            # Append mountpoint to existing device entry
            consolidated_info[partition.device]['mountpoint'] += f'\n ; {partition.mountpoint}'
        else:
            # Add new device entry
            consolidated_info[partition.device] = {
                'device': partition.device,
                'mountpoint': partition.mountpoint,
                'fstype': partition.fstype,
                'usage': psutil.disk_usage(partition.mountpoint)._asdict()
            }

    # Return the consolidated list of partition info
    return list(consolidated_info.values())

