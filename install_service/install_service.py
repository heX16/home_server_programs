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
Usage: install_service.py [--dir_sysd=PATH] [--store_sysd=FILE] [--dir_cron=PATH] [--store_cron=FILE]

Options:
  --dir_sysd=PATH    path to directory from copy service file
  --store_sysd=FILE  name of YAML file where stored files info [default: service_list.yaml]
  --dir_cron=PATH    path to directory from copy crond file
  --store_cron=FILE  name of YAML file where stored files info [default: cron_list.yaml]
'''

from docopt import docopt # pip3 install docopt
from file_comparator import *
from pprint import *
from subprocess import *

def sh(command: str, *params):
  try:
    c = None
    c = run(command.format(*params), shell=True)
    if c!=None and c.stdout!='' and c.returncode!=0:
      print(c.stdout)
  except FileNotFoundError as e:
    print("Error: FileNotFound. Command: \"" + command.format(*params) + "\"")
  except Exception as e:
    print("Error: " + type(e) + ". Command: \"" + command.format(*params) + "\"")
    if c!=None and c.stderr!='':
      print("Output:")
      print(c.stderr)

class FileEventsSystemd:

  def file_added(self, file_name):
    print('Added:', file_name)
    sh("cp {1}{0} /etc/systemd/system/", file_name, self.dir)
    sh("sudo systemctl enable {0}", file_name)
    sh("sudo systemctl start {0}", file_name)

  def file_removed(self, file_name):
    print('Removed:', file_name)
    sh("sudo systemctl stop {0}", file_name)
    sh("sudo systemctl disable {0}", file_name)
    sh("rm /etc/systemd/system/{0}", file_name)
    sh("sudo systemctl daemon-reload")
    sh("sudo systemctl reset-failed")

  def file_changed(self, file_name):
    print('Changed:', file_name)
    sh("sudo systemctl stop {0}", file_name)
    sh("cp {1}{0} /etc/systemd/system", file_name, self.dir)
    sh("sudo systemctl daemon-reload")
    sh("sudo systemctl enable {0}", file_name)
    sh("sudo systemctl start {0}", file_name)

  def file_changed_store_error(self, file_name):
    print('Store error:', file_name)



class FileEventsCrond:

  def file_added(self, file_name):
    print('Added:', file_name)
    sh("cp {1}{0} /etc/cron.d/", file_name, self.dir)

  def file_removed(self, file_name):
    print('Removed:', file_name)
    sh("rm /etc/cron.d/{0}", file_name)

  def file_changed(self, file_name):
    print('Changed:', file_name)
    sh("cp {1}{0} /etc/cron.d/", file_name, self.dir)

  def file_changed_store_error(self, file_name):
    print('Store error:', file_name)



def main():
  # параметры
  options = docopt(usage)

  if '--store_sysd' in options and '--dir_sysd' in options:
    print('Begin systemd.')
    event = FileEventsSystemd()
    event.dir = options['--dir_sysd']
    store_cmp = FileStoreComparator(options['--store_sysd'], options['--dir_sysd'], '*.service')
    store_cmp.on_added   = event.file_added
    store_cmp.on_removed = event.file_removed
    store_cmp.on_changed = event.file_changed
    store_cmp.on_changed_store_error = event.file_changed_store_error
    store_cmp.compare()

  if '--store_cron' in options and '--dir_cron' in options:
    print('Begin crond.')
    event = FileEventsCrond()
    event.dir = options['--dir_cron']
    store_cmp = FileStoreComparator(options['--store_cron'], options['--dir_cron'], '*')
    store_cmp.on_added   = event.file_added
    store_cmp.on_removed = event.file_removed
    store_cmp.on_changed = event.file_changed
    store_cmp.on_changed_store_error = event.file_changed_store_error
    store_cmp.compare()

  print('End.')

if __name__ == "__main__":
  main()
