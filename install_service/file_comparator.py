# ver 2
# 2022.05.03

import yaml
import datetime
import glob
import os
from pprint import *

"""

TODO:
    все file_name/path переделать с list/string на Path.

TODO:

сделать обработчик событий - логгер изменений. Создает список изменений которые были обнаруженны при запуске FileStoreComparator.
с последующей возможностью запуска процедур "event_*" идентичных FileStoreComparator, но которые вызываются из переданного списка.
таким образом появляется промежуточное звено.
сначала FileStoreComparator создает список.
затем список как-либо обрабатывается.
затем список передается для вызова всех процедур "event_*".


сделать особый объект - синхронизатор изменений.
Берет 2 (или больше) списка изменений, и начинает синхронизацию дирикторий.


сделать объект events с собранием всем возможных event


добавить поддержку:
https://pypi.org/project/igittigitt/
A spec-compliant gitignore parser for Python
вытащить в отдельный файл.

перенести работу с yaml в отдельный файл.
тоесть по умолчанию реализация save/load должна быть пустая.

------------------

TODO:

сделать особую версию - тройной компаратор.
сравнивает с БД сразу 2 директории.
при этом поведении следующее:

наличие файлов:
   N; лист ; дир1 ; дир2 ;
   7; есть ; есть ; есть ; нет изменений.
   6; есть ; есть ; нет  ; удален, удалить из дир1.
   5; есть ; нет  ; есть ; удален, удалить из дир2.
   4; есть ; нет  ; нет  ; удален.
   3; нет  ; есть ; есть ; появился, скопировать в ди1 и дир2.
   2; нет  ; есть ; нет  ; появился, скопировать в дир2.
   1; нет  ; нет  ; есть ; появился, скопировать в дир1.
   0; нет  ; нет  ; нет  ; -

изменение файлов:
   -; есть ; изм  ; есть ; изменился, обновить в дир2.
   -; есть ; есть ; изм  ; изменился, обновить в дир1.
   -; *    ; изм  ; изм  ; конфликт, поздний файл переименовать и скопировать, более свежий - записать дату в БД.
   -; изм  ; есть ; есть ; ошибка в базе данных. обновить базу данных.

----------------


"""

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
    #todo: normalize path. Example: targetdir='/etc', targetdir='etc', targetdir='/etc/'
    self.targetdir  = targetdir # watching directory
    self.searchmask = '*'
    self.file_extension = '*'
    self.on_added = None
    self.on_removed = None
    self.on_changed = None
    self.on_changed_store_error = None
    self.on_filter = None
    self.recursion = True

  def get_file_list_and_date(self, targetdir, path):
    ''' Получить список всех файлов и даты их модификации.
    Возвращает дерево из dict.
    TODO: в процессе работы делает смену каталогов - хороший алгоритм должен работать без смены каталогов, но пока сгодится и так.
    '''
    r = {}
    olddir = os.getcwd()
    try:
      os.chdir(targetdir)
      for f in glob.glob(self.searchmask):
        if os.path.isfile(f):
          if self.file_extension=='*' or os.path.splitext(f)[1][1:]==self.file_extension:
            if self.event_filter(path+[f], False):
              # add file to file list
              r.update({f: time_trim_ms(datetime.datetime.fromtimestamp(os.path.getmtime(f))) })

        if os.path.isdir(f) and self.recursion and self.event_filter(path+[f], True):
          dirlist = self.get_file_list_and_date(f, path+[f]) # <- RECURSION!
          if dirlist != {}:
            # add dir to file list
            r.update({f: dirlist })
    finally:
      os.chdir(olddir)
    return r

  def event_filter(self, path, isdir):
    # see also: https://pypi.org/project/igittigitt/
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
      `path` - LIST!!! - Need change to `Path`
    '''

    # enum 'store' and find in 'files'
    for f,v in store.copy().items():
      datech = files.get(f, None)

      # compare dir
      if self.recursion and isinstance(datech,dict) and isinstance(v,dict):
        self.compare_list(v, datech, path+[f]) # <- RECURSION
        # remove from 'files' list - nedded for next comparsion step.
        del files[f]
        continue

      # compare files
      if datech==None:
        # present in 'store', none in 'files' - file removed
        del store[f]
        self.event_file_removed(path+[f])
      # if isinstance... type(datech)!=type(v) ... - file_to_dir, dir_to_file....
      else:
        #todo: WIP!
        if isinstance(datech,dict):
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

