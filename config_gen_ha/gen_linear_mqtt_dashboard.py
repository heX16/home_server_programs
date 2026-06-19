import argparse
import json
import random
from pathlib import Path

import gen_test


def gen_json_config_header(headtext):
  return {
    'uid': '73b59f33-c263-4fbf-983d-'+str(100000000000+random.randint(1, 100000000)),
    'type': 'HEADER',
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
def gen_json_config_node(item, nodetype='SWITCH'):
  return {
    'uid': '73b59f33-c263-4fbf-983d-'+str(100000000000+random.randint(1, 100000000)),
    'type': nodetype,
    'name': item['name'],
    'topic': item['mqtt']+'/r',
    'pubTopic': item['mqtt']+'/w',
  }


def generate_linear_mqtt_settings(group_data, output_path='settings.json'):
  ################### конфиг 'linear mqtt' #################

  signals_list = group_data['signals_list']
  tab_list = group_data['tab_list']

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
      'id': tab_num,
      'name': tab
    })
    tab_num = tab_num + 1

  config_linear_mqtt = {
      'settingsVersion': 1,
      'port': '1883',
      'username': '',
      'push_notifications_subscribe_topic': 'out/wcs/push_notifications/#',
      'server_topic': '',
      'keep_alive': '60',
      'connection_in_background': False,
      'server': '192.168.1.9',
      'dashboards': config_linear_mqtt_dashboards,
      'tabs': config_linear_mqtt_tabs
    }

  with open(output_path, 'w', encoding='utf-8-sig') as outfile:
      json.dump(
        config_linear_mqtt,
        outfile, ensure_ascii=False)


def main():
  parser = argparse.ArgumentParser(
    description='Generate Linear MQTT Dashboard settings.json')
  parser.add_argument(
    '--output',
    default=Path(__file__).resolve().parent / 'settings.json',
    type=Path,
    help='Output path for settings.json (default: settings.json next to this script)',
  )
  args = parser.parse_args()

  signals_list = gen_test.read_signals_list()
  signals_list = gen_test.append_system_do_duplicates(signals_list)
  group_data = gen_test.build_group_data(signals_list)
  generate_linear_mqtt_settings(group_data, args.output)
  print(f'generated {args.output}')


if __name__ == '__main__':
  main()
