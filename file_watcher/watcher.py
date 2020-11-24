#!/usr/bin/env python3
# coding: utf-8

'''
Программа которая обнаруживает изменения в дирикториях и/или файлах.
И если произошло изменение то запускает программу.
Настраивается только на одну дирикторию "--dir" и следит за дирикториями и файлами в ней.

Конфигурация:
commands: # список команд.
  ИмяКоманды: 'Текст команды'
files:    # файлы для отслеживания.
  'ПутьФайла': ИмяКоманды
dirs:     # дириктории для отслеживания.
  'ПутьДириктории': ИмяКоманды

'''

usage = '''
Usage: watcher.py --config=YAML_CFG [--dir=PATH] [--store=FILE] [--ext=EXT] [--daemon] [--scantime=SECOND]

Options:
  --config=YAML_CFG   YAML config where desc. action on file/dir changes [default: watcher_config.yaml]
  --dir=PATH    path to directory from copy service file
  --store=FILE  name of YAML file where stored files info [default: watcher_store.yaml]
  --ext=EXT     extension of service [default: *]
  --daemon      run to infinity loop (by default run once and end)
  --scantime=SECOND   scan interval (for daemon) [default: 60]
'''

from docopt import docopt # pip3 install docopt
from file_comparator import *
from pprint import *
from subprocess import *
from pathlib import Path
import oyaml as yaml
import shutil # chown
import os # chmod
import time

def shell(command: str):
  try:
    c = None
    c = run(command, shell=True)
    if c!=None and c.stdout!='' and isinstance(c.stdout,str):
      print(c.stdout)
  except FileNotFoundError as e:
    print("Error: FileNotFound. Command: \"" + command + "\"")
  except Exception as e:
    print("Error: " + type(e) + ". Command: \"" + command + "\"")
    if c!=None and c.stderr!='' and isinstance(c.stderr,str):
      print("Output:")
      print(c.stderr)

class FileStoreComparator2(FileStoreComparator):

  def __init__(self, store_file: str, targetdir = '.\\'):
    super().__init__(store_file, targetdir)
    self.config_path = '' # path to config for reload on change
    self.ignore_list = [] # NOTE: скрывает указанный файл в каждой дире!!! - это поведение надобы пофиксить но нет времени...
    self.run_commands = []

  def activate_cmd(self, cmd):
    if isinstance(cmd,str):
      cmd=[cmd]
    for c in cmd:
      if c in self.run_commands:
        self.run_commands[c] = True

  def detect_watch_event(self, path):
    path_str = "/".join(path)
    # reload config file
    if path_str == self.config_path:
      self.load_config(self.config_path)
      return
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
    with open(filename, 'r', encoding='utf8') as stream:
        self.config = yaml.load(stream)
        if self.config['files'] == None:
            print('WARN: "files:" section is empty')
            self.config['files'] = {}
        if self.config['dirs'] == None:
            print('WARN: "dirs:" section is empty')
            self.config['dirs'] = {}
    self.run_commands = dict.fromkeys(self.config['commands'].keys(), False)

  def compare(self):
    super().compare()

    for k,v in self.run_commands.items():
      if v:
        self.run_commands[k] = False
        print('run: ' + k)
        shell(self.config['commands'][k])

    #todo: add options
    # fix FS state after run commands
    super().compare()
    # and ignore changes
    for k in self.run_commands.keys():
      self.run_commands[k] = False


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
  store_cmp.config_path = options['--config']
  store_cmp.load_config(store_cmp.config_path)

  while True:
    store_cmp.compare()
    if options['--daemon'] != True:
      break
    time.sleep(int(options['--scantime']))

if __name__ == "__main__":
  main()
