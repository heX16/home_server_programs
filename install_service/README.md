Install systemd units from a synced folder
==========================================

`install_service.py` installs and updates `systemd` unit files from a local
directory synchronized to the server (for example via Syncthing).

The script detects:

- new unit files;
- removed unit files;
- changed unit files,

and runs the needed `systemctl` commands (copy, enable, start, stop, disable,
daemon‑reload, reset‑failed).


Usage
-----

Run on the server where `/opt/homesrv/home_server_programs` is located:

```bash
cd /opt/homesrv/home_server_programs/install_service
./install_service.py --dir=PATH --store=FILE
```

Arguments:

- `--dir=PATH` – path to the local directory with unit files;
- `--store=FILE` – YAML file with stored state
  (default inside the script: `service_list.yaml`).

Typical use: call the script from cron, a systemd timer or manually after you
change unit files in the synced directory.

