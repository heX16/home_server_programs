#!/usr/bin/env python3
# coding: utf-8

'''
Загрузить список уже установленных сервисов и дату модификации файла (хранится в отдельном файле).
Загрузить список сервисов из папки "service".
1. Если появился новый сервис - скопировать файл, дать команду {обновления, включения, запуска}.
2. Если исчез сервис - дать команду {остановки, отключения}, удалить старую копию файла, дать команду обновления.
3. Если сервис обновился - дать команду остановки, скопировать файл, дать команду {обновления, перезапуска}.
'''

usage = '''
Usage: install_service.py --dir=PATH [--store=FILE] [--ext=EXT]

Options:
  --dir=PATH    path to directory from copy service file
  --store=FILE  name of YAML file where stored files info [default: service_list.yaml]
  --ext=EXT     extension of service [default: *.service]
'''

from docopt import docopt # pip3 install docopt
from file_comparator import *
from pprint import *
from subprocess import *

def sh(command: str, *params):
  try:
    c = None
    c = run(command.format(*params), shell=True)
    if c!=None and c.stdout!='':
      print(c.stdout)
  except FileNotFoundError as e:
    print("Error: FileNotFound. Command: \"" + command.format(*params) + "\"")
  except Exception as e:
    print("Error: " + type(e) + ". Command: \"" + command.format(*params) + "\"")
    if c!=None and c.stderr!='':
      print("Output:")
      print(c.stderr)

def event_file_added(file_name):
  print('Added:', file_name)
  sh("cp service/{0} /etc/systemd/system/", file_name)
  sh("systemctl enable {0}", file_name)
  sh("systemctl start {0}", file_name)

def event_file_removed(file_name):
  print('Removed:', file_name)
  sh("systemctl stop {0}", file_name)
  sh("systemctl disable {0}", file_name)
  sh("rm /etc/systemd/system/{0}", file_name)

def event_file_changed(file_name):
  print('Changed:', file_name)
  sh("systemctl stop {0}", file_name)
  sh("cp service/{0} /etc/systemd/system", file_name)
  sh("systemctl enable {0}", file_name)
  sh("systemctl start {0}", file_name)

def event_file_changed_store_error(file_name):
  print('Store error:', file_name)


def main():
  # параметры
  options = docopt(usage)

  store_cmp = FileStoreComparator(options['--store'], options['--dir'], options['--ext'])

  store_cmp.on_added = event_file_added
  store_cmp.on_removed = event_file_removed
  store_cmp.on_changed = event_file_changed
  store_cmp.on_changed_store_error = event_file_changed_store_error

  store_cmp.compare()

if __name__ == "__main__":
  main()
