#!/usr/bin/env python3
# coding: utf-8

'''
Алгоритм:
Загрузить "списке своих сервисов", хранится в отдельном файле, тамже хранятся даты модификации файлов сервисов.
Загрузить список сервисов из _локальной_ папки "service".
1. Если в "локальной папке" появился новый "файл сервиса" - скопировать файл в "системную папку", дать команду {обновления, включения, запуска}.
2. Если в "локальной папке" исчез "файл сервиса" - дать команду {остановки, отключения}, удалить файл из "системной папки", дать команду обновления systemd.
3. Если в "локальной папке" "файл сервис" обновился - дать команду остановки, скопировать файл в "системную папку", дать команду {обновления, перезапуска}.

TODO:
Предусмотреть проверку на отсутствие файлов в "системной папке", но при этом их наличия в "списке локальных сервисов" и в "локальной папке".
Если файлов нет в "системной папке" то сделать процедуры из пункта 1 (появился новый "файл сервиса").
Это нужно для ситуации когда скрипт запускается на полностью новой системе.

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
    sh("sudo systemctl reload-or-restart cron.service")

  def file_removed(self, file_name):
    print('Removed:', file_name)
    sh("rm /etc/cron.d/{0}", file_name)
    sh("sudo systemctl reload-or-restart cron.service")

  def file_changed(self, file_name):
    print('Changed:', file_name)
    sh("cp {1}{0} /etc/cron.d/", file_name, self.dir)
    sh("sudo systemctl reload-or-restart cron.service")

  def file_changed_store_error(self, file_name):
    print('Store error:', file_name)
    sh("sudo systemctl reload-or-restart cron.service")



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
