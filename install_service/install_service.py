#!/usr/bin/env python3
# coding: utf-8

from docopt import docopt  # pip install docopt
from pprint import pprint
from subprocess import run, PIPE
from pathlib import Path
from typing import Union
import logging
import sys
import file_comparator

version = 2.2

usage = '''
Usage: install_service.py --dir=PATH --store=FILE [--log-level=LEVEL]

Options:
  --dir=PATH    path to directory from copy service file
  --store=FILE  name of YAML file where stored files info
  --log-level=LEVEL  log level [default: WARNING]
'''

some_notes = '''
### Algorithm:

1. Load the **"list of your services"**, stored in a separate file, where the
   modification dates of the service files are also stored.
2. Load the list of services from the **_local_ folder "service"**.

#### Steps:

1. If there is a new **"service file"** in the **"local folder"**:
   - Copy the file to the **"system folder"**.
   - Give the command: `{update, enable, start}`.
2. If the **"service file"** disappeared in the **"local folder"**:
   - Give the command: `{stop, disable}`.
   - Delete the file from the **"system folder"**.
   - Give the `systemd update` command.
3. If the **"service file"** is updated in the **"local folder"**:
   - Give the `stop` command.
   - Copy the file to the **"system folder"**.
   - Give the command: `{update, restart}`.

---

### NOTE:

I could have used **"ansible"** for this task, but I wanted something
_simple_, _small_, based on synchronization via syncthing, and without a
central controlling host.
In **ansible**, I would have to make a combination of the modules: `copy`,
`systemd` (and probably `shell`). But this solution is terrible!
[Ansible Documentation](https://docs.ansible.com/ansible/latest/collections/ansible/builtin/)
'''

log = logging.getLogger('hspro.install_service')

def setup_logging(level_str: str) -> None:
    # journald is timestamping each entry; keep log lines compact and stderr-based.
    level_name = str(level_str).upper().strip()
    level = getattr(logging, level_name, None)
    if not isinstance(level, int):
        level = logging.WARNING

    log.handlers = []
    log.setLevel(level)
    log.propagate = False

    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(level)
    handler.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))
    log.addHandler(handler)

    if str(level_str).upper().strip() not in dir(logging):
        # Emit after configuration so it is guaranteed to appear under systemd.
        log.warning('Invalid --log-level value: %s. Using WARNING.', level_str)

def sh(command: str, *params):
    """
    Run shell command with provided params. Compatible with Python 3.6.
    """
    c = None
    try:
        cmd_formatted = command.format(*params)
        log.warning('Run: %s', cmd_formatted)
        # Capture output for c.stdout and c.stderr
        c = run(cmd_formatted, shell=True, stdout=PIPE, stderr=PIPE, universal_newlines=True)
        if c is not None and c.stdout and c.returncode != 0:
            log.error('%s', c.stdout)
    except FileNotFoundError:
        log.error('Error: FileNotFound. Command: "%s"', command)
    except Exception as e:
        log.exception('Error: %s. Command: "%s"', type(e), command)
        if c is not None and c.stderr:
            log.error('Output:\n%s', c.stderr)


def parse_service_file_WIP(self, file_path: Path):
    """
    Parse .service file for custom parameters.
    """
    enable = True
    start = True
    service_type = ''

    try:
        with open(file_path, 'r') as file:
            for line in file:
                if line.strip().startswith('Type='):
                    service_type = line.split('=')[1].strip().lower()
                if line.strip().startswith('install_service_enable='):
                    enable = line.split('=')[1].strip().lower() == 'true'
                elif line.strip().startswith('install_service_start='):
                    start = line.split('=')[1].strip().lower() == 'true'
    except Exception as e:
        log.error('Error parsing file %s: %s', file_path, e)

    return service_type, enable, start


def service_has_timer(file_name: Path) -> Union[Path, bool]:
    """
    Check if a given .service file has a corresponding .timer file.

    :param file_name: Path object representing the .service file.
    :return: Path object for the .timer file if it exists, otherwise False.
    """
    if systemd_file_type(file_name) == 'service':
        f_timer = file_name.with_suffix('.timer')
        if f_timer.is_file():
            return f_timer
    return False


def systemd_file_type(file_name: Path):
    """
    Extracts the type of a systemd service file based on its suffix (and validates it).

    :param file_name: Path object representing the file.
    :return: String with the file type if valid (e.g., 'service', 'timer'), or False if invalid.
    """
    valid_types = {
        'service', 'timer', 'socket', 'device', 'mount', 'automount',
        'swap', 'target', 'path', 'slice', 'scope'
    }
    suffix = file_name.suffix[1:]  # Extract suffix without the dot

    if suffix in valid_types:
        return suffix
    return False


def systemd_file_supports_enable(file_type: str) -> bool:
    """
    Checks if a systemd unit file type supports the 'enable' command.

    Supported types for 'enable':
    - service: Enables auto-start of services.
    - timer: Enables scheduling of timers.
    - socket: Enables auto-start of sockets.
    - mount: Enables auto-mounting of filesystem points.
    - automount: Enables automatic mounting of filesystem points.
    - swap: Enables auto-start of swap units.
    - target: Enables grouping of other units.
    - path: Enables file or directory monitoring.

    :param file_type: Type of the systemd unit (e.g., 'service', 'timer').
    :return: True if the 'enable' command is supported, otherwise False.
    """
    enable_supported = {
        'service', 'timer', 'socket', 'mount', 'automount',
        'swap', 'target', 'path'
    }
    return file_type in enable_supported


def systemd_file_supports_start(file_type: str) -> bool:
    """
    Checks if a systemd unit file type supports the 'start' command.

    Supported types for 'start':
    - service: Starts services manually.
    - timer: Activates timers.
    - socket: Activates sockets for listening.
    - mount: Mounts filesystem points.
    - swap: Activates swap units.
    - target: Activates groups of units.

    :param file_type: Type of the systemd unit (e.g., 'service', 'timer').
    :return: True if the 'start' command is supported, otherwise False.
    """
    start_supported = {
        'service', 'timer', 'socket', 'mount', 'swap', 'target'
    }
    return file_type in start_supported


class FileEventsSystemd:
    """
    Class handling file events for systemd service management.
    """


    def file_filter(self, path, isdir) -> bool:
        # TODO: implement suffix-based filtering as needed.
        file_name = '/'.join(path)
        return True

    def file_added(self, path):
        file_name = Path('/'.join(path))
        unit_type = systemd_file_type(file_name)
        log.warning('Added: %s', file_name)

        timer_file = service_has_timer(file_name)

        sh('cp {0} /etc/systemd/system/', str(Path(self.dir) / file_name))

        if timer_file == False:
            if systemd_file_supports_enable(unit_type):
                sh('sudo systemctl --quiet enable {0}', str(file_name))
            if systemd_file_supports_start(unit_type):
                sh('sudo systemctl start {0}', str(file_name))
        else:
            sh('sudo systemctl start {0}', str(timer_file))

    def file_removed(self, path):
        file_name = '/'.join(path)
        unit_type = systemd_file_type(Path(file_name))
        log.warning('Removed: %s', file_name)

        if systemd_file_supports_start(unit_type):
            sh('sudo systemctl stop {0}', file_name)
        if systemd_file_supports_enable(unit_type):
            sh('sudo systemctl --quiet disable {0}', file_name)
        sh('rm /etc/systemd/system/{0}', file_name)
        sh('sudo systemctl daemon-reload')
        sh('sudo systemctl reset-failed')

    def file_changed(self, path):
        file_name = '/'.join(path)
        unit_type = systemd_file_type(Path(file_name))
        log.warning('Changed: %s', file_name)

        timer_file = service_has_timer(Path(file_name))

        if systemd_file_supports_start(unit_type):
            sh('sudo systemctl stop {0}', file_name)
        sh('cp {0} /etc/systemd/system/', str(Path(self.dir) / file_name))
        sh('sudo systemctl daemon-reload')

        if timer_file == False:
            if systemd_file_supports_enable(unit_type):
                sh('sudo systemctl --quiet enable {0}', str(file_name))
            if systemd_file_supports_start(unit_type):
                sh('sudo systemctl start {0}', str(file_name))
        else:
            sh('sudo systemctl start {0}', str(timer_file))

    def file_changed_store_error(self, path):
        file_name = '/'.join(path)
        log.error('Store error: %s', file_name)


class FileStoreComparatorAutoSave(file_comparator.FileStoreComparator):
    def on_store_updated(self, path: list):
        # Persist store early (before any external commands that may hang).
        if self._store_root is None:
            return
        self.save_store(self._store_root)


def main():
    options = docopt(usage)

    setup_logging(options['--log-level'])

    log.info('Starting systemd service manager.')
    log.info('Install systemd. Ver: %s', version)
    log.info('lib: file_comparator. Ver: %s', file_comparator.version)
    event = FileEventsSystemd()
    event.dir = options['--dir']
    store_cmp = FileStoreComparatorAutoSave(options['--store'], options['--dir'])
    store_cmp.on_added = event.file_added
    store_cmp.on_removed = event.file_removed
    store_cmp.on_changed = event.file_changed
    store_cmp.on_changed_store_error = event.file_changed_store_error
    store_cmp.on_filter = event.file_filter
    store_cmp.compare()

    log.info('End.')


if __name__ == '__main__':
    main()
