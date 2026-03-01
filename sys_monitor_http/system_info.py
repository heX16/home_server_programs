import re
import subprocess
import time

import psutil

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


# RPi (vcgencmd) API — calls vcgencmd and parses output
def _run_vcgencmd(args):
    """Run vcgencmd with given args. Returns (success, stdout_str or None)."""
    try:
        result = subprocess.run(
            ['vcgencmd'] + args,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout:
            return True, result.stdout.strip()
        return False, None
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False, None


def get_rpi_vcgencmd_available():
    ok, _ = _run_vcgencmd(['measure_temp'])
    return {'vcgencmd_available': ok}


def get_rpi_temperature():
    ok, out = _run_vcgencmd(['measure_temp'])
    if not ok or not out:
        return {'temperature': 0.0}
    # Parse e.g. "temp=56.9'C"
    m = re.search(r"temp=([\d.]+)", out)
    if m:
        try:
            return {'temperature': float(m.group(1))}
        except ValueError:
            pass
    return {'temperature': 0.0}


# Throttled bit masks and flag names (vcgencmd get_throttled)
THROTTLED_FLAGS = [
    (0x1, 'under_voltage_detected'),
    (0x2, 'arm_frequency_capped'),
    (0x4, 'currently_throttled'),
    (0x8, 'soft_temperature_limit_active'),
    (0x10000, 'under_voltage_occurred'),
    (0x20000, 'arm_frequency_capping_occurred'),
    (0x40000, 'throttling_occurred'),
    (0x80000, 'soft_temperature_limit_occurred'),
]


def get_rpi_throttled():
    ok, out = _run_vcgencmd(['get_throttled'])
    if not ok or not out:
        return {'throttled_raw': '', 'throttled_info': []}
    m = re.search(r'throttled=(0x[0-9a-fA-F]+)', out)
    if not m:
        return {'throttled_raw': '', 'throttled_info': []}
    raw = m.group(1)
    try:
        value = int(raw, 16)
    except ValueError:
        return {'throttled_raw': '', 'throttled_info': []}
    throttled_info = [name for mask, name in THROTTLED_FLAGS if value & mask]
    return {'throttled_raw': raw, 'throttled_info': throttled_info}

