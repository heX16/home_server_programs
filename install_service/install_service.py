#!/usr/bin/env python3
# coding: utf-8

from pathlib import Path

version = 1.2

'''
Алгоритм:
Загрузить "списке своих сервисов", хранится в отдельном файле, тамже хранятся даты модификации файлов сервисов.
Загрузить список сервисов из _локальной_ папки "service".
1. Если в "локальной папке" появился новый "файл сервиса" - скопировать файл в "системную папку", дать команду {обновления, включения, запуска}.
2. Если в "локальной папке" исчез "файл сервиса" - дать команду {остановки, отключения}, удалить файл из "системной папки", дать команду обновления systemd.
3. Если в "локальной папке" "файл сервис" обновился - дать команду остановки, скопировать файл в "системную папку", дать команду {обновления, перезапуска}.

TODO:
    Добавить поддержку /etc/systemd/network/*.network файлов.
    suport "network/*.network"

TODO:
    файл с состояним служб.
    в котором пишутся данные о состоянии служб после обновления.
    можно запросить свежие данные в ручную - выставить флаг в файле.

TODO:
    файл в котором можно включить службу или отключить.

TODO:
    rename: install_service.py -> systemd_service_manager.py

TODO:
    Предусмотреть возможность проверки конфигов.
    Проверка перед инсталяцией конфига.
    если была ошибка то пишется в файл с состояним служб.

TODO:
    Предусмотреть проверку на отсутствие файлов в "системной папке", но при этом их наличия в "списке локальных сервисов" и в "локальной папке".
    Если файлов нет в "системной папке" то сделать процедуры из пункта 1 (появился новый "файл сервиса").
    Это нужно для ситуации когда скрипт запускается на полностью новой системе.

TODO:
    предусмотреть синхронизацию в другую сторону.


NOTE:
Для решения этой задачи можно было использовать "ansible", но мне хотелось чего-то простого, маленького, на основе синхронизации через syncthing, и без центрального управляющего хоста.
В ansible пришлось бы делать комбинацию из модулей: copy, systemd, (и наверное shell).
https://docs.ansible.com/ansible/latest/collections/ansible/builtin/
'''



usage = '''
Usage: install_service.py [--dir_sysd=PATH] [--store_sysd=FILE] [--dir_cron=PATH] [--store_cron=FILE]

Options:
  --dir_sysd=PATH    path to directory from copy service file
  --store_sysd=FILE  name of YAML file where stored files info [default: service_list.yaml]
  --dir_cron=PATH    path to directory from copy crond file
  --store_cron=FILE  name of YAML file where stored files info [default: cron_list.yaml]
'''

from docopt import docopt # pip3 install docopt
import file_comparator
from pprint import *
from subprocess import *
from pathlib import Path

def sh(command: str, *params):
  try:
    c = None
    command = command.format(*params)
    print('Run:', command)
    c = run(command, shell=True)
    if c!=None and c.stdout!='' and c.returncode!=0:
      print(c.stdout)
  except FileNotFoundError as e:
    print("Error: FileNotFound. Command: \"" + command + "\"")
  except Exception as e:
    print("Error: " + type(e) + ". Command: \"" + command + "\"")
    if c!=None and c.stderr!='':
      print("Output:")
      print(c.stderr)


def parse_service_file_WIP(self, file_path: Path):
    '''
    Parse .service file for custom parameters.
    '''
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
                elif line.startswith('install_service_start='):
                    start = line.split('=')[1].strip().lower() == 'true'
    except Exception as e:
        print(f'Error parsing file {file_path}: {e}')

    return service_type, enable, start


def service_has_timer(file_name: Path) -> Path | bool:
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


  def file_filter(self, path, isdir) -> bool:
    # TODO: add support suffix: ".service", ".socket", ".device", ".mount", ".automount", ".swap", ".target", ".path", ".timer", ".slice", or ".scope".
    file_name = "/".join(path)
    #print(file_name)
    return True


  def file_added(self, path):
    file_name = Path("/".join(path))
    unit_type = systemd_file_type(file_name)
    print('Added:', file_name)

    timer_file = service_has_timer(file_name)

    sh("cp {0}{1} /etc/systemd/system/", self.dir, str(file_name))

    if timer_file == False:
      if systemd_file_supports_enable(unit_type):
        sh("sudo systemctl --quiet enable {0}", str(file_name))
      if systemd_file_supports_start(unit_type):
        sh("sudo systemctl start {0}", str(file_name))
    else:
      sh("sudo systemctl start {0}", str(f_timer))


  def file_removed(self, path):
    file_name = "/".join(path)
    unit_type = systemd_file_type(file_name)
    print('Removed:', file_name)

    if systemd_file_supports_start(unit_type):
      sh("sudo systemctl stop {0}", file_name)
    if systemd_file_supports_enable(unit_type):
      sh("sudo systemctl --quiet disable {0}", file_name)
    sh("rm /etc/systemd/system/{0}", file_name)
    sh("sudo systemctl daemon-reload")
    sh("sudo systemctl reset-failed")


  def file_changed(self, path):
    file_name = "/".join(path)
    unit_type = systemd_file_type(file_name)
    print('Changed:', file_name)

    timer_file = service_has_timer(file_name)

    if systemd_file_supports_start(unit_type):
      sh("sudo systemctl stop {0}", file_name)
    sh("cp {1}{0} /etc/systemd/system/", file_name, self.dir)
    sh("sudo systemctl daemon-reload")

    if timer_file == False:
      if systemd_file_supports_enable(unit_type):
        sh("sudo systemctl --quiet enable {0}", str(file_name))
      if systemd_file_supports_start(unit_type):
        sh("sudo systemctl start {0}", str(file_name))
    else:
      sh("sudo systemctl start {0}", str(f_timer))


  def file_changed_store_error(self, path):
    file_name = "/".join(path)
    print('Store error:', file_name)



class FileEventsCrond:

  def file_added(self, path):
    file_name = "/".join(path)
    print('Added:', file_name)
    sh("cp {1}{0} /etc/cron.d/", file_name, self.dir)
    sh("sudo systemctl reload-or-restart cron.service")

  def file_removed(self, path):
    file_name = "/".join(path)
    print('Removed:', file_name)
    sh("rm /etc/cron.d/{0}", file_name)
    sh("sudo systemctl reload-or-restart cron.service")

  def file_changed(self, path):
    file_name = "/".join(path)
    print('Changed:', file_name)
    sh("cp {1}{0} /etc/cron.d/", file_name, self.dir)
    sh("sudo systemctl reload-or-restart cron.service")

  def file_changed_store_error(self, path):
    file_name = "/".join(path)
    print('Store error:', file_name)
    sh("sudo systemctl reload-or-restart cron.service")



def main():
  # параметры
  options = docopt(usage)

  print('Install systemd. Ver:', version)
  print('lib: file_comparator. Ver:', file_comparator.version)

  if options['--store_sysd'] is not None and options['--dir_sysd'] is not None:
    print('Begin systemd.')
    event = FileEventsSystemd()
    event.dir = options['--dir_sysd']
    store_cmp = file_comparator.FileStoreComparator(options['--store_sysd'], options['--dir_sysd'])
    store_cmp.on_added   = event.file_added
    store_cmp.on_removed = event.file_removed
    store_cmp.on_changed = event.file_changed
    store_cmp.on_changed_store_error = event.file_changed_store_error
    store_cmp.on_filter = event.file_filter
    store_cmp.compare()

  if options['--store_cron'] is not None and options['--dir_cron'] is not None:
    print('Begin crond.')
    event = FileEventsCrond()
    event.dir = options['--dir_cron']
    store_cmp = file_comparator.FileStoreComparator(options['--store_cron'], options['--dir_cron'])
    store_cmp.on_added   = event.file_added
    store_cmp.on_removed = event.file_removed
    store_cmp.on_changed = event.file_changed
    store_cmp.on_changed_store_error = event.file_changed_store_error
    store_cmp.compare()

  print('End.')

if __name__ == "__main__":
  main()
