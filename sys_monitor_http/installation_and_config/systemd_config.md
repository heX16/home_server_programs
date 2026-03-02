# Systemd socket activation for Sys Monitor HTTP

**Idea:** Port is held by systemd; the app starts on first connection and stops after idle. When nobody is connected, memory use is effectively zero.

## How it works

1. **sysmon.socket** — listens on the public port (always on, minimal footprint).
2. First TCP connection → systemd starts **sysmon.service** (proxy) and **sysmon-app.service** (Flask).
3. **systemd-socket-proxyd** accepts on the socket and forwards to the app on a local port.
4. After idle timeout the proxy exits → app stops (`StopWhenUnneeded=yes`) → only the socket keeps listening.

## Unit files

| File | Role |
|------|------|
| `sysmon.socket` | Listens on public port, activates `sysmon.service` on connection |
| `sysmon.service` | Runs `systemd-socket-proxyd` with idle timeout → app port |
| `sysmon-app.service` | Runs Flask (`flask_backend:app`) on localhost |

Unit file contents, paths, and port numbers: see `systemd_cfg/`.

## Deployment

Copy the three unit files to the system (e.g. `/etc/systemd/system/`), set the app directory in `sysmon-app.service`, then enable and start only the socket (e.g. `systemctl enable --now sysmon.socket`). The two services have no `[Install]` and start on demand.

## Notes

- Only the socket is enabled; services are started by the socket.
- Uses built-in `systemd-socket-proxyd` (no extra packages).
- For higher load, Flask can be replaced with gunicorn in `sysmon-app.service`; the activation flow stays the same.
