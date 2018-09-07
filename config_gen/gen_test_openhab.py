#!/usr/bin/env python3
# coding: utf-8

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

# todo: сделать считывание данных напрямую из ODS. вынести считывание в отдельную либу. подумать над форматом ODS.

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

def gen_json_config_header(headtext):
  return {
    'uid': '73b59f33-c263-4fbf-983d-'+str(100000000000+random.randint(1, 100000000)),
    "type": "HEADER",
    'name': headtext,
  }


#    "uid": "73b59f33-c263-4fbf-983d-3d0351006310",
#    "pubTopic2": "",
#    "pubTopic3": "",
#    "pubTopic": "\/extbus\/1\/9\/w",
#    "publishValue": "1",
#    "publishValue2": "0",
#    "type": "SWITCH",
#    "additionalValue2": "",
#    "additionalValue3": "",
#    "mode": -1,
#    "feedback": true,
#    "primaryColor": -13877680,
#    "additionalValue": "",
#    "name": "Прихожая 1",
#    "topic": "\/extbus\/1\/9\/r",
#    "retained": false,
#    "onReceiveExecute": "",
#    "label2": "",
#    "formatMode": "",
#    "topic2": "",
#    "label": "",
#    "topic1": "",
#    "topic3": "",
#    "name3": "",
#    "onShowExecute": "",
#    "pubTopic1": "",
#    "name1": "",
#    "primaryColor1": -13877680,
#    "name2": "",
#    "primaryColor2": -13877680,
#    "primaryColor3": -13877680,
#    "decimalMode": false
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
  data = item['sysname'] + item['name']
  #todo:WIP
  return data

# item: n,name,mqtt
def gen_binary_sensor_node(item):
  #example from inet: Contact MKDoorSensor1 "Side Door [%s]" { mqtt="<[broker:MK-SmartHouse/security/MK-DoorSensor1:state:default]" }
  #  n: 2
  #  name: Вкл 2
  #  mqtt: "extbus/8/15"
  return 'Contact {0} ({3}) "{1} [%s]" {{ mqtt="<[mqtt:{2}/r:state:MAP(bin.map)]" }}'. \
    format(item['sysname'], item['name'], item['mqtt'], item['groupid'])

# item: n,name,mqtt
def gen_switch_node(item):
  #example from inet:  Switch Sonoff01 "Ванная" {mqtt=" >[mqtt:sonoff/01/POWER:command:*:MAP(2bin.map)], <[mqtt:sonoff/01/POWER:state:MAP(bin.map)]"}
  return 'Switch {0} "{1}" ({3}) {{mqtt=" >[mqtt:{2}/w:command:*:MAP(2bin.map)], <[mqtt:{2}/r:state:MAP(bin.map)]"}}'. \
    format(item['sysname'], item['name'], item['mqtt'], item['groupid'])

def eng_name(t):
  s = translit(t.strip(), 'ru', reversed=True).lower()
  s = s.replace("-", '_')
  s = s.replace(" ", '_')
  # фильтруем - пропускаем только допустимые символы, остальные удаляем
  f = '_' + string.ascii_letters + string.digits
  s = ''.join(list(filter(lambda c: c in f, s)))
  if (len(s)>1) and (s[0] in string.digits):
    s = '_'+s
  return s

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
    #print(row)
    # определяем номера столбцов
    if first_line:
      first_line = False
      for idx, cell in enumerate(row):
        if cell=='Тип':
          iType = idx
        if cell=='Имя в интерфейсе':
          iName = idx
        if cell=='Наименование сигнала':
          iNameSig = idx
        if cell=='sig':
          iN = idx
        if cell=='N':
          iNS = idx
        if cell=='MQTT name':
          iMqtt = idx
        if cell=='Группа':
          iGrp = idx
        if cell=='Logic':
          iLogic = idx
        if cell=='Модуль':
          iModule = idx
        if cell=='Я.':
          iBox = idx
        if cell=='Вкладка':
          iTab = idx
      continue

    # выкачиваем все строки в signals_list
    item = {
      'n': row[iN].strip().replace('.', '_'), # глобальный уникальный индификатор
      'ns': row[iNS], # номер сигнала в ящике
      'name': row[iName].strip(),
      'namesig': row[iNameSig].strip(),
      'group': row[iGrp].strip(),
      'groupid': eng_name(row[iGrp].strip()),
      'mqtt': row[iMqtt].strip(),
      #'logic': row[iLogic],
      'type': row[iType],
      'module': row[iModule],
      'box': row[iBox],
      'b_m': str(row[iBox])+'_'+str(row[iModule]),
      'system': False,
      'tab': row[iTab],
    }

    # обрабатываем ячейки
    if item['groupid']=='':
      if item['type']=='DI':
        item['groupid']='di'
      else:
        item['groupid']='reserved'
    if item['name']=='':
      item['name'] = item['namesig']
    if item['type']=='DI':
      item['sysname'] = 'DI_'+item['n']
      signals_list.append(item)
    if item['type']=='DO':
      item['sysname'] = 'DO_'+item['n']
      signals_list.append(item)





# Write YAML file

# сохраняем список DI
with io.open('../items/inputs.items', 'w', encoding='utf-8') as outfile:
    outfile.write('\n'.join(regen_list(filter(lambda x: x['type']=='DI', signals_list), gen_binary_sensor_node)))

# _дублируем_ список DO
# (суки! дебилы!!! - см https://community.home-assistant.io/t/group-specific-friendly-name/12816/26)
#def switch2(n):
#  n['n']=n['n']+'_sys'
#  n['name']=n['box']+'.'+n['ns']+' '+n['namesig']
#  n['sysname'] = 'switch.'+n['n']
#  n['group'] = 'Box'+n['box']
#  n['tab'] = 'Sys'
#  n['system'] = True
#  return n;
#
#tmp_list = list(
#  map(switch2,
#    copy.deepcopy(
#      filter(lambda x: x['type']=='DO', signals_list))))
#signals_list.extend(tmp_list)


with io.open('../items/outputs.items', 'w', encoding='utf-8') as outfile:
  outfile.write( '\n'.join(regen_list(filter(lambda x: x['type']=='DO', signals_list), gen_switch_node)) )

#pprint.pprint(signals_list, width=5) ## DBG

#cust_list = {}
#cust_list.update(regen_dict(signals_list, gen_customize_node))
#with io.open('../config_ha/customize/customize_gen.yaml', 'w', encoding='utf-8-sig') as outfile:
#    yaml.dump(cust_list, outfile, default_flow_style=False, allow_unicode=True)

# сортируем по группам #####################

signals_list = sorted(signals_list, key=lambda x: x['group'])

# группы #####################

cust_list = {}
grp_list_accum = list()

# создаем перечень уникальных групп по названиям групп (используется только массив DO)
grp_set = set(list(map(lambda i: str(i['group']).strip(), filter(lambda x: x['type']=='DO', signals_list))))
grp_set.discard('')
grp_set.discard('group_reserved')
grp_list = list(sorted(grp_set))
grp_set = None
#for i in grp_list: print('['+i+']' + eng_name(i))

# создаем перечень уникальных TAB (используется только массив DO)
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
#cust_list.update(gen_group(filter(lambda x: x['type']=='DO', signals_list), 'all_switch'))
#cust_list.update(gen_group(filter(lambda x: x['type']=='DI', signals_list), 'all_binary_sensor'))

# сохраняем список 'скрытых' групп
#with io.open('D:\Work\House1-openhab2\items\groups.items', 'w', encoding='utf-8-sig') as outfile:
#    yaml.dump(cust_list, outfile, default_flow_style=False, allow_unicode=True)

# sitemap - отдельный файл для каждого этажа
for tab in tab_list:
  # создаем элементы вкладок
  t = ['sitemap %s label="%s" {' % (tab,tab)]
  lastgrp = ''
  for i in filter(lambda x: (x['tab']==tab and x['group']!=''), signals_list):
    if i['group']!=lastgrp:
      if lastgrp!='':
        t = t + ['  }']
      t = t + ['  Frame label="{0}" {{'.format(i['group'])]
      lastgrp = i['group']
    t = t + ['    Switch item=%s icon="light"' % i['sysname'] ]
  t = t + ['  }']
  t = t + ['}'] + ['']
  with io.open('../sitemaps/%s.sitemap'%tab, 'w', encoding='utf-8') as outfile:
    outfile.write( '\n'.join(t) )

# sitemap - один файл для всех элементов
t = ['sitemap default label="Дом (весь)" {']
for tab in tab_list:
  lastgrp = ''
  for i in filter(lambda x: (x['tab']==tab and x['group']!=''), signals_list):
    if i['group']!=lastgrp:
      if lastgrp!='':
        t = t + ['  }']
      t = t + ['  Frame label="{0}" {{'.format(i['group'])]
      lastgrp = i['group']
    t = t + ['    Switch item=%s icon="light"' % i['sysname'] ]
  t = t + ['  }']
t = t + ['}'] + ['']

with io.open('../sitemaps/All_Home.sitemap', 'w', encoding='utf-8') as outfile:
  outfile.write( '\n'.join(t) )

# write transform

p = '../transform/2bin.map'
if not Path(p).is_file():
  with io.open(p, 'w', encoding='utf-8') as outfile:
    outfile.write('\n'.join(['ON=1','OFF=0','on=1','off=0','On=1','Off=0','OPEN=1','CLOSED=0']))

p = '../transform/bin.map'
if not Path().is_file():
  with io.open(p, 'w', encoding='utf-8') as outfile:
    outfile.write('\n'.join(['1=ON','0=OFF']))



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

#with open('settings.json', 'w', encoding='utf-8-sig') as outfile:
#    json.dump(
#      config_linear_mqtt,
#      outfile, ensure_ascii=False)

# автоматизация - отключенно. используется gen_logic.
#with io.open('automation.yaml', 'w', encoding='utf8') as outfile:
#    yaml.dump(gen_automation_all(), outfile, default_flow_style=False, allow_unicode=True)

print('generate ok')











# https://home-assistant.io/docs/automation/templating/


