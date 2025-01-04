#!/usr/bin/env python3
# coding: utf-8

import yaml
from datetime import *
import glob
import os
from pprint import *

'''
TODO: EXCLUDE:
/sys/fs/cgroup
/tmp
/var/log
/var/tmp
/var/lib/openmediavault/rrd
/var/spool
/var/lib/rrdcached
/var/lib/monit
/var/cache/samba
/var/lib/mosquitto
/run/user/1000
'''


searchmask = '*'

# shell_lib
def time_trim_ms(t: datetime):
  return datetime(t.year, t.month, t.day, t.hour, t.minute, t.second)

# shell_lib - example
def event_filter(path, isdir):
    filename = "/" + "/".join(path)

    if isdir and os.path.islink(filename):
        return False
    if isdir and (filename=='/sys' or filename=='/run' or filename=='/proc' or filename=='/dev'):
        return False
    if isdir:
        return True

    if isdir==False:
        filetime = datetime.fromtimestamp( os.path.getmtime(filename) )
        if filetime > datetime.now() - timedelta(days=1):
            return True
        else:
            return False
    # default
    return True

# shell_lib?
def enumfiles(targetdir, path: list):
    global searchmask
    olddir = os.getcwd()
    try:
      #TODO: targetdir_path = Path(targetdir); for p in targetdir_path.rglob(searchmask):
      os.chdir(targetdir)
      for f in glob.glob(searchmask):
        if os.path.isfile(f):
          if event_filter(path+[f], False):
            filetime = time_trim_ms(datetime.fromtimestamp( os.path.getmtime(f) ) )
            print( str(filetime), "/".join(path+[f]))

        if os.path.isdir(f) and event_filter(path+[f], True):
          enumfiles(f, path+[f]) # <- RECURSION!
        #if os.path.isdir(f) and event_filter(path+[f], True):
    finally:
      os.chdir(olddir)


def main():
  # параметры
  # ... options = docopt(usage)

  enumfiles('/', [])


if __name__ == "__main__":
  main()

