#!/usr/bin/env python3
# coding: utf-8

usage = '''
Usage: watch.py [--dir=PATH] [--store=FILE] [--ext=EXT]

Options:
  --dir=PATH    path to directory from copy service file
  --store=FILE  name of YAML file where stored files info [default: service_list.yaml]
  --ext=EXT     extension of service [default: *]
'''

from docopt import docopt # pip3 install docopt
from file_comparator import *
from pprint import *
from subprocess import *
from pathlib import Path

class FileStoreComparator2(FileStoreComparator):

  def __init__(self, store_file: str, targetdir = '.\\'):
    super().__init__(store_file, targetdir)
    self.ignore_list = [] # NOTE: скрывает указанный файл в каждой дире!!! - это поведение надобы пофиксить но нет времени...

  def event_file_added(self, path):
    print('Added:', "/".join(path))

  def event_file_removed(self, path):
    print('Removed:', "/".join(path))

  def event_file_changed(self, path):
    print('Changed:', "/".join(path))

  def event_file_changed_store_error(self, path):
    print('Store error:', "/".join(path))

  def event_filter(self, path, isdir):
    if (isdir and '__pycache__' in path) or (not isdir and path[-1] in self.ignore_list):
      return False
    else:
      return True

def main():
  # параметры
  options = docopt(usage)

  # !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
  #options['--dir'] = 'D:\\Sync\\House0-programs'
  #options['--store'] = 'D:\\Sync\\House0-programs\\file_watcher\\service_list.yaml'

  store_cmp = FileStoreComparator2(options['--store'], options['--dir'])
  store_cmp.file_extension = options['--ext']
  store_cmp.ignore_list = [Path(options['--store']).name]

  store_cmp.compare()



if __name__ == "__main__":
  main()
