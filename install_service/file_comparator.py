import yaml
import datetime
import glob
import os

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

  def __init__(self, store_file: str, targetdir = '.\\', searchmask = '*'):
    self.store_file = store_file
    self.encoding='utf-8'
    self.targetdir  = targetdir
    self.searchmask = searchmask
    self.on_added = None
    self.on_removed = None
    self.on_changed = None
    self.on_changed_store_error = None

  def get_file_list_and_date(self):
    ''' Получить список файлов и даты их модификации
    Возвращает dict
    '''
    r = {}
    olddir = os.getcwd()
    try:
      os.chdir(self.targetdir)
      for f in glob.glob(self.searchmask):
        if os.path.isfile(f):
          r.update({f: time_trim_ms(datetime.datetime.fromtimestamp(os.path.getmtime(f))) })
    finally:
      os.chdir(olddir)
    return r

  def event_file_added(self, file_name):
    if callable(self.on_added):
      self.on_added(file_name)

  def event_file_removed(self, file_name):
    if callable(self.on_removed):
      self.on_removed(file_name)

  def event_file_changed(self, file_name):
    if callable(self.on_changed):
      self.on_changed(file_name)

  def event_file_changed_store_error(self, file_name):
    if callable(self.on_changed_store_error):
      self.on_changed_store_error(file_name)

  def compare_list(self, store: dict, files: dict):
    '''
    'store' be changed to actual state!
    'files' be changed!
    '''

    # enum 'store' and find in 'files'
    for f,v in store.copy().items():
      datech = files.get(f, None)
      if datech==None:
        # present in 'store', none in 'files' - file removed
        del store[f]
        self.event_file_removed(f)
      else:
        # present in 'store' and 'files'.
        # remove from 'files' list - nedded for next comparsion step.
        del files[f]
        # analize time.
        if datech > v:
          # present in 'store' and 'files' by datetime changed
          store[f]=datech
          self.event_file_changed(f)
        else:
          if datech < v:
            # present in 'store' and 'files' by datetime changed, but not correct
            store[f]=datech
            self.event_file_changed_store_error(f)
    # enum lefted 'files' - added files.
    for k,v in files.items():
      store.update({k:v})
      self.event_file_added(k)

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
    files = self.get_file_list_and_date()
    self.compare_list(store, files)
    self.save_store(store)

