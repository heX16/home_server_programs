import sys
import csv
import io
import string
import binascii
import copy
import yaml # pip install pyyaml
import pprint # TEMP
from pathlib import Path
from transliterate import translit # pip install transliterate

# CONFIG_HA_DIR = Path(__file__).resolve().parent.parent / 'config_ha'
CONFIG_HA_DIR = Path('config_ha')




def norm_col(cell):
  return cell.strip().split('\n')[0].strip()


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
  # Example:
  #- platform: mqtt
  #  name: 2
  #  friendly_name: Вкл 2
  #  state_topic: "extbus/8/15/r"
  #  payload_on: '1'
  #  payload_off: '0'
  data = {
    'platform': 'mqtt',
    'name': item['n'],
    'friendly_name': item['name'],
    'state_topic': item['mqtt']+'/r',
    'payload_on': '1',
    'payload_off': '0'
  }
  return data

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
  data = {
    'platform': 'mqtt',
    'name': item['n'],
    'state_topic': item['mqtt']+'/r',
    'command_topic': item['mqtt']+'/w',
    'payload_on':  '1',
    'payload_off': '0',
    'retain': True
  }
  return data


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


def read_signals_list():
  # Read CSV file
  signals_list = []
  iType = None
  iName = None
  iNameSig = None
  iMqtt = None
  iN = None
  iGrp = None
  iLogic = None
  iTab = None

  # f = open('test.txt', 'w')
  #f.write('test')

  with open('перечень_сигналов.csv', newline='', encoding="utf-8") as csvfile:
    datareader = csv.reader(csvfile, delimiter=';', quotechar='"')
    first_line = True
    for row in datareader:
      # определяем номеря столбцов
      if first_line:
        #print(row)
        first_line = False
        for idx, cell in enumerate(row):
          col = norm_col(cell)
          if col == 'Тип':
            iType = idx
          if col == 'Имя в интерфейсе':
            iName = idx
          if col == 'Наименование сигнала':
            iNameSig = idx
          if col == 'sig':
            iN = idx
          if col == 'N':
            iNS = idx
          if col in ('MQTT name', 'Путь MQTT'):
            iMqtt = idx
          if col == 'Группа':
            iGrp = idx
          if col == 'Logic':
            iLogic = idx
          if col == 'Модуль':
            iModule = idx
          if col == 'Я.':
            iBox = idx
          if col == 'Вкладка':
            iTab = idx
        continue

      # выкачиваем все строки в signals_list
      for idx, cell in enumerate(row):
        item = {
          'n': row[iN].strip().replace('.', '_'), # глобальный уникальный индификатор
          'ns': row[iNS], # номер сигнала в ящике
          'name': row[iName].strip(),
          'namesig': row[iNameSig].strip(),
          'group': row[iGrp].strip(),
          'mqtt': row[iMqtt].strip(),
          #'logic': row[iLogic],
          'type': row[iType],
          'module': row[iModule],
          'box': row[iBox],
          'b_m': str(row[iBox])+'_'+str(row[iModule]),
          'system': False,
          'tab': row[iTab],
        }
        if item['name']=='':
          item['name'] = item['namesig']

        if (idx==iType) and (cell=='DI'):
          item['sysname'] = 'binary_sensor.'+item['n']
          signals_list.append(item)
        if (idx==iType) and (cell=='DO'):
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


def ha_gen_configs(signals_list, group_data):
  # Write YAML file

  # сохраняем список DI
  di_nodes = list(map(ha_gen_binary_sensor_node, filter(lambda x: x['type'] == 'DI', signals_list)))
  with io.open(CONFIG_HA_DIR / 'sensors_binary' / 'sensors_gen.yaml', 'w', encoding='utf-8-sig') as outfile:
      yaml.dump(di_nodes, outfile, default_flow_style=False, allow_unicode=True)

  do_nodes = list(map(ha_gen_switch_node, filter(lambda x: x['type'] == 'DO', signals_list)))
  with io.open(CONFIG_HA_DIR / 'switches' / 'switch_gen.yaml', 'w', encoding='utf-8-sig') as outfile:
      yaml.dump(do_nodes, outfile, default_flow_style=False, allow_unicode=True)

  #pprint.pprint(signals_list, width=5) ## DBG

  customize_nodes = {}
  for node in map(ha_gen_customize_node, signals_list):
    customize_nodes.update(node)
  with io.open(CONFIG_HA_DIR / 'customize' / 'customize_gen.yaml', 'w', encoding='utf-8-sig') as outfile:
      yaml.dump(customize_nodes, outfile, default_flow_style=False, allow_unicode=True)

  cust_list = group_data['groups_yaml']

  # сохраняем список 'скрытых' групп
  with io.open(CONFIG_HA_DIR / 'groups' / 'group_gen.yaml', 'w', encoding='utf-8-sig') as outfile:
      yaml.dump(cust_list, outfile, default_flow_style=False, allow_unicode=True)

  # автоматизация - отключенно. используется gen_logic.
  #with io.open('automation.yaml', 'w', encoding='utf8') as outfile:
  #    yaml.dump(gen_automation_all(), outfile, default_flow_style=False, allow_unicode=True)


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
  signals_list = read_signals_list()
  signals_list = append_system_do_duplicates(signals_list)
  group_data = build_group_data(signals_list)
  ha_gen_configs(signals_list, group_data)
  print('generate ok')


if __name__ == '__main__':
  main()




# https://home-assistant.io/docs/automation/templating/

