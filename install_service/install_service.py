#!/usr/bin/env python3
# coding: utf-8

version = 1.1

'''
Алгоритм:
Загрузить "списке своих сервисов", хранится в отдельном файле, тамже хранятся даты модификации файлов сервисов.
Загрузить список сервисов из _локальной_ папки "service".
1. Если в "локальной папке" появился новый "файл сервиса" - скопировать файл в "системную папку", дать команду {обновления, включения, запуска}.
2. Если в "локальной папке" исчез "файл сервиса" - дать команду {остановки, отключения}, удалить файл из "системной папки", дать команду обновления systemd.
3. Если в "локальной папке" "файл сервис" обновился - дать команду остановки, скопировать файл в "системную папку", дать команду {обновления, перезапуска}.

TODO:
    Добавить поддержку /etc/systemd/network/*.network файлов.

TODO:
    При изменении файлов (file_changed) делать копирование, "daemon-reload", и "reload-or-restart".
    Сейчас происходит stop/start - это неправильно.

TODO:
    файл список служб. в котором пишутся данные о состоянии служб после прогона файла.
    в нем также можно включить службу или отключить.

TODO:
    rename: install_service.py -> systemd_sync_manager.py

TODO:
    Предусмотреть возможность проверки конфигов.
    Проверка перед инсталяцией конфига.

TODO:
    Предусмотреть проверку на отсутствие файлов в "системной папке", но при этом их наличия в "списке локальных сервисов" и в "локальной папке".
    Если файлов нет в "системной папке" то сделать процедуры из пункта 1 (появился новый "файл сервиса").
    Это нужно для ситуации когда скрипт запускается на полностью новой системе.

TODO:
    The type suffix must be one of ".service", ".socket", ".device", ".mount", ".automount", ".swap", ".target", ".path", ".timer", ".slice", or ".scope". And "../network/*.network"



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
    print('Run:', command.format(*params))
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

  def file_filter(self, path, isdir):
    # TODO: add support suffix: ".service", ".socket", ".device", ".mount", ".automount", ".swap", ".target", ".path", ".timer", ".slice", or ".scope".
    file_name = "/".join(path)
    #print(file_name)
    return True

  def file_added(self, path):
    file_name = Path("/".join(path))
    print('Added:', file_name)
    sh("cp {1}{0} /etc/systemd/system/", str(file_name), self.dir)
    sh("sudo systemctl --quiet enable {0}", str(file_name))
    sh("sudo systemctl start {0}", str(file_name))
    if file_name.suffix == '.service':
      f_timer = file_name.with_suffix('.timer')
      if f_timer.is_file():
        sh("sudo systemctl start {0}", str(f_timer))

  def file_removed(self, path):
    file_name = "/".join(path)
    print('Removed:', file_name)
    sh("sudo systemctl stop {0}", file_name)
    sh("sudo systemctl --quiet disable {0}", file_name)
    sh("rm /etc/systemd/system/{0}", file_name)
    sh("sudo systemctl daemon-reload")
    sh("sudo systemctl reset-failed")

  def file_changed(self, path):
    file_name = "/".join(path)
    print('Changed:', file_name)
    sh("sudo systemctl stop {0}", file_name)
    sh("cp {1}{0} /etc/systemd/system/", file_name, self.dir)
    sh("sudo systemctl daemon-reload")
    sh("sudo systemctl --quiet enable {0}", file_name)
    sh("sudo systemctl start {0}", file_name)

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
