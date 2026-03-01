# sys_monitor_http — GPT memory / project summary

HTTP service for system monitoring (CPU, RAM, disks, uptime). Web UI with Chart.js; multiple backends.

## Structure

| File | Role |
|------|------|
| `system_info.py` | Shared logic: `get_system_status()`, `get_disk_info()`, `get_rpi_*()` (RPi/vcgencmd stubs). Uses `psutil`. |
| `fastapi_backend.py` | FastAPI app: `/`, `/api/system_status`, `/api/disk`, `/api/rpi/*`, static files. |
| `flask_backend.py` | Same API on Flask; `app.run(debug=True)`. |
| `flask_cgi_backend.exec.py` | Flask + `CGIHandler` for Apache CGI; script runs per request, no long-lived process. |
| `static/index.html` | UI: CPU line chart, memory doughnut, disk list + progress, uptime. |
| `static/system_monitor.js` | Chart.js init, poll API every 5s, format bytes/uptime. |
| `sys_monitor_http.conf` | Apache snippet: `ScriptAlias /sysmon` → `flask_cgi_backend.exec.py`, CGI, logs. |
| `old/` | Legacy backends (e.g. FastAPI with inline system logic). |

## API

- `GET /` → `index.html`
- `GET /api/system_status` → `{ cpu: { usage, cores }, memory: { total, available, used, percent }, uptime: { system } }`
- `GET /api/disk` → list of `{ device, mountpoint, fstype, usage }`; one device can have multiple mountpoints merged into one entry.
- `GET /api/rpi/vcgencmd_available` → `{ vcgencmd_available: bool }`
- `GET /api/rpi/temperature` → `{ temperature: float }`
- `GET /api/rpi/throttled` → `{ throttled_raw: string, throttled_info: string[] }` (decoded flag names when bits set)

## Deps

- FastAPI: `fastapi`, `uvicorn`, `psutil`
- Flask: `Flask`, `psutil`

## Run / deploy

- Local: `python flask_backend.py` or `uvicorn fastapi_backend:app`
- Apache CGI: enable CGI, use README + `sys_monitor_http.conf`; `/sysmon` runs CGI script per request (saves RAM when rarely used).

## Code notes

- FastAPI: static mount and `index.html` path assume CWD; can break if run from another dir. Flask CGI uses `static_folder='static'`.
- `index.html` loads `static/system_monitor.js`; OK for Flask; for FastAPI ensure static root matches.
- `system_monitor.js` `formatBytes`: `Math.round(x, 2)` is invalid (JS `Math.round` has one arg); use e.g. `toFixed(2)` for 2 decimals.
- `get_disk_info()` merges multiple mountpoints per device into one record; `mountpoint` can be `"m1\n ; m2"`; frontend shows it as one block.
- RPi (vcgencmd): `get_rpi_temperature()` runs `vcgencmd measure_temp`, parses e.g. `temp=56.9'C` → `{ temperature: float }`; on failure returns `0.0`. `get_rpi_vcgencmd_available()` uses same call to detect presence. `get_rpi_throttled()` runs `vcgencmd get_throttled`, returns raw hex string and `throttled_info` list of active flag names (see `THROTTLED_FLAGS` in system_info.py).
