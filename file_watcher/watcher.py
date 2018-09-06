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
Usage: watch.py [--config=YAML_CFG] [--dir=PATH] [--store=FILE] [--ext=EXT]

Options:
  --config=YAML_CFG   YAML config where desc. action on file/dir changes [default: watcher_config.yaml]
  --dir=PATH    path to directory from copy service file
  --store=FILE  name of YAML file where stored files info [default: service_list.yaml]
  --ext=EXT     extension of service [default: *]
'''

from docopt import docopt # pip3 install docopt
from file_comparator import *
from pprint import *
from subprocess import *
from pathlib import Path
import yaml
import shutil # chown
import os # chmod

def shell(command: str):
  try:
    c = None
    c = run(command, shell=True)
    if c!=None and c.stdout!='' and type(c.stdout)==str:
      print(c.stdout)
  except FileNotFoundError as e:
    print("Error: FileNotFound. Command: \"" + command + "\"")
  except Exception as e:
    print("Error: " + type(e) + ". Command: \"" + command + "\"")
    if c!=None and c.stderr!='' and type(c.stderr)==str:
      print("Output:")
      print(c.stderr)

class FileStoreComparator2(FileStoreComparator):

  def __init__(self, store_file: str, targetdir = '.\\'):
    super().__init__(store_file, targetdir)
    self.ignore_list = [] # NOTE: скрывает указанный файл в каждой дире!!! - это поведение надобы пофиксить но нет времени...
    self.run_commands = []

  def activate_cmd(self, cmd):
    if type(cmd)==str:
      cmd=[cmd]
    for c in cmd:
      if c in self.run_commands:
        self.run_commands[c] = True

  def detect_watch_event(self, path):
    path_str = "/".join(path)
    # find in files
    if path_str in self.config['files']:
      self.activate_cmd(self.config['files'][path_str])
    # find in dirs
    for k,cmd in self.config['dirs'].items():
      if path_str[:len(k)] == k:
        print('Dir changed: ' + k)
        self.activate_cmd(cmd)

  def event_file_added(self, path):
    print('Added: ' + "/".join(path))
    self.detect_watch_event(path)

  def event_file_removed(self, path):
    print('Removed: ' + "/".join(path))
    self.detect_watch_event(path)

  def event_file_changed(self, path):
    print('Changed: ' + "/".join(path))
    self.detect_watch_event(path)

  def event_file_changed_store_error(self, path):
    print('Store error:' + "/".join(path))

  def event_filter(self, path, isdir):
    if (isdir and '__pycache__' in path) or (not isdir and path[-1] in self.ignore_list):
      return False
    else:
      return True

  def load_config(self, filename: str):
    # Read YAML file
    cfg_list = None
    with open(filename, 'r', encoding='utf8') as stream:
        self.config = yaml.load(stream)
    #self.run_commands = {k: False   for k in self.config['commands'].keys() }
    self.run_commands = dict.fromkeys(self.config['commands'].keys(), False)

  def compare(self):
    super().compare()

    for k,v in self.run_commands.items():
      if v:
        self.run_commands[k] = False
        print('run:', k)
        shell(self.config['commands'][k])



def main():
  # параметры
  options = docopt(usage)

  # debug:
  #options['--dir'] = 'D:\\Sync\\House0-programs'
  #options['--store'] = 'D:\\Sync\\House0-programs\\file_watcher\\watcher_store_test.yaml'
  #options['--config'] = 'D:\\Sync\\House0-programs\\file_watcher\\watcher_config_test.yaml'

  store_cmp = FileStoreComparator2(options['--store'], options['--dir'])
  store_cmp.file_extension = options['--ext']
  store_cmp.ignore_list.append(Path(options['--store']).name)
  store_cmp.load_config(options['--config'])

  store_cmp.compare()

if __name__ == "__main__":
  main()
