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

  def __init__(self, store_file, targetdir='.\\'):
    super().__init__(store_file, targetdir)
    self.store_rel_path = path_relative_to_dir(self.store_file, self.targetdir)

  def event_file_added(self, path: Path) -> None:
    print('Added:', path.as_posix())

  def event_file_removed(self, path: Path) -> None:
    print('Removed:', path.as_posix())

  def event_file_changed(self, path: Path) -> None:
    print('Changed:', path.as_posix())

  def event_file_changed_store_error(self, path: Path) -> None:
    print('Store error:', path.as_posix())

  def event_filter(self, path: Path, isdir: bool) -> bool:
    if (isdir and '__pycache__' in path.parts) or (isdir and '.git' in path.parts):
      return False
    if self.store_rel_path and relative_path_matches_ignore_entry(path, [self.store_rel_path]):
      return False
    return super().event_filter(path, isdir)

  def _purge_ignored_from_store(self, store: dict) -> None:
    super()._purge_ignored_from_store(store)
    if not store or not self.store_rel_path:
      return
    for key in list(store.keys()):
      if relative_path_matches_ignore_entry(key, [self.store_rel_path]):
        store.pop(key, None)

def main():
  # Parameters
  options = docopt(usage)

  # Example:
  # options['--dir'] = 'D:\\Sync\\House0-programs'
  # options['--store'] = 'D:\\Sync\\House0-programs\\file_watcher\\service_list.yaml'

  store_file = Path(options['--store'])
  target_dir = options['--dir'] or '.'
  store_cmp = FileStoreComparator2(store_file, target_dir)
  store_cmp.compare()



if __name__ == "__main__":
  main()
