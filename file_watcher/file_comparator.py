# ver 2

import yaml
import datetime
import glob
import os
from pprint import *

def time_trim_ms(t: datetime.datetime):
  return datetime.datetime(t.year, t.month, t.day, t.hour, t.minute, t.second)

def GetFileContent(fileName, encoding='utf-8'):
  """ возвращает строку с текстовым содержимым файла (в нужной кодировке) """
  try:
    with open(fileName,'r', encoding=encoding) as f:
      return str(f.read())
  except IOError:
    return ''

class FileStoreComparator:

  def __init__(self, store_file: str, targetdir = '.\\'):
    self.store_file = store_file
    self.encoding='utf-8'
    self.targetdir  = targetdir
    self.searchmask = '*'
    self.file_extension = '*'
    self.on_added = None
    self.on_removed = None
    self.on_changed = None
    self.on_changed_store_error = None
    self.on_filter = None
    self.recursion = True

  def get_file_list_and_date(self, targetdir, path):
    ''' Получить список файлов и даты их модификации
    Возвращает dict
    Note: в процессе работы делает смену каталогов - хороший алгоритм должен работать без смены каталогов, но пока сгодится и так.
    '''
    r = {}
    olddir = os.getcwd()
    try:
      os.chdir(targetdir)
      for f in glob.glob(self.searchmask):
        if os.path.isfile(f):
          if self.file_extension=='*' or os.path.splitext(f)[1][1:]==self.file_extension:
            if self.event_filter(path+[f], False):
              r.update({f: time_trim_ms(datetime.datetime.fromtimestamp(os.path.getmtime(f))) })

        if os.path.isdir(f) and self.recursion and self.event_filter(path+[f], True):
          dirlist = self.get_file_list_and_date(f, path+[f]) # <- RECURSION!
          if dirlist != {}:
            r.update({f: dirlist })
    finally:
      os.chdir(olddir)
    return r

  def event_filter(self, path, isdir):
    if callable(self.on_filter):
      return self.on_filter(path, isdir)
    else:
      return True

  def event_file_added(self, path):
    if callable(self.on_added):
      self.on_added(path)

  def event_file_removed(self, path):
    if callable(self.on_removed):
      self.on_removed(path)

  def event_file_changed(self, path):
    if callable(self.on_changed):
      self.on_changed(path)

  def event_file_changed_store_error(self, path):
    if callable(self.on_changed_store_error):
      self.on_changed_store_error(path)

  def compare_list(self, store: dict, files: dict, path: list):
    '''
    in-out param:
      'store' dict be changed to actual state!
      'files' dict be changed!
    '''

    # enum 'store' and find in 'files'
    for f,v in store.copy().items():
      datech = files.get(f, None)

      # compare dir
      if self.recursion and type(datech)==dict and type(v)==dict:
        self.compare_list(v, datech, path+[f]) # <- RECURSION
        # remove from 'files' list - nedded for next comparsion step.
        del files[f]
        continue

      # compare files
      if datech==None:
        # present in 'store', none in 'files' - file removed
        del store[f]
        self.event_file_removed(path+[f])
      # if type(datech)!=type(v) ... - file_to_dir, dir_to_file....
      else:
        #todo: WIP!
        if type(datech)==dict:
          continue

        # present in 'store' and 'files'.
        # remove from 'files' list - nedded for next comparsion step.
        del files[f]
        # analize time.
        if datech > v:
          # present in 'store' and 'files' by datetime changed
          store[f]=datech
          self.event_file_changed(path+[f])
        else:
          if datech < v:
            # present in 'store' and 'files' by datetime changed, but not correct
            store[f]=datech
            self.event_file_changed_store_error(path+[f])
    # enum lefted 'files' - added files.
    for k,v in files.items():
      store.update({k:v})
      self.event_file_added(path+[k])

  def load_store(self):
    try:
      with open(self.store_file, 'r', encoding=self.encoding) as f:
        store = yaml.load(f)
        if store==None:
          store = {}
    except:
      store = {}
    return store

  def save_store(self, store):
    data = yaml.dump(store, default_flow_style=False, allow_unicode=True)
    if GetFileContent(self.store_file, encoding=self.encoding) != data:
      with open(self.store_file, 'w', encoding=self.encoding) as f:
        f.write(data)

  def compare(self):
    store = self.load_store()
    files = self.get_file_list_and_date(self.targetdir, [])
    self.compare_list(store, files, [])
    self.save_store(store)

