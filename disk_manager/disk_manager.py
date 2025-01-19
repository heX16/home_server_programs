"""
Disk Manager Script

Usage:
  disk_manager.py mount <config_file>
  disk_manager.py unmount <config_file>

Arguments:
  mount       Mount the specified partition.
  unmount     Unmount the specified partition.
  config_file Path to the YAML configuration file.

Options:
  -h --help   Show this screen.
"""

import subprocess
import time
import yaml
from docopt import docopt
import sys


def run_command(command):
    """
    Runs a shell command and returns its success status and output.

    :param command: Command to execute as a list.
    :return: Tuple (bool, str) indicating success status and output/error.
    """
    try:
        result = subprocess.run(command, text=True, capture_output=True)
        print(f'Command: {" ".join(command)}')
        print(f'Stdout: {result.stdout.strip()}')
        print(f'Stderr: {result.stderr.strip()}')
        if result.returncode == 0:
            return True, result.stdout.strip()
        else:
            return False, result.stdout.strip()
    except Exception as e:
        print(f'Error executing command: {" ".join(command)}\n{e}')
        return False, str(e)


def systemd_command(action, target):
    """
    Executes a systemd command with the specified action and target.

    :param action: SystemD action (e.g., 'start', 'stop').
    :param target: Target unit or service (e.g., 'service1', 'media-data2tb.mount').
    :return: Tuple (bool, str) indicating success status and output/error.
    """
    print(f'Executing systemd {action} command on {target}')
    return run_command(['systemctl', action, target])


def stop_services(services, timeout):
    """
    Stops the specified systemd services and waits until they are fully stopped.

    :param services: List of services to stop.
    :param timeout: Maximum time to wait for each service to stop, in seconds.
    """
    for service in services:
        print(f'Stopping service: {service}')
        success, output = systemd_command('stop', service)
        if not success:
            print(f'Failed to stop service {service}: {output}')
            sys.exit(1)

        print(f'Waiting for {service} to stop (timeout: {timeout} seconds)...')
        wait_time = 0

        while wait_time < timeout:
            success, status = systemd_command('is-active', service)
            if status.strip() == 'inactive':
                print(f'Service {service} stopped.')
                break
            wait_time += 1
            time.sleep(1)
        else:
            print(f'Timeout reached while waiting for {service} to stop. Exiting.')
            sys.exit(1)


def start_services(services):
    """
    Starts the specified systemd services.

    :param services: List of services to start.
    """
    for service in services:
        print(f'Starting service: {service}')
        success, output = systemd_command('start', service)
        if not success:
            print(f'Failed to start service {service}: {output}')
        else:
            print(f'Service {service} started.')


def mount_partition(mount_systemd_unit='', device='', mount_point=''):
    """
    Mounts a partition using either systemd or classic method.

    :param mount_systemd_unit: Name of the systemd mount unit (e.g., 'media-data2tb.mount').
    :param device: Device to mount (e.g., '/dev/sdX1').
    :param mount_point: Mount point to use (e.g., '/mnt/data').
    """
    if mount_systemd_unit:
        print(f'Mounting using SystemD: {mount_systemd_unit}')
        success, output = systemd_command('start', mount_systemd_unit)
        if not success:
            print(f'Failed to mount using SystemD: {mount_systemd_unit}\n{output}')
            sys.exit(1)
        print(f'Successfully mounted {mount_systemd_unit} using SystemD.')
    elif device and mount_point:
        print(f'Mounting partition {device} to {mount_point}')
        success, output = run_command(['mount', device, mount_point])
        if not success:
            print(f'Failed to mount partition {device} to {mount_point}: {output}')
            sys.exit(1)
        print(f'Partition {device} mounted to {mount_point}.')
    else:
        print('Invalid configuration: Specify either systemd_mount or device/mount_point for mounting.')
        sys.exit(1)


def unmount_partition(mount_systemd_unit='', device='', mount_point=''):
    """
    Unmounts a partition using either systemd or classic method.

    :param mount_systemd_unit: Name of the systemd mount unit (e.g., 'media-data2tb.mount').
    :param device: Device to unmount (e.g., '/dev/sdX1').
    :param mount_point: Mount point to unmount (e.g., '/mnt/data').
    """
    if mount_systemd_unit:
        print(f'Unmounting using SystemD: {mount_systemd_unit}')
        success, output = systemd_command('stop', mount_systemd_unit)
        if not success:
            print(f'Failed to unmount using SystemD: {mount_systemd_unit}\n{output}')
            sys.exit(1)
        print(f'Successfully unmounted {mount_systemd_unit} using SystemD.')
    elif mount_point:
        print(f'Unmounting partition: {mount_point}')
        success, output = run_command(['umount', mount_point])
        if not success:
            print(f'Failed to unmount partition {mount_point}: {output}')
            sys.exit(1)
        print(f'Partition {mount_point} unmounted.')
    else:
        print('Invalid configuration: Specify either systemd_mount or mount_point for unmounting.')
        sys.exit(1)


def main(action, config_file):
    """
    Main function to manage mount/unmount operations.

    :param action: 'mount' or 'unmount'.
    :param config_file: Path to the YAML configuration file.
    """
    with open(config_file, 'r') as file:
        config = yaml.safe_load(file)

    services = config.get('services', [])
    systemd_mount_unit = config.get('systemd_mount', '')
    device = config.get('device', '')
    mount_point = config.get('mount_point', '')
    timeout = config.get('timeout', 30)  # Default timeout is 30 seconds.

    if action == 'unmount':
        stop_services(services, timeout)
        unmount_partition(mount_systemd_unit, device, mount_point)
        start_services(services)
    elif action == 'mount':
        stop_services(services, timeout)
        mount_partition(mount_systemd_unit, device, mount_point)
        start_services(services)
    else:
        print('Invalid action. Use "mount" or "unmount".')
        sys.exit(1)


if __name__ == '__main__':
    arguments = docopt(__doc__)
    action = 'mount' if arguments['mount'] else 'unmount'
    config_file = arguments['<config_file>']
    main(action, config_file)
