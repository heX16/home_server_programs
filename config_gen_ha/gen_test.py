import sys
import csv
import io
import string
import binascii
import copy
import random
import yaml # pip install pyyaml
import json
import pprint # TEMP
from pathlib import Path
from transliterate import translit # pip install transliterate

# CONFIG_HA_DIR = Path(__file__).resolve().parent.parent / 'config_ha'
CONFIG_HA_DIR = Path('config_ha')




def regen_list(mylist, myproc):
  res = []
  for i in mylist:
    res.append(myproc(i))
  return res

def regen_dict(mylist, myproc):
  res = {}
  for i in mylist:
    res.update(myproc(i))
  return res

def norm_col(cell):
  return cell.strip().split('\n')[0].strip()

def gen_json_config_header(headtext):
  return {
    'uid': '73b59f33-c263-4fbf-983d-'+str(100000000000+random.randint(1, 100000000)),
    "type": "HEADER",
    'name': headtext,
  }


#            "uid": "73b59f33-c263-4fbf-983d-3d0351006310",
#            "pubTopic2": "",
#            "pubTopic3": "",
#            "pubTopic": "\/extbus\/1\/9\/w",
#            "publishValue": "1",
#            "publishValue2": "0",
#            "type": "SWITCH",
#            "additionalValue2": "",
#            "additionalValue3": "",
#            "mode": -1,
#            "feedback": true,
#            "primaryColor": -13877680,
#            "additionalValue": "",
#            "name": "Прихожая 1",
#            "topic": "\/extbus\/1\/9\/r",
#            "retained": false,
#            "onReceiveExecute": "",
#            "label2": "",
#            "formatMode": "",
#            "topic2": "",
#            "label": "",
#            "topic1": "",
#            "topic3": "",
#            "name3": "",
#            "onShowExecute": "",
#            "pubTopic1": "",
#            "name1": "",
#            "primaryColor1": -13877680,
#            "name2": "",
#            "primaryColor2": -13877680,
#            "primaryColor3": -13877680,
#            "decimalMode": false
def gen_json_config_node(item, nodetype = "SWITCH"):
  return {
    'uid': '73b59f33-c263-4fbf-983d-'+str(100000000000+random.randint(1, 100000000)),
    "type": nodetype,
    'name': item['name'],
    'topic': item['mqtt']+'/r',
    'pubTopic': item['mqtt']+'/w',
  }


# items: sysname
def gen_group(item_list, grp_name, grp_caption = '', is_view = False):
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
def gen_customize_node(item):
  # Example:
  #switch.1:
  #  friendly_name: "ванная"
  data = {
    item['sysname']:
    { 'friendly_name': item['name']}
  }
  return data

# item: n,name,mqtt
def gen_binary_sensor_node(item):
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
def gen_switch_node(item):
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


##############################################################
##############################################################
##############################################################
##############################################################
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






# Write YAML file

# сохраняем список DI
with io.open(CONFIG_HA_DIR / 'sensors_binary' / 'sensors_gen.yaml', 'w', encoding='utf-8-sig') as outfile:
    yaml.dump(regen_list(filter(lambda x: x['type']=='DI', signals_list), gen_binary_sensor_node),
      outfile, default_flow_style=False, allow_unicode=True)

# _дублируем_ список DO
# (суки! дебилы!!! - см https://community.home-assistant.io/t/group-specific-friendly-name/12816/26)
def switch2(n):
  n['n']=n['n']+'_sys'
  n['name']=n['box']+'.'+n['ns']+' '+n['namesig']
  n['sysname'] = 'switch.'+n['n']
  n['group'] = 'Box'+n['box']
  n['tab'] = 'Sys'
  n['system'] = True
  return n;

tmp_list = list(
  map(switch2,
    copy.deepcopy(
      filter(lambda x: x['type']=='DO', signals_list))))
signals_list.extend(tmp_list)

with io.open(CONFIG_HA_DIR / 'switches' / 'switch_gen.yaml', 'w', encoding='utf-8-sig') as outfile:
    yaml.dump(regen_list(filter(lambda x: x['type']=='DO', signals_list), gen_switch_node),
      outfile, default_flow_style=False, allow_unicode=True)

#pprint.pprint(signals_list, width=5) ## DBG

cust_list = {}
cust_list.update(regen_dict(signals_list, gen_customize_node))
with io.open(CONFIG_HA_DIR / 'customize' / 'customize_gen.yaml', 'w', encoding='utf-8-sig') as outfile:
    yaml.dump(cust_list, outfile, default_flow_style=False, allow_unicode=True)

# сортируем по группам #####################

signals_list = sorted(signals_list, key=lambda x: x['group'])

# группы #####################

def eng_name(t):
  s = translit(t.strip(), 'ru', reversed=True).lower()
  s = s.replace("\'", '')
  s = s.replace("-", '_')
  s = s.replace(" ", '_')
  f = '_' + string.ascii_letters + string.digits
  s = ''.join(list(filter(lambda c: c in f, s)))
  return s

cust_list = {}
grp_list_accum = list()

# создаем перечень уникальных групп по названиям групп (используется только группа DO)
grp_set = set(list(map(lambda i: str(i['group']).strip(), filter(lambda x: x['type']=='DO', signals_list))))
grp_set.discard('')
grp_set.discard('group_reserved')
grp_list = list(sorted(grp_set))
grp_set = None
#for i in grp_list: print('['+i+']' + eng_name(i))

# создаем перечень уникальных групп по названиям групп (используется только группа DO)
tab_set = set(list(map(lambda i: str(i['tab']).strip(), filter(lambda x: x['type']=='DO', signals_list))))
tab_set.discard('')
tab_list = list(sorted(tab_set))
tab_set = None
#for i in tab_list: print('['+i+']')

# проходим по всему списку групп, и создаем фильтрованные списки принадлежности к группам
for i in grp_list:
  l = filter(lambda fv: fv['group'] == i, signals_list)
  cust_list.update(gen_group(l, eng_name(i), i))

# системные группы
cust_list.update(gen_group(filter(lambda x: x['type']=='DO', signals_list), 'all_switch'))
cust_list.update(gen_group(filter(lambda x: x['type']=='DI', signals_list), 'all_binary_sensor'))

# сохраняем список 'скрытых' групп
with io.open(CONFIG_HA_DIR / 'groups' / 'group_gen.yaml', 'w', encoding='utf-8-sig') as outfile:
    yaml.dump(cust_list, outfile, default_flow_style=False, allow_unicode=True)


################### конфиг 'linear mqtt' #################

# перечисляем вкладки
config_linear_mqtt_dashboards = []
config_linear_mqtt_tabs = []
tab_num = 1
for tab in tab_list:
  # создаем элементы вкладок

  lastgrp = ''
  items = []
  for i in filter(lambda x: (x['tab']==tab and x['group']!=''), signals_list):
    if i['group']!=lastgrp:
      lastgrp = i['group']
      items.append(gen_json_config_header(lastgrp))
    items.append(gen_json_config_node(i))

  config_linear_mqtt_dashboards.append({
    'dashboard': items,
    'id': tab_num
  })
  config_linear_mqtt_tabs.append({
    "id": tab_num,
    "name": tab
  })
  tab_num = tab_num + 1



config_linear_mqtt = {
    "settingsVersion": 1,
    "port": "1883",
    "username": "",
    "push_notifications_subscribe_topic": "out/wcs/push_notifications/#",
    "server_topic": "",
    "keep_alive": "60",
    "connection_in_background": False,
    "server": "192.168.1.9",
    "dashboards": config_linear_mqtt_dashboards,
    "tabs": config_linear_mqtt_tabs
  }

with open('settings.json', 'w', encoding='utf-8-sig') as outfile:
    json.dump(
      config_linear_mqtt,
      outfile, ensure_ascii=False)

# автоматизация - отключенно. используется gen_logic.
#with io.open('automation.yaml', 'w', encoding='utf8') as outfile:
#    yaml.dump(gen_automation_all(), outfile, default_flow_style=False, allow_unicode=True)

print('generate ok')











# https://home-assistant.io/docs/automation/templating/


