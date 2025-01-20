#!/usr/bin/env python3
# coding: utf-8

from docopt import docopt  # pip install docopt
from pprint import pprint
from subprocess import run, PIPE
from pathlib import Path
from typing import Union
import file_comparator

version = 2.2

usage = '''
Usage: install_service.py --dir=PATH --store=FILE

Options:
  --dir=PATH    path to directory from copy service file
  --store=FILE  name of YAML file where stored files info [default: service_list.yaml]
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

def sh(command: str, *params):
    """
    Run shell command with provided params. Compatible with Python 3.6.
    """
    c = None
    try:
        cmd_formatted = command.format(*params)
        print('Run:', cmd_formatted)
        # Capture output for c.stdout and c.stderr
        c = run(cmd_formatted, shell=True, stdout=PIPE, stderr=PIPE, universal_newlines=True)
        if c is not None and c.stdout and c.returncode != 0:
            print(c.stdout)
    except FileNotFoundError:
        print('Error: FileNotFound. Command: "' + command + '"')
    except Exception as e:
        print('Error: ' + str(type(e)) + '. Command: "' + command + '"')
        if c is not None and c.stderr:
            print('Output:')
            print(c.stderr)


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
        print(f'Error parsing file {file_path}: {e}')

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
        print('Added:', file_name)

        timer_file = service_has_timer(file_name)

        sh('cp {0}{1} /etc/systemd/system/', self.dir, str(file_name))

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
        print('Removed:', file_name)

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
        print('Changed:', file_name)

        timer_file = service_has_timer(Path(file_name))

        if systemd_file_supports_start(unit_type):
            sh('sudo systemctl stop {0}', file_name)
        sh('cp {1}{0} /etc/systemd/system/', file_name, self.dir)
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
        print('Store error:', file_name)


def main():
    options = docopt(usage)

    print('Starting systemd service manager.')
    print('Install systemd. Ver:', version)
    print('lib: file_comparator. Ver:', file_comparator.version)
    event = FileEventsSystemd()
    event.dir = options['--dir']
    store_cmp = file_comparator.FileStoreComparator(options['--store'], options['--dir'])
    store_cmp.on_added = event.file_added
    store_cmp.on_removed = event.file_removed
    store_cmp.on_changed = event.file_changed
    store_cmp.on_changed_store_error = event.file_changed_store_error
    store_cmp.on_filter = event.file_filter
    store_cmp.compare()

    print('End.')


if __name__ == '__main__':
    main()
