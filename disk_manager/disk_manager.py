'''
Disk Manager Script

Usage:
  disk_manager.py mount <config_file> [--verbose]
  disk_manager.py unmount <config_file> [--verbose]

Options:
  -h --help   Show this screen.
  --verbose   Print more debug information.
'''

import subprocess
import time
import yaml
from docopt import docopt
import sys
import logging
from typing import List, Optional

logger = logging.getLogger(__name__)

run_command_stdout = ''
run_command_stderr = ''
run_command_returncode = 0

def run_command(command: List[str]) -> bool:
    '''Runs a shell command.'''
    global run_command_stdout, run_command_stderr, run_command_returncode
    run_command_stdout = ''
    run_command_stderr = ''
    run_command_returncode = 0

    logger.debug('Running command: %s', ' '.join(command))
    try:
        result = subprocess.run(command, text=True, capture_output=True)
        run_command_stdout = result.stdout.strip()
        run_command_stderr = result.stderr.strip()
        run_command_returncode = result.returncode

        if run_command_stdout:
            logger.debug('#### Command stdout:\n%s', run_command_stdout)
        if run_command_stderr:
            logger.debug('#### Command stderr:\n%s', run_command_stderr)
        logger.debug('#### Command return code: %s', run_command_returncode)

        return (result.returncode == 0)
    except Exception as e:
        logger.exception('Error executing command: %s', ' '.join(command))
        run_command_stderr = str(e)
        return False


def systemd_command(action: str, target: str, check_errcode: bool = True) -> bool:
    '''Runs a systemd command.'''
    success = run_command(['systemctl', action, target])
    if check_errcode and not success:
        logger.error('Failed systemd %s for the service %s', action, target)
    return success


def detect_automount_unit(mount_unit: str) -> Optional[str]:
    '''Detects .automount if present.'''
    automount_candidate = mount_unit.replace('.mount', '.automount')
    ok = systemd_command('status', automount_candidate, check_errcode=False)
    return automount_candidate if ok else None


def start_services(services: list):
    '''Starts services.'''
    for service in services:
        logger.info('Starting service: %s', service)
        systemd_command('start', service)


def stop_services(services: list, timeout: int) -> bool:
    '''Stops services.'''
    for service in services:
        logger.info('Stopping service: %s', service)
        if not systemd_command('stop', service):
            logger.error('Cannot stop service %s', service)
            return False

        wait_time = 0
        while wait_time < timeout:
            systemd_command('is-active', service, check_errcode=False)
            if 'inactive' in run_command_stdout:
                logger.info('Service %s stopped.', service)
                break
            time.sleep(1)
            wait_time += 1
        else:
            logger.error('Timeout while stopping %s', service)
            return False
    return True


def systemd_get_properties(unit: str) -> dict:
    '''Calls "systemctl show <unit>" and returns a dict of key=value from the output.'''
    info_dict = {}
    ok = systemd_command('show', unit, check_errcode=False)
    if not ok:
        logger.debug('systemctl show %s failed or returned non-zero code.', unit)
        return info_dict

    for line in run_command_stdout.splitlines():
        if '=' in line:
            key, val = line.split('=', 1)
            info_dict[key] = val
    return info_dict


def systemd_unit_inactive(mount_unit: str) -> bool:
    ''' Checks if the SystemD mount unit is inactive '''
    p = systemd_get_properties(mount_unit)
    return p['ActiveState'] == 'inactive'


def partition_is_mounted(systemd_mount_unit: str = '', device: str = '', mount_point: str = '') -> bool:
    '''Checks if the partition is currently mounted via systemd or classic methods.'''
    if systemd_mount_unit:
        if systemd_unit_inactive(systemd_mount_unit):
            return False
        return True
    elif device and mount_point:
        ok = run_command(['mountpoint', '-q', mount_point])
        return ok
    else:
        logger.error('No systemd_mount or device/mount_point provided to check if partition is mounted.')
        return False


def mount_partition(systemd_mount_unit: str = '', device: str = '', mount_point: str = '') -> bool:
    '''Mounts a partition.'''
    if systemd_mount_unit:
        logger.info('Mounting with SystemD: %s', systemd_mount_unit)
        am = detect_automount_unit(systemd_mount_unit)
        if am:
            logger.info('Starting automount: %s', am)
            systemd_command('start', am)

        success = systemd_command('start', systemd_mount_unit)
        if not success:
            logger.error('Failed to mount using SystemD: %s', systemd_mount_unit)
        return success

    elif device and mount_point:
        logger.info('Mounting partition %s to %s', device, mount_point)
        success = run_command(['mount', device, mount_point])
        if not success:
            logger.error('Failed to mount %s to %s. stderr: %s',
                         device, mount_point, run_command_stderr)
        return success
    else:
        logger.error('Invalid config: no systemd_mount or device/mount_point provided')
        return False

def unmount_partition(systemd_mount_unit: str = '', device: str = '', mount_point: str = '') -> bool:
    '''Unmounts a partition.'''
    if systemd_mount_unit:
        logger.info('Unmounting with SystemD: %s', systemd_mount_unit)
        am = detect_automount_unit(systemd_mount_unit)
        if am:
            logger.info('Stopping automount: %s', am)
            systemd_command('stop', am)

        success = systemd_command('stop', systemd_mount_unit)
        if not success:
            systemd_command('status', systemd_mount_unit, check_errcode=False)
            logs_lower = (run_command_stdout + run_command_stderr).lower()
            if 'target is busy' in logs_lower or 'resource busy' in logs_lower:
                logger.error('Cannot unmount %s, it is busy.', systemd_mount_unit)
            else:
                logger.error('Failed to unmount using SystemD: %s', systemd_mount_unit)
        return success

    elif mount_point:
        logger.info('Unmounting partition: %s', mount_point)
        success = run_command(['umount', mount_point])
        if not success:
            logs_lower = (run_command_stdout + run_command_stderr).lower()
            if 'target is busy' in logs_lower or 'resource busy' in logs_lower:
                logger.error('Cannot unmount %s, it is busy.', mount_point)
            else:
                logger.error('Failed to unmount partition %s', mount_point)
        return success
    else:
        logger.error('Invalid config: no systemd_mount or mount_point provided')
        return False


def main(action: str, config_file: str) -> None:
    '''Main function.'''
    with open(config_file, 'r') as file:
        config = yaml.safe_load(file)

    services = config.get('services', [])
    systemd_mount_unit = config.get('systemd_mount', '')
    device = config.get('device', '')
    mount_point = config.get('mount_point', '')
    timeout = config.get('timeout', 30)

    mounted = partition_is_mounted(systemd_mount_unit, device, mount_point)
    if action == 'unmount' and not mounted:
        logger.warning('Partition is not mounted, skipping unmount.')
        sys.exit(0)
    elif action == 'mount' and mounted:
        logger.warning('Partition is already mounted, skipping mount.')
        sys.exit(0)

    if not stop_services(services, timeout):
        logger.error('Stopping services failed. Exiting.')
        sys.exit(1)

    if action == 'unmount':
        if not unmount_partition(systemd_mount_unit, device, mount_point):
            start_services(services)
            sys.exit(2)
        else:
            logger.info('Unmount succeeded.')
    elif action == 'mount':
        if not mount_partition(systemd_mount_unit, device, mount_point):
            start_services(services)
            sys.exit(3)
        else:
            logger.info('Mount succeeded.')

    start_services(services)


if __name__ == '__main__':
    arguments = docopt(__doc__)
    action = 'mount' if arguments['mount'] else 'unmount'
    config_file = arguments['<config_file>']

    verbose = arguments['--verbose']
    log_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=log_level, format='[%(levelname)s] %(message)s')

    main(action, config_file)
