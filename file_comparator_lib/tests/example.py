#!/usr/bin/env python3
# coding: utf-8

usage = '''
Usage: watch.py [--dir=PATH] [--store=FILE]

Options:
  --dir=PATH    path to directory to compare [default: .]
  --store=FILE  name of YAML file where stored files info [default: service_list.yaml]
'''

from docopt import docopt # pip3 install docopt
from file_comparator import *
from pprint import *
from subprocess import *
from pathlib import Path

class FileStoreComparator2(FileStoreComparator):

  def __init__(self, store_file: str, targetdir = '.\\'):
    super().__init__(store_file, targetdir)
    self.ignore_list = [] # NOTE: hides the file in every directory; should be fixed but not now.

  def event_file_added(self, path: Path) -> None:
    print('Added:', path.as_posix())

  def event_file_removed(self, path: Path) -> None:
    print('Removed:', path.as_posix())

  def event_file_changed(self, path: Path) -> None:
    print('Changed:', path.as_posix())

  def event_file_changed_store_error(self, path: Path) -> None:
    print('Store error:', path.as_posix())

  def event_filter(self, path: Path, isdir: bool) -> bool:
    if (isdir and '__pycache__' in path.parts) or (isdir and '.git' in path.parts) or (not isdir and path.name in self.ignore_list):
      return False
    else:
      return True

def main():
  # Parameters
  options = docopt(usage)

  # Example:
  # options['--dir'] = 'D:\\Sync\\House0-programs'
  # options['--store'] = 'D:\\Sync\\House0-programs\\file_watcher\\service_list.yaml'

  store_file = Path(options['--store'])
  target_dir = options['--dir'] or '.'
  store_cmp = FileStoreComparator2(store_file, target_dir)
  store_cmp.ignore_list = [store_file.name]

  store_cmp.compare()



if __name__ == "__main__":
  main()
