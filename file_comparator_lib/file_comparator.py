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
    self.on_added = None
    self.on_removed = None
    self.on_changed = None
    self.on_changed_store_error = None
    self.on_filter = None
    self.recursion = True
    self.follow_symlinks = True
    self._store_root = None

  def on_store_updated(self, change_type: str, key: str, values: dict) -> None:
    """
    Hook called right after the store is mutated.
    Override in subclasses (default: do nothing).

    :param change_type: One of: 'added', 'removed', 'updated', 'store_error'.
    :param key: POSIX-like key (e.g. 'dir/file.ext') identifying the changed entry.
    :param values: The store metadata dict for this key (a live reference).
                   You can mutate it to persist custom fields into YAML.
    """
    pass

  def _key_to_path(self, key: str) -> Path:
    """
    Convert store key to Path suitable for event callbacks.
    Directory keys end with '/'.
    """
    if str(key).endswith('/'):
      return Path(str(key)[:-1])
    return Path(str(key))

  def _normalize_key(self, key: str, meta: dict = None) -> str:
    """
    Normalize keys to POSIX style and ensure directory keys end with '/'.
    """
    k = str(key or '').strip().replace('\\', '/')
    while k.startswith('./'):
      k = k[2:]
    while '//' in k:
      k = k.replace('//', '/')

    is_dir = k.endswith('/') or (isinstance(meta, dict) and meta.get('type') == 'dir')
    if is_dir:
      k = k.rstrip('/') + '/'
    else:
      k = k.rstrip('/')
    return k

  def _mtime_to_epoch(self, value) -> int:
    """
    Convert mtime representation to epoch seconds (int).
    Accepts FSS string, int, float, or numeric string.
    """
    if isinstance(value, int):
      return int(value)
    if isinstance(value, float):
      return int(value)
    if isinstance(value, str):
      try:
        return fss_to_epoch(value)
      except Exception:
        try:
          return int(value)
        except Exception:
          return 0
    return 0

  def event_filter(self, path: Path, isdir: bool) -> bool:
    # see also: https://pypi.org/project/igittigitt/
    if callable(self.on_filter):
      return self.on_filter(path, isdir)
    else:
      return True

  def get_fs_map(self, targetdir: Path) -> dict:
    """
    Scan filesystem and return flat-map: key -> meta dict.
    - Files: key 'a/b/c.txt', meta {'type': 'file', 'mtime': '<FSS>'}
    - Dirs:  key 'a/b/c/',   meta {'type': 'dir'}
    """
    out: dict = {}

    def scan_dir(abs_dir: Path, rel_dir: Path) -> None:
      if rel_dir.parts and self.event_filter(rel_dir, True):
        out[rel_dir.as_posix().rstrip('/') + '/'] = {'type': 'dir'}

      for child in abs_dir.iterdir():
        rel_path = rel_dir / child.name

        if (not self.follow_symlinks) and child.is_symlink():
          continue

        if child.is_dir():
          if (not self.recursion) or (not self.event_filter(rel_path, True)):
            continue
          scan_dir(child, rel_path)
          continue

        if child.is_file():
          if not self.event_filter(rel_path, False):
            continue
          out[rel_path.as_posix()] = {
            'type': 'file',
            'mtime': epoch_to_fss(epoch_from_mtime(child)),
          }

    scan_dir(targetdir.resolve(), Path('.'))
    return out

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

  def _remove_dir_tree(self, store: dict, dir_key: str, keys_under: list = None) -> None:
    """
    Remove a directory entry and everything under it from the flat-map store.

    Directory keys must end with '/' (e.g. 'a/b/c/').
    Removal events are fired leaf-first (deepest keys first).
    """
    dir_key = str(dir_key or '')
    if not dir_key.endswith('/'):
      dir_key = dir_key.rstrip('/') + '/'

    if keys_under is None:
      keys_under = [k for k in store.keys() if k == dir_key or k.startswith(dir_key)]
      # Leaf-first: remove deepest nodes first.
      keys_under.sort(key=len, reverse=True)
    for k in keys_under:
      values = store.pop(k, None)
      if values is None:
        continue
      self.on_store_updated('removed', k, values)
      self.event_file_removed(self._key_to_path(k))

  def compare_map(self, store: dict, disk: dict) -> None:
    """
    Compare and mutate store (flat-map key -> meta dict) to match disk.
    This method fires callbacks and calls on_store_updated() after each mutation.
    """
    # Pass 1: removed directories (cascade).
    removed_dirs = [k for k in store.keys() if str(k).endswith('/') and k not in (disk or {})]
    removed_dirs.sort(key=len, reverse=True)  # deep-first

    for dir_key in removed_dirs:
      if dir_key not in store:
        continue
      self._remove_dir_tree(store, dir_key)

    # Pass 2: removed remaining keys (mostly files).
    removed_keys = [k for k in store.keys() if k not in disk]
    removed_keys.sort(key=len, reverse=True)
    for k in removed_keys:
      values = store.pop(k, None)
      if values is None:
        continue
      self.on_store_updated('removed', k, values)
      self.event_file_removed(self._key_to_path(k))

    # Added keys.
    for k, disk_meta in (disk or {}).items():
      if k in store:
        continue
      values = dict(disk_meta) if isinstance(disk_meta, dict) else {}
      store[k] = values
      self.on_store_updated('added', k, values)
      self.event_file_added(self._key_to_path(k))

    # Updated/store_error for files.
    for k, disk_meta in (disk or {}).items():
      if k not in store:
        continue
      if k.endswith('/'):
        # Existence-only for directories.
        continue

      if not isinstance(disk_meta, dict):
        continue
      if disk_meta.get('type') != 'file':
        continue

      store_meta = store.get(k, {})
      if not isinstance(store_meta, dict):
        store_meta = {}
        store[k] = store_meta

      disk_epoch = self._mtime_to_epoch(disk_meta.get('mtime'))
      store_epoch = self._mtime_to_epoch(store_meta.get('mtime'))

      if disk_epoch > store_epoch:
        store_meta.setdefault('type', 'file')
        store_meta['mtime'] = disk_meta.get('mtime')
        self.on_store_updated('updated', k, store_meta)
        self.event_file_changed(self._key_to_path(k))
      elif disk_epoch < store_epoch:
        store_meta.setdefault('type', 'file')
        store_meta['mtime'] = disk_meta.get('mtime')
        self.on_store_updated('store_error', k, store_meta)
        self.event_file_changed_store_error(self._key_to_path(k))

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
    if not isinstance(raw, dict):
      raw = {}

    store_map: dict = {}
    for key, meta in raw.items():
      if isinstance(meta, dict):
        values = meta
      elif isinstance(meta, int):
        values = {'type': 'file', 'mtime': epoch_to_fss(meta)}
      elif isinstance(meta, str):
        values = {'type': 'file', 'mtime': meta}
      else:
        continue

      norm_key = self._normalize_key(key, values)
      values.setdefault('type', 'dir' if norm_key.endswith('/') else 'file')
      store_map[norm_key] = values

    return store_map

  def save_store(self, store):
    data = yaml.dump(store or {}, default_flow_style=False, allow_unicode=True)
    if GetFileContent(self.store_file, encoding=self.encoding) != data:
      with open(self.store_file, 'w', encoding=self.encoding) as f:
        f.write(data)

  def compare(self):
    store = self.load_store()
    self._store_root = store
    disk = self.get_fs_map(self.targetdir)
    self.compare_map(store, disk)
    self.save_store(store)

