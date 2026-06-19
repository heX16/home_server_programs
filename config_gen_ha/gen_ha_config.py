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
import string
import binascii
import copy
import yaml
import pprint # TEMP
from pathlib import Path
from docopt import docopt
from transliterate import translit

OUTPUT_SUBDIRS = ('mqtt', 'customize', 'groups')




def norm_col(cell):
  return cell.strip().split('\n')[0].strip()


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


# items: sysname
def ha_gen_group(item_list, grp_name, grp_caption = '', is_view = False):
#all_sensors:
#  name: All_DI
#  view: yes
#  entities:
#    - binary_sensor.6101
#    - binary_sensor.6102
#    ...
  if is_view:
    is_view = 'yes'
  else:
    is_view = 'no'
  ent = []
  for i in item_list:
    ent.append(i['sysname'])

  res = {
      grp_name: {
        'view': is_view,
        'name': grp_caption,
        'entities': ent
      }
  }
  return res



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
  #     object_id: '...'
  #     state_topic: '...'
  #     payload_on: '1'
  #     payload_off: '0'
  return {
    'binary_sensor': {
      'name': item['name'],
      'unique_id': f'di_{item["n"]}',
      'object_id': item['n'],
      'state_topic': item['mqtt'] + '/r',
      'payload_on': '1',
      'payload_off': '0',
    }
  }

# item: n,name,mqtt
def ha_gen_switch_node(item):
  # Example:
  #- platform: mqtt
  #  name: 3
  #  state_topic: "extbus/8/5/r"
  #  command_topic: "extbus/8/5/w"
  #  payload_on:  "1"
  #  payload_off: "0"
  #  retain: true
  # пытался сделать упорядочненный массив, но не вышло - yaml не знает этот класс
  #  data = collections.OrderedDict([
  #    ('platform', 'mqtt'),
  #    ('name', item['n']),
  #    ('state_topic', item['mqtt']+'/r'),
  #    ('command_topic', item['mqtt']+'/w'),
  #    ('payload_on',  '1'),
  #    ('payload_off', '0'),
  #    ('retain', True)
  #  ])
  #pprint.pprint(item, width=5)
  return {
    'switch': {
      'name': item['name'],
      'unique_id': f'do_{item["n"]}',
      'object_id': item['n'],
      'state_topic': item['mqtt'] + '/r',
      'command_topic': item['mqtt'] + '/w',
      'payload_on': '1',
      'payload_off': '0',
      'retain': True,
    }
  }


def duplicate_do_as_system_switch(n):
  """
  Create a "system" duplicate of a DO item.

  Home Assistant groups do not support per-group friendly names cleanly, so we duplicate
  DO switches and put them into a separate technical view (tab 'Sys') with generated names.
  See: https://community.home-assistant.io/t/group-specific-friendly-name/12816/26
  """

  n['n']=n['n']+'_sys'
  n['name']=n['box']+'.'+n['ns']+' '+n['namesig']
  n['sysname'] = 'switch.'+n['n']
  n['group'] = 'Box'+n['box']
  n['tab'] = 'Sys'
  n['system'] = True
  return n;


def eng_name(t):
  s = translit(t.strip(), 'ru', reversed=True).lower()
  s = s.replace("\'", '')
  s = s.replace("-", '_')
  s = s.replace(" ", '_')
  f = '_' + string.ascii_letters + string.digits
  s = ''.join(list(filter(lambda c: c in f, s)))
  return s


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


def build_group_data(signals_list):
  signals_list_sorted = sorted(signals_list, key=lambda x: x['group'])

  # unique group names (only DO groups)
  grp_set = set(list(map(lambda i: str(i['group']).strip(), filter(lambda x: x['type'] == 'DO', signals_list_sorted))))
  grp_set.discard('')
  grp_set.discard('group_reserved')
  grp_list = list(sorted(grp_set))

  # unique tab names (only DO tabs)
  tab_set = set(list(map(lambda i: str(i['tab']).strip(), filter(lambda x: x['type'] == 'DO', signals_list_sorted))))
  tab_set.discard('')
  tab_list = list(sorted(tab_set))

  groups_yaml = {}

  for grp in grp_list:
    l = filter(lambda fv: fv['group'] == grp, signals_list_sorted)
    groups_yaml.update(
        ha_gen_group(l, eng_name(grp), grp))

  # system groups
  groups_yaml.update(
      ha_gen_group(filter(lambda x: x['type'] == 'DO', signals_list_sorted), 'all_switch'))

  groups_yaml.update(
      ha_gen_group(filter(lambda x: x['type'] == 'DI', signals_list_sorted), 'all_binary_sensor'))

  return {
    'signals_list': signals_list_sorted,
    'tab_list': tab_list,
    'groups_yaml': groups_yaml,
  }


def ha_gen_configs(signals_list, group_data, out_dir):
  # Write YAML file
  ensure_output_dirs(out_dir)

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

  cust_list = group_data['groups_yaml']

  # сохраняем список 'скрытых' групп
  with io.open(out_dir / 'groups' / 'group_gen.yaml', 'w', encoding='utf-8-sig') as outfile:
      yaml.dump(cust_list, outfile, default_flow_style=False, allow_unicode=True)



def append_system_do_duplicates(signals_list):
  """
  Duplicate all DO items and append them back into `signals_list` as "system" switches.

  This is used to create an additional, purely technical view/grouping of switches:
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
  group_data = build_group_data(signals_list)
  ha_gen_configs(signals_list, group_data, out_dir)
  print(f'generate ok: {out_dir}')


if __name__ == '__main__':
  main()


