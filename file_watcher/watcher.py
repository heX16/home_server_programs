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
Usage: watcher.py --config=YAML_CFG [--dir=PATH] [--store=FILE] [--log-level=LEVEL] [--daemon] [--scantime=SECOND] [--skip-link]

Options:
  --config=YAML_CFG   YAML config where desc. action on file/dir changes [default: watcher_config.yaml]
  --dir=PATH    path to directory from copy service file
  --store=FILE  name of YAML file where stored files info [default: watcher_store.yaml]
  --log-level=LEVEL  log level [default: WARNING]
  --daemon      run to infinity loop (by default run once and end)
  --scantime=SECOND   scan interval (for daemon) [default: 60]
  --skip-link   ignore changes in symlink files
'''

version = 2.5

from docopt import docopt # pip3 install docopt
from file_comparator import *
from pprint import *
from subprocess import *
from pathlib import Path
import logging
import oyaml as yaml
import shutil # chown
import os # chmod, islink
import sys
import time

from watchdog.observers import Observer # pip3 install watchdog
from watchdog.events import FileSystemEventHandler

log = logging.getLogger('hspro.file_watcher')

def setup_logging(level_str: str) -> None:
  # journald is timestamping each entry; keep log lines compact and stderr-based.
  level_name = str(level_str).upper().strip()
  level = getattr(logging, level_name, None)
  if not isinstance(level, int):
    level = logging.WARNING

  log.handlers = []
  log.setLevel(level)
  log.propagate = False

  handler = logging.StreamHandler(sys.stderr)
  handler.setLevel(level)
  handler.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))
  log.addHandler(handler)

  if str(level_str).upper().strip() not in dir(logging):
    # Emit after configuration so it is guaranteed to appear under systemd.
    log.warning('Invalid --log-level value: %s. Using WARNING.', level_str)

def shell(command: str):
  try:
    c = None
    c = run(command, shell=True)
    if c!=None and c.stdout!='' and isinstance(c.stdout,str):
      log.info(c.stdout)
  except FileNotFoundError as e:
    log.error('Error: FileNotFound. Command: "%s"', command)
  except Exception as e:
    log.exception('Error: %s. Command: "%s"', type(e), command)
    if c!=None and c.stderr!='' and isinstance(c.stderr,str):
      log.error('Output:\n%s', c.stderr)

class FileStoreComparator2(FileStoreComparator):

  def __init__(self, store_file: str, targetdir: str = '.\\'):
    super().__init__(store_file, targetdir)
    self.config_path = '' # path to config for reload on change
    self.ignore_list = [] # NOTE: скрывает указанный файл в каждой дире!!! - это поведение надобы пофиксить но нет времени...
    self.run_commands = []
    self.skip_link = False

  def activate_cmd(self, cmd):
    if isinstance(cmd,str):
      cmd=[cmd]
    for c in cmd:
      if c in self.run_commands:
        self.run_commands[c] = True

  def detect_watch_event(self, path: Path) -> None:
    path_str = path.as_posix()
    # reload config file
    if path_str == self.config_path:
      self.load_config(self.config_path)
      return
    # find in files
    if path_str in self.config['files']:
      self.activate_cmd(self.config['files'][path_str])
    # find in dirs
    for config_path, config_cmd in self.config['dirs'].items():
      if path_str[:len(config_path)] == config_path:
        log.warning('Dir changed: %s', config_path)
        self.activate_cmd(config_cmd)
      # special mode - any change in targetdir
      if config_path == '.':
        log.warning('Dir changed: %s', self.targetdir)
        self.activate_cmd(config_cmd)

  def event_file_added(self, path: Path) -> None:
    log.warning('Added: %s', path.as_posix())
    self.detect_watch_event(path)

  def event_file_removed(self, path: Path) -> None:
    log.warning('Removed: %s', path.as_posix())
    self.detect_watch_event(path)

  def event_file_changed(self, path: Path) -> None:
    log.warning('Changed: %s', path.as_posix())
    self.detect_watch_event(path)

  def event_file_changed_store_error(self, path: Path) -> None:
    log.error('Store error:%s', path.as_posix())

  def event_filter(self, path: Path, isdir: bool) -> bool:
    #todo: __pycache__ - is hardcoded, add options or config for this.

    #todo: normalize path in: targetdir + "/" + "/".join(path). Example: targetdir='/etc', targetdir='etc', targetdir='/etc/'...

    if (
      (isdir and '__pycache__' in path.parts)
      or (not isdir and path.name in self.ignore_list)
      or (self.skip_link and (self.targetdir / path).is_symlink())
    ):
      return False
    else:
      return True

  def load_config(self, filename: str):
    # Read YAML file
    with open(filename, 'r', encoding='utf8') as stream:
        self.config = yaml.safe_load(stream)
        if self.config['files'] == None:
            log.warning('WARN: "files:" section is empty')
            self.config['files'] = {}
        if self.config['dirs'] == None:
            log.warning('WARN: "dirs:" section is empty')
            self.config['dirs'] = {}
    self.run_commands = dict.fromkeys(self.config['commands'].keys(), False)

  def compare(self):
    super().compare()

    for k,v in self.run_commands.items():
      if v:
        self.run_commands[k] = False
        log.warning('run: %s', k)
        shell(self.config['commands'][k])

    #todo: add options
    # fix FS state after run commands
    super().compare()
    # and ignore changes
    for k in self.run_commands.keys():
      self.run_commands[k] = False



class FlagEventHandler(FileSystemEventHandler):
    def __init__(self, logger=None):
        self.changed = False
        super().__init__()

    def on_moved(self, event):
        self.changed = True

    def on_created(self, event):
        self.changed = True

    def on_deleted(self, event):
        self.changed = True

    def on_modified(self, event):
        self.changed = True


def main():
  # параметры
  options = docopt(usage)
  setup_logging(options['--log-level'])

  # debug:
  #options['--dir'] = 'D:\\Sync\\House0-programs'
  #options['--store'] = 'D:\\Sync\\House0-programs\\file_watcher\\watcher_store_test.yaml'
  #options['--config'] = 'D:\\Sync\\House0-programs\\file_watcher\\watcher_config_test.yaml'

  store_cmp = FileStoreComparator2(options['--store'], options['--dir'])
  store_cmp.ignore_list.append(Path(options['--store']).name)
  store_cmp.config_path = options['--config']
  store_cmp.skip_link = options['--skip-link']
  store_cmp.load_config(store_cmp.config_path)

  if options['--daemon'] != True:
    # one run:
    store_cmp.compare()
  else:
    # background process:
    event_handler = FlagEventHandler()
    observer = Observer()
    observer.schedule(event_handler, str(store_cmp.targetdir), recursive=True)
    observer.start()
    try:
      #TODO: correct exit on SIG and etc...
      while True:
        time.sleep(int(options['--scantime']))
        if event_handler.changed:
            event_handler.changed = False
            store_cmp.compare()
    finally:
      if options['--daemon'] == True:
        observer.stop()
        observer.join()

if __name__ == "__main__":
  main()
