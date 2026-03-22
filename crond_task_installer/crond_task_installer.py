#!/usr/bin/env python3

usage = '''
Usage: crond_task_installer.py [--dir=PATH] [--store=FILE]

Options:
  --dir=PATH    path to directory from copy crond file
  --store=FILE  name of YAML file where stored files info [default: cron_list.yaml]
'''

from docopt import docopt  # pip3 install docopt
import file_comparator
from pprint import *
from subprocess import *
from pathlib import Path

def sh(command: str, *params):
  try:
    c = None
    command = command.format(*params)
    print('Run:', command)
    c = run(command, shell=True)
    if c != None and c.stdout != '' and c.returncode != 0:
      print(c.stdout)
  except FileNotFoundError as e:
    print('Error: FileNotFound. Command: "' + command + '"')
  except Exception as e:
    print('Error: ' + str(type(e)) + '. Command: "' + command + '"')
    if c != None and c.stderr != '':
      print('Output:')
      print(c.stderr)


class FileEventsCrond:
  def file_added(self, path: Path) -> None:
    file_name = path.as_posix()
    print('Added:', file_name)
    sh('cp {1}{0} /etc/cron.d/', file_name, self.dir)
    sh('sudo systemctl reload-or-restart cron.service')

  def file_removed(self, path: Path) -> None:
    file_name = path.as_posix()
    print('Removed:', file_name)
    sh('rm /etc/cron.d/{0}', file_name)
    sh('sudo systemctl reload-or-restart cron.service')

  def file_changed(self, path: Path) -> None:
    file_name = path.as_posix()
    print('Changed:', file_name)
    sh('cp {1}{0} /etc/cron.d/', file_name, self.dir)
    sh('sudo systemctl reload-or-restart cron.service')

  def file_changed_store_error(self, path: Path) -> None:
    file_name = path.as_posix()
    print('Store error:', file_name)
    sh('sudo systemctl reload-or-restart cron.service')


def main():
  options = docopt(usage)

  print('Install crond. Ver:', version)  # version не определён в исходном коде
  print('lib: file_comparator. Ver:', file_comparator.version)

  if options['--store_cron'] is not None and options['--dir_cron'] is not None:
    print('Begin crond.')
    event = FileEventsCrond()
    event.dir = options['--dir_cron']
    store_cmp = file_comparator.FileStoreComparator(options['--store_cron'], options['--dir_cron'])
    store_cmp.on_added = event.file_added
    store_cmp.on_removed = event.file_removed
    store_cmp.on_changed = event.file_changed
    store_cmp.on_changed_store_error = event.file_changed_store_error
    store_cmp.compare()

  print('End.')


if __name__ == '__main__':
  main()
