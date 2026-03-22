version = 2.2
# 2022.05.09

import yaml # pip3 install pyyaml
import datetime
import time
import glob
import os
from pathlib import Path
from pprint import *
from typing import Union


"""

TODO:
    все file_name/path переделать с list/string на Path.

TODO:
    В YAML ключи путей разбиваются по '/', т.е. ожидается POSIX-разделитель.
    На Windows (обратные слэши) это может давать несостыковки: сканер файлов
    берет имена из glob/os, а они зависят от платформы. Нужна нормализация путей
    (единый формат для store и для файловой системы).

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

def fss_to_tree(fss_map: dict) -> dict:
  """
  Convert flat FSS-YAML mapping (path -> metadata) into nested tree.
  Only entries with type: file and mtime are considered.
  """
  tree: dict = {}
  for full_path, meta in (fss_map or {}).items():
    if not isinstance(meta, dict):
      continue
    if meta.get('type') != 'file':
      continue
    mtime_str = meta.get('mtime')
    if not mtime_str:
      continue
    try:
      mtime_epoch = fss_to_epoch(mtime_str)
    except Exception:
      continue
    parts = [p for p in str(full_path).split('/') if p]
    if not parts:
      continue
    node = tree
    for part in parts[:-1]:
      node = node.setdefault(part, {})
    node[parts[-1]] = mtime_epoch
  return tree


def tree_to_fss(store_tree: dict) -> dict:
  """
  Convert nested store tree into flat FSS-YAML mapping (path -> metadata).
  """
  fss_map: dict = {}

  def walk(node: dict, prefix: list):
    for name, value in (node or {}).items():
      current_path = prefix + [name]
      if isinstance(value, dict):
        walk(value, current_path)
      else:
        # leaf file: value is epoch seconds
        try:
          ts = int(value)
        except (TypeError, ValueError):
          continue
        path_str = '/'.join(current_path)
        fss_map[path_str] = {
          'type': 'file',
          'mtime': epoch_to_fss(ts),
        }

  walk(store_tree or {}, [])
  return fss_map


def time_trim_ms(t: datetime.datetime):
  return datetime.datetime(t.year, t.month, t.day, t.hour, t.minute, t.second)


def epoch_from_mtime(path: Union[str, Path]) -> int:
  """
  Return file mtime in whole seconds since epoch.
  """
  return int(Path(path).stat().st_mtime)


def epoch_to_fss(ts: int) -> str:
  """
  Convert epoch seconds to FSS timestamp string: YYYY-MM-DD_HH:MM:SSZ (UTC).
  """
  dt = datetime.datetime.utcfromtimestamp(ts)
  return dt.strftime('%Y-%m-%d_%H:%M:%SZ')


def fss_to_epoch(ts: str) -> int:
  """
  Parse FSS timestamp string (YYYY-MM-DD_HH:MM:SSZ) to epoch seconds.
  """
  dt = datetime.datetime.strptime(ts, '%Y-%m-%d_%H:%M:%SZ')
  return int(dt.replace(tzinfo=datetime.timezone.utc).timestamp())

def GetFileContent(fileName: Union[str, Path], encoding: str = 'utf-8'):
  """ возвращает строку с текстовым содержимым файла (в нужной кодировке) """
  try:
    with open(Path(fileName), 'r', encoding=encoding) as f:
      return str(f.read())
  except IOError:
    return ''

class FileStoreComparator:

  def __init__(self, store_file: Union[str, Path], targetdir: Union[str, Path] = '.\\'):
    self.store_file = Path(store_file)
    self.encoding='utf-8'
    #todo: normalize path. Example: targetdir='/etc', targetdir='etc', targetdir='/etc/'
    self.targetdir = Path(targetdir) # watching directory
    self.searchmask = '*'
    self.file_extension = '*'
    self.on_added = None
    self.on_removed = None
    self.on_changed = None
    self.on_changed_store_error = None
    self.on_filter = None
    self.recursion = True
    self._store_root = None

  def on_store_updated(self, change_type: str, key: str) -> None:
    """
    Hook called right after the store is mutated.
    Override in subclasses (default: do nothing).

    :param change_type: One of: 'added', 'removed', 'updated', 'store_error'.
    :param key: POSIX-like key (e.g. 'dir/file.ext') identifying the changed entry.
    """
    pass

  def get_file_list_and_date(self, targetdir: Path, path: Path):
    ''' Получить список всех файлов и даты их модификации.
    Возвращает дерево из dict.
    '''
    r = {}
    for entry in targetdir.glob(self.searchmask):
      entry_name = entry.name
      rel_path = path / entry_name

      if entry.is_file():
        if self.file_extension == '*' or entry.suffix[1:] == self.file_extension:
          if self.event_filter(rel_path, False):
            # add file to file list (store epoch seconds)
            r.update({entry_name: epoch_from_mtime(entry)})

      if entry.is_dir() and self.recursion and self.event_filter(rel_path, True):
        dirlist = self.get_file_list_and_date(entry, rel_path) # <- RECURSION!
        if dirlist != {}:
          # add dir to file list
          r.update({entry_name: dirlist})
    return r

  def event_filter(self, path: Path, isdir: bool) -> bool:
    # see also: https://pypi.org/project/igittigitt/
    if callable(self.on_filter):
      return self.on_filter(path, isdir)
    else:
      return True

  def event_file_added(self, path: Path) -> None:
    if callable(self.on_added):
      self.on_added(path)

  def event_file_removed(self, path: Path) -> None:
    if callable(self.on_removed):
      self.on_removed(path)

  def event_file_changed(self, path: Path) -> None:
    if callable(self.on_changed):
      self.on_changed(path)

  def event_file_changed_store_error(self, path: Path) -> None:
    if callable(self.on_changed_store_error):
      self.on_changed_store_error(path)

  def compare_list(self, store: dict, files: dict, path: Path):
    '''
    in-out param:
      'store' dict be changed to actual state!
      'files' dict be changed!
      `path` - relative `Path` within watched directory.
    '''

    # enum 'store' and find in 'files'
    # f - file name
    # v - file data in store
    for f,v in store.copy().items():
      datech = files.get(f, None)

      # compare dir
      if self.recursion and isinstance(datech, dict) and isinstance(v, dict):
        self.compare_list(v, datech, path / f) # <- RECURSION
        # remove from 'files' list - nedded for next comparsion step.
        del files[f]
        continue

      # compare files
      if datech==None:
        # present in 'store', none in 'files' - file removed
        del store[f]
        rel = path / f
        self.on_store_updated('removed', rel.as_posix())
        self.event_file_removed(rel)
      # if isinstance... type(datech)!=type(v) ... - file_to_dir, dir_to_file....
      else:
        #todo: WIP! (WTF??? - я забыл что это)
        if isinstance(datech, dict):
          continue

        # present in 'store' and 'files'.
        # remove from 'files' list - nedded for next comparsion step.
        del files[f]
        # analize time.
        # DEBUG:
        #print('data in disk ', datech)
        #print('data in store', v)
        if datech > v:
          # present in 'store' and 'files' by datetime changed
          store[f]=datech
          rel = path / f
          self.on_store_updated('updated', rel.as_posix())
          self.event_file_changed(rel)
        else:
          if datech < v:
            # present in 'store' and 'files' by datetime changed, but not correct
            store[f]=datech
            rel = path / f
            self.on_store_updated('store_error', rel.as_posix())
            self.event_file_changed_store_error(rel)
    # end _for_ in store

    # enum lefted 'files' - added files.
    for k,v in files.items():
      store.update({k:v})
      rel = path / k
      self.on_store_updated('added', rel.as_posix())
      self.event_file_added(rel)


  def load_store(self):
    try:
      with open(self.store_file, 'r', encoding=self.encoding) as f:
        raw = yaml.safe_load(f)
        if raw is None:
          raw = {}
    except IOError as e:
      # TODO: except - нужна более обширная обработка.
      print('I/O error({0}): {1}'.format(e.errno, e.strerror))
      raw = {}
    # raw is FSS-YAML flat mapping; convert to internal tree.
    store_tree = fss_to_tree(raw)
    return store_tree

  def save_store(self, store):
    # Convert internal tree to FSS-YAML flat mapping.
    fss_map = tree_to_fss(store or {})
    data = yaml.dump(fss_map, default_flow_style=False, allow_unicode=True)
    if GetFileContent(self.store_file, encoding=self.encoding) != data:
      with open(self.store_file, 'w', encoding=self.encoding) as f:
        f.write(data)

  def compare(self):
    store = self.load_store()
    self._store_root = store
    files = self.get_file_list_and_date(self.targetdir, Path())
    self.compare_list(store, files, Path())
    self.save_store(store)

