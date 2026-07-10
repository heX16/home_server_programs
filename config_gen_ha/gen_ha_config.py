"""Generate Home Assistant YAML config from a signals CSV file.

Usage:
  gen_ha_config.py --csv=<path> --out=<dir>
  gen_ha_config.py (-h | --help)

Options:
  --csv=<path>   Input CSV file path.
  --out=<dir>    Output directory for generated Home Assistant YAML.
  -h, --help     Show this help message and exit.
"""

import sys
import csv
import io
import copy
import re
import zlib
import yaml
from pathlib import Path
from docopt import docopt

OUTPUT_SUBDIRS = ('mqtt', 'customize', 'lovelace')

DASHBOARD_ROOM_RESERVED = 'group_reserved'
DASHBOARD_ROOM_OTHER = 'Other'


def norm_col(cell):
  return cell.strip().split('\n')[0].strip()


def norm_tab(value):
  if value is None:
    return ''
  return str(value).strip()


def slugify_ascii(value):
  """
  Convert an arbitrary tab name to a filename-safe ASCII slug.

  Notes:
  - keeps only [a-z0-9-]
  - converts whitespace/underscores to '-'
  - removes everything else (including Cyrillic); uses deterministic fallback if empty

  Examples:
   - '  Main  Tab  '   -> 'main-tab'
   - '__Main__Tab__'   -> 'main-tab'
   - '---main---'      -> 'main'
   - 'Main---Tab'      -> 'main-tab'
   - 'main..tab!!'     -> 'maintab'
   - 'R&D / Lab'       -> 'rd-lab'
   - 'Кухня'           -> 'x????????' (CRC32-based fallback)
   - 'Свет 1'          -> '1'
   - 'Kitchen Кухня'   -> 'kitchen'
   - 'Kitchen 2'       -> 'kitchen-2'
   - 'Room_Кухня_2'    -> 'room-2'
  """
  raw = norm_tab(value).lower()
  raw = re.sub(r'[\s_]+', '-', raw)
  raw = re.sub(r'[^a-z0-9-]+', '', raw)
  # Collapse multiple '-' and trim them from both ends.
  raw = re.sub(r'-{2,}', '-', raw).strip('-')
  if raw:
    return raw
  crc = zlib.crc32(norm_tab(value).encode('utf-8')) & 0xffffffff
  return f'x{crc:08x}'


def unique_slug(base_slug, used_slugs):
  if base_slug not in used_slugs:
    used_slugs.add(base_slug)
    return base_slug
  i = 2
  while True:
    candidate = f'{base_slug}-{i}'
    if candidate not in used_slugs:
      used_slugs.add(candidate)
      return candidate
    i += 1


def build_lovelace_rooms_dashboard_for_tab(signals_list, tab_value, tab_slug):
  filtered = list(filter(lambda x: norm_tab(x.get('tab', '')) == tab_value, signals_list))
  dashboard = build_lovelace_rooms_dashboard(filtered)
  dashboard = dict(dashboard)
  dashboard['title'] = f'{tab_value}'
  if dashboard.get('views'):
    dashboard['views'] = [dict(dashboard['views'][0])]
    dashboard['views'][0]['path'] = f'rooms-{tab_slug}'
  return dashboard


SIGNALS_CSV_COLUMNS = {
  'type': 'Тип',
  'name': 'Имя в интерфейсе',
  'namesig': 'Наименование сигнала',
  'sig': 'sig',
  'ns': 'N',
  'mqtt': ('MQTT name', 'Путь MQTT'),
  'group': 'Группа',
  'logic': 'Logic',
  'module': 'Модуль',
  'box': 'Я.',
  'tab': 'Вкладка',
}

OPTIONAL_SIGNALS_CSV_COLUMNS = {'logic'}


def parse_signals_csv_header(row):
  """Map the first CSV row to semantic column indices."""
  col_to_idx = {norm_col(cell): idx for idx, cell in enumerate(row)}
  indices = {}

  for key, header in SIGNALS_CSV_COLUMNS.items():
    if isinstance(header, tuple):
      idx = next((col_to_idx[name] for name in header if name in col_to_idx), None)
    else:
      idx = col_to_idx.get(header)
    indices[key] = idx

  missing = [
    key for key, idx in indices.items()
    if idx is None and key not in OPTIONAL_SIGNALS_CSV_COLUMNS
  ]
  if missing:
    seen_headers = ', '.join(col_to_idx.keys())
    raise ValueError(
      f'Missing required CSV columns: {", ".join(missing)}. '
      f'Available headers: {seen_headers}'
    )

  return indices


# item: n,name,mqtt
# result: {name: data}
def ha_gen_customize_node(item):
  # Example:
  #switch.1:
  #  friendly_name: "ванная"
  data = {
    item['sysname']:
    { 'friendly_name': item['name']}
  }
  return data

# item: n,name,mqtt
def ha_gen_binary_sensor_node(item):
  # MQTT integration (list per item) style:
  # - binary_sensor:
  #     name: '...'
  #     unique_id: '...'
  #     default_entity_id: binary_sensor.<n>
  #     state_topic: '...'
  #     payload_on: '1'
  #     payload_off: '0'
  return {
    'binary_sensor': {
      'name': item['name'],
      'unique_id': f'di_{item["n"]}',
      'default_entity_id': item['sysname'],
      'state_topic': item['mqtt'] + '/p',
      'payload_on': '1',
      'payload_off': '0',
    }
  }

# item: n,name,mqtt
def ha_gen_switch_node(item):
  # Example:
  #- platform: mqtt
  #  name: 3
  #  state_topic: "extbus/8/5/p"
  #  command_topic: "extbus/8/5/w"
  #  payload_on:  "1"
  #  payload_off: "0"
  return {
    'switch': {
      'name': item['name'],
      'unique_id': f'do_{item["n"]}',
      'default_entity_id': item['sysname'],
      'state_topic': item['mqtt'] + '/p',
      'command_topic': item['mqtt'] + '/w',
      'payload_on': '1',
      'payload_off': '0',
    }
  }


def duplicate_do_as_system_switch(n):
  """
  Create a "system" duplicate of a DO item.

  System switches use technical names (box/signal metadata) and are written to mqtt/do_sys.yaml.
  They are excluded from the generated Lovelace rooms dashboard.
  """

  n['n']=n['n']+'_sys'
  n['name']=n['box']+'.'+n['ns']+' '+n['namesig']
  n['sysname'] = 'switch.'+n['n']
  n['group'] = 'Box'+n['box']
  n['tab'] = 'Sys'
  n['system'] = True
  return n


def room_name_for_dashboard(item):
  """Map CSV group column to a Lovelace room card title."""
  group = str(item.get('group', '')).strip()
  if group == DASHBOARD_ROOM_RESERVED:
    return None
  if not group:
    return DASHBOARD_ROOM_OTHER
  return group


def dashboard_sort_key(item):
  """Stable sort inside a room: by box, signal number, then entity id."""
  box = str(item.get('box', ''))
  ns = str(item.get('ns', ''))
  try:
    ns_num = int(ns)
  except (TypeError, ValueError):
    ns_num = ns
  return (box, ns_num, item.get('n', ''))


def box_group_name(item):
  """Map a signal to a debug card group name based on its box number."""
  return 'Box' + str(item.get('box', '')).strip()


def debug_entity_row(entity, icon):
  """Build a Lovelace entity row with a fixed icon for state-colored display."""
  return {
    'entity': entity['sysname'],
    'name': entity['name'],
    'icon': icon,
  }


def build_lovelace_debug_entities_cards(signals_list, predicate, icon):
  """
  Build Lovelace entities cards grouped by box for the debug dashboard.

  Each card lists matching signals sorted by box/signal number.
  """
  groups = {}
  for item in signals_list:
    if not predicate(item):
      continue
    group = box_group_name(item)
    groups.setdefault(group, []).append(item)

  cards = []
  for group in sorted(groups.keys()):
    entities = sorted(groups[group], key=dashboard_sort_key)
    cards.append({
      'type': 'entities',
      'title': group,
      'show_header_toggle': False,
      'state_color': True,
      'entities': [debug_entity_row(entity, icon) for entity in entities],
    })
  return cards


def build_lovelace_debug_dashboard(signals_list):
  """
  Build Lovelace debug dashboard YAML: DI inputs and system DO duplicates.

  DI view groups binary_sensor.* by box. Sys DO view groups switch.*_sys by box.
  """
  di_cards = build_lovelace_debug_entities_cards(
    signals_list,
    lambda item: item['type'] == 'DI',
    'mdi:toggle-switch',
  )
  sys_do_cards = build_lovelace_debug_entities_cards(
    signals_list,
    lambda item: item['type'] == 'DO' and item.get('system', False),
    'mdi:lightbulb',
  )

  return {
    'title': 'Debug',
    'views': [
      {
        'title': 'DI',
        'path': 'debug-di',
        'icon': 'mdi:electric-switch',
        'cards': di_cards,
      },
      {
        'title': 'Sys DO',
        'path': 'debug-sys-do',
        'icon': 'mdi:lightbulb',
        'cards': sys_do_cards,
      },
    ],
  }


def build_lovelace_rooms_dashboard(signals_list):
  """
  Build Lovelace dashboard YAML: one view with entities cards per room.

  Includes only non-system DO switches. Rooms come from the CSV `Группа` column.
  """
  rooms = {}
  for item in signals_list:
    if item['type'] != 'DO':
      continue
    if item.get('system', False):
      continue
    room = room_name_for_dashboard(item)
    if room is None:
      continue
    rooms.setdefault(room, []).append(item)

  cards = []
  for room in sorted(rooms.keys()):
    entities = sorted(rooms[room], key=dashboard_sort_key)
    cards.append({
      'type': 'entities',
      'title': room,
      'entities': [entity['sysname'] for entity in entities],
    })

  return {
    'title': 'Rooms',
    'views': [
      {
        'title': 'Комнаты',
        'path': 'rooms',
        'icon': 'mdi:floor-plan',
        'cards': cards,
      }
    ],
  }


def ensure_output_dirs(out_dir):
  out_dir.mkdir(parents=True, exist_ok=True)
  for subdir in OUTPUT_SUBDIRS:
    (out_dir / subdir).mkdir(parents=True, exist_ok=True)


def read_signals_list(csv_path):
  # Read CSV file
  signals_list = []

  with open(csv_path, newline='', encoding='utf-8') as csvfile:
    datareader = csv.reader(csvfile, delimiter=';', quotechar='"')
    # next() consumes the first row as the CSV header;
    # the loop below starts from the second row
    indices = parse_signals_csv_header(next(datareader))

    for row in datareader:
      for idx, cell in enumerate(row):
        item = {
          'n': row[indices['sig']].strip().replace('.', '_'), # глобальный уникальный индификатор
          'ns': row[indices['ns']], # номер сигнала в ящике
          'name': row[indices['name']].strip(),
          'namesig': row[indices['namesig']].strip(),
          'group': row[indices['group']].strip(),
          'mqtt': row[indices['mqtt']].strip(),
          #'logic': row[indices['logic']],
          'type': row[indices['type']],
          'module': row[indices['module']],
          'box': row[indices['box']],
          'b_m': str(row[indices['box']])+'_'+str(row[indices['module']]),
          'system': False,
          'tab': row[indices['tab']],
        }
        if item['name']=='':
          item['name'] = item['namesig']

        if (idx == indices['type']) and (cell == 'DI'):
          item['sysname'] = 'binary_sensor.'+item['n']
          signals_list.append(item)
        if (idx == indices['type']) and (cell == 'DO'):
          item['sysname'] = 'switch.'+item['n']
          signals_list.append(item)

  return signals_list


def ha_gen_configs(signals_list, out_dir):
  # Write YAML file
  ensure_output_dirs(out_dir)
  legacy_rooms = out_dir / 'lovelace' / 'rooms-generated.yaml'
  if legacy_rooms.exists():
    legacy_rooms.unlink()

  # MQTT manual entities (Home Assistant integration `mqtt:`), list-per-item style.
  di_nodes = list(map(ha_gen_binary_sensor_node, filter(lambda x: x['type'] == 'DI', signals_list)))
  do_nodes = list(map(ha_gen_switch_node, filter(lambda x: (x['type'] == 'DO') and (not x.get('system', False)), signals_list)))
  do_sys_nodes = list(map(ha_gen_switch_node, filter(lambda x: (x['type'] == 'DO') and (x.get('system', False)), signals_list)))

  with io.open(out_dir / 'mqtt' / 'di.yaml', 'w', encoding='utf-8-sig') as outfile:
      yaml.dump(di_nodes, outfile, default_flow_style=False, allow_unicode=True)

  with io.open(out_dir / 'mqtt' / 'do.yaml', 'w', encoding='utf-8-sig') as outfile:
      yaml.dump(do_nodes, outfile, default_flow_style=False, allow_unicode=True)

  with io.open(out_dir / 'mqtt' / 'do_sys.yaml', 'w', encoding='utf-8-sig') as outfile:
      yaml.dump(do_sys_nodes, outfile, default_flow_style=False, allow_unicode=True)

  with io.open(out_dir / 'mqtt' / 'extra.yaml', 'w', encoding='utf-8-sig') as outfile:
      yaml.dump([], outfile, default_flow_style=False, allow_unicode=True)

  customize_nodes = {}
  for node in map(ha_gen_customize_node, signals_list):
    customize_nodes.update(node)
  with io.open(out_dir / 'customize' / 'customize_gen.yaml', 'w', encoding='utf-8-sig') as outfile:
      yaml.dump(customize_nodes, outfile, default_flow_style=False, allow_unicode=True)

  used_slugs = set()
  tabs_in_order = []
  for item in signals_list:
    tab = norm_tab(item.get('tab', ''))
    if not tab:
      continue
    if tab not in tabs_in_order:
      tabs_in_order.append(tab)

  for tab in tabs_in_order:
    base_slug = slugify_ascii(tab)
    tab_slug = unique_slug(base_slug, used_slugs)
    lovelace_dashboard = build_lovelace_rooms_dashboard_for_tab(signals_list, tab, tab_slug)
    out_name = f'tab-{tab_slug}.yaml'
    with io.open(out_dir / 'lovelace' / out_name, 'w', encoding='utf-8-sig') as outfile:
        yaml.dump(lovelace_dashboard, outfile, default_flow_style=False, allow_unicode=True)

  debug_dashboard = build_lovelace_debug_dashboard(signals_list)
  with io.open(out_dir / 'lovelace' / 'debug-generated.yaml', 'w', encoding='utf-8-sig') as outfile:
      yaml.dump(debug_dashboard, outfile, default_flow_style=False, allow_unicode=True)


def append_system_do_duplicates(signals_list):
  """
  Duplicate all DO items and append them back into `signals_list` as "system" switches.

  This is used to create an additional, purely technical set of switches:
  - the duplicated items get a modified `n`/`sysname` suffix (`*_sys`)
  - a generated `name` based on box/signal metadata
  - a forced `tab` = 'Sys' and `system` = True

  The function mutates the input list in-place and returns the updated `signals_list`
  (the same list instance).
  """
  tmp_list = list(
    map(duplicate_do_as_system_switch,
      copy.deepcopy(
        filter(lambda x: x['type'] == 'DO', signals_list))))
  signals_list.extend(tmp_list)
  return signals_list


def main():
  args = docopt(__doc__)
  csv_path = Path(args['--csv']).resolve()
  out_dir = Path(args['--out']).resolve()

  if not csv_path.is_file():
    print(f'error: CSV file not found: {csv_path}', file=sys.stderr)
    sys.exit(1)

  signals_list = read_signals_list(csv_path)
  signals_list = append_system_do_duplicates(signals_list)
  ha_gen_configs(signals_list, out_dir)
  print(f'generate ok: {out_dir}')


if __name__ == '__main__':
  main()
