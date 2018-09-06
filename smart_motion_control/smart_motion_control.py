#!/usr/bin/env python3

import paho.mqtt.client as paho   # pip install paho-mqtt
import yaml # pip3 install pyyaml
import math
import time
import sched
import logging
import sys
import io
import pprint
from docopt import docopt
from datetime import datetime
from smart_motion_control_lib import *
from mqtt_variable import *

usage = '''
Usage: install_service.py [--config=FILE] [--mqtt=HOST] [--quiet] [--verbose]

Options:
  --config=FILE  config file       [default: config.yaml]
  --mqtt=HOST    MQTT server name  [default: localhost]
  --quiet        print less text
  --verbose      print more text
'''

debug = True

mqttEvents = None

def s(b):
  return b.decode("utf-8")

class csSmartSwitchMqttPathOptions:
  ''' Опции - Пути к MQTT '''

  def __init__(self):
    self.name=''       # "человеческое" имя
    self.value_path='' # путь к оперативным значениям
    self.opt_path=''   # путь к опциям
    self.relay_r=''    # реле (чтение)
    self.relay_w=''    # реле (запись)
    self.mot_det_r=''  # ДД (чтение)
    self.switch_r=''   # включатель кнопочный (чтение)
    self.time_motion=''  # длительность включения от сработки ДД (#уставка)
    self.time_switch_auto_off='' # длительность отключения ДД при выключении вручную (смартфоном или включателем) (#уставка)
    self.time_disable_start1=''  # время когда датчик движения не работает. начало времени. (указывается в часах 0..24)
    self.time_disable_len1=''    # время когда датчик движения не работает. продолжительность. (указывается в часах 0..24)
    self.time_disable_start2=''  # идентично time_disable_start1
    self.time_disable_len2=''    # идентично time_disable_len1
    self.auto_disable_r='' # опция: отключить ДД
    #self.sunset_enabled='' # опция: используется отключение автоматики после восхода солнца
    #self.sunrise_r=''  # флаг что солнце зашло
    #self.sunset_r=''   # флаг что солнце взошло


class csMqttEventCollector:
  ''' Вызывает события при событии (проблема в том что у MQTT объекта только один "слот" для события. А мне нужно много. '''
  #todo: избавится от csMqttEventCollector ИЛИ csMqttEvents - должен остаться только один...

  def __init__(self, mqttClient):
    self.on_connect_list = []
    self.on_disconnect_list = []
    self.mqttClient = mqttClient
    self.mqttClient.on_connect = self.__connect_event
    self.mqttClient.on_disconnect = self.__disconnect_event

  def __connect_event(self, client, userdata, flags, rc):
    for cb in self.on_connect_list:
      cb(client, userdata, flags, rc)

  def __disconnect_event(self, client, userdata, rc):
    for cb in self.on_disconnect_list:
      cb(client, userdata, rc)

  def add_connect_event(self, cb):
    self.on_connect_list = self.on_connect_list + [cb]

  def add_disconnect_event(self, cb):
    self.on_disconnect_list = self.on_disconnect_list + [cb]


class csSmartSwitchMqtt:
  ''' Принимаем данные от MQTT и передаем их в алгоритм.
      Также получаем результаты от алгоритма и передаем их в MQTT.
  '''

  def __init__(self, switch_obj, mqtt_client, event_list, events_list2, opt: csSmartSwitchMqttPathOptions):
    self.mqtt_client = mqtt_client
    self.switch = switch_obj
    self.mqtt = opt # mqtt path
    self.prev_switch = None
    self.prev_mot_det = None
    self.prev_out_enabled = None
    self.prev_state = 0 # предыдущее состояние
    self.event_list = event_list
    self.events_list2 = events_list2
    #bool filter: lambda m: True if m=='1' else False)
    self.events_list2.add_connect_event(self.event_connect)
    self.events_list2.add_disconnect_event(self.event_disconnect)
    self.time_disable_start1=csMqttVarLocal(mqtt_client, event_list, self.mqtt.opt_path+'/'+self.mqtt.time_disable_start1, 0, lambda m: int(m))
    self.time_disable_len1  =csMqttVarLocal(mqtt_client, event_list, self.mqtt.opt_path+'/'+self.mqtt.time_disable_len1,   0, lambda m: int(m))
    self.time_disable_start2=csMqttVarLocal(mqtt_client, event_list, self.mqtt.opt_path+'/'+self.mqtt.time_disable_start2, 0, lambda m: int(m))
    self.time_disable_len2  =csMqttVarLocal(mqtt_client, event_list, self.mqtt.opt_path+'/'+self.mqtt.time_disable_len2,   0, lambda m: int(m))

  def event_connect(self, client, userdata, flags, rc):
    def sub(path, event):
      if type(path)==str and path != '':
        self.mqtt_client.subscribe(path)
        # todo: ??? - он проверяет на повторное добавление??? или будет двойной вызов?
        self.mqtt_client.message_callback_add(path, event)

    # добавляем обработчики изменений топиков MQTT
    sub(self.mqtt.relay_r, self.event_relay)
    sub(self.mqtt.mot_det_r, self.event_mot_det)
    sub(self.mqtt.switch_r, self.event_switch)
    # "дергаем" обьекты чтобы они подписались на топики
    self.event_list.connect_event()
    logging.debug("ReConnect: "+self.mqtt.name)

  def event_disconnect(self, client, userdata, rc):
    if rc != paho.MQTT_ERR_SUCCESS:
      logging.debug('mqtt dissconect detected')
      time.sleep(2)
      client.reconnect()

  def event_relay(self, client, userdata, msg):
    ''' Изменение: состояния реле (удаленного включателя) '''

    # 'парсим' входящие данные
    d = True if s(msg.payload)=='1' else False

    logging.debug('event_relay d='+str(d)+' name='+self.mqtt.name)

    # передаем данные в алгоритм
    self.switch.data_in.relay = d

  def event_switch(self, client, userdata, msg):
    ''' Изменение: состояния механического включателя '''

    # 'парсим' входящие данные
    d = True if s(msg.payload)=='1' else False
    logging.debug('event_switch d='+str(d)+' name='+self.mqtt.name)

    # 'инициализируем' (если это первое обращение к данным)
    if self.prev_switch is None:
      self.prev_switch = not d

    # если данные изменились - передаем их в алгоритм
    if self.prev_switch != d:
      self.prev_switch = d
      self.switch.data_in.switch = True

  def event_mot_det(self, client, userdata, msg):
    ''' Изменение: состояния ДД '''

    # 'парсим' входящие данные
    d = True if s(msg.payload)=='1' else False
    logging.debug('event_mot_det d='+str(d)+' name='+self.mqtt.name)

    # 'инициализируем' (если это первое обращение к данным)
    if self.prev_mot_det is None:
      self.prev_mot_det = not d

    # если данные изменились - передаем их в алгоритм, но передаем только если 0->1
    # ВНИМАНИЕ: снимать флаг 'self.switch.data_in.motion' нужно 'снаружи' (вручную)
    if self.prev_mot_det != d:
      self.prev_mot_det = d
      if d==True:
        logging.debug('mot_det: 0->1 '+str(d)+' name='+self.mqtt.name)
        self.switch.data_in.motion = True

  def check_time(self, hour, start, length):
    ''' Проверка времени.
        hour-проверяемый час (текущий час)
        start-начало времени (номер часа)
        length-продолжительность '''
    if length > 0 and length < 24:
      # проверка на выход за диапазон (0.0 - 23.99)
      if start + length > 24:
        # тогда проверяем второй диапазон - проверяем ту часть которая вышла за 24 часа
        if hour >= 0 and hour < (start + length - 24):
          return True
      # обычная проверка (причем если диапазон выходит за 24 часа то нам это не заботит - ошибки не будет)
      if hour >= start and hour < start + length:
        return True
    return False

  def get_current_hour(self):
    return datetime.now().hour + datetime.now().minute / 60 # 0.0 - 23.99
    #return datetime.now().hour # 0..23

  def is_disable_hour(self, hour):
    ''' Проверка времени - True значит мы попали в "запрещенные часы" '''
    #####if self.check_time(hour, self.time_disable_start1.value, self.time_disable_len1.value): return True
    if self.check_time(hour, self.time_disable_start2.value, self.time_disable_len2.value):
      return True
    return False

  def run(self):
    ''' Запуск системы '''

    if self.is_disable_hour(self.get_current_hour()):
      # настал "тихий час" когда датчик движения не срабатывает
      self.switch.motion = False

    # алгоритм
    self.switch.run()

    # если вывод изменился - тогда обрабатываем
    if self.switch.data_out.enabled != self.prev_out_enabled:
      self.prev_out_enabled = self.switch.data_out.enabled
      if not self.switch.data_out.ignore_change:
        # если нет флага игнорирование тогда высылаем команду ('0' или '1')
        d = self.switch.data_out.enabled
        logging.debug('write to relay: '+str(d)+' mqtt_path='+self.mqtt.relay_w)
        self.mqtt_client.publish(self.mqtt.relay_w, str(int(d)))

    # сбрасываем флаг
    self.switch.data_out.ignore_change = False
    self.switch.data_in.motion = False

    # логгируем состояние
    if self.switch.state != self.prev_state:
      self.prev_state = self.switch.state
      logging.debug('state: '+str(self.prev_state))

def apply_config_dict(obj, config_dict: dict):
  for k,v in config_dict.items():
    setattr(obj, k, v)

def load_config(filename: str):
  # Read YAML file
  with open(filename, 'r', encoding='utf8') as stream:
      data = yaml.load(stream)

  conf_list = []
  for i in data['motion_detectors']:
    cfg = csSmartSwitchMqttPathOptions()
    apply_config_dict(cfg, i)
    conf_list = conf_list + [cfg]
  return conf_list


def main():
  # параметры
  options = docopt(usage)

#  abspath = os.path.abspath(__file__)
#  dname = os.path.dirname(abspath)
#  os.chdir(dname)
  # сообщения

  if options['--quiet']:
    level=logging.NOTSET
  elif options['--verbose']:
    level=logging.DEBUG
  else:
    level=logging.ERROR
  logging.basicConfig(stream=sys.stderr, level=level)

  cfg_list = load_config(options['--config'])

  # события
  mqttEvents = csMqttEvents()

  # расписание
  scheduler = sched.scheduler()

  #todo: ... opt.switch_r='extbus/2/25/r', - не работает, входит в бесконечное переключение. отладить нехватает времени, да и нет нужды особой...

  # initialise MQTT broker connection
  mqttc = paho.Client('smartswitch01')

  eventsCollector = csMqttEventCollector(mqttc)

  swMqtt = []

  # создаем переключатели
  for cfg in cfg_list:
    logging.info("Cfg name:" + cfg.name)
    # создаем переключатель
    switchTmp = SmartMotDetSwitch(scheduler, 20, 5)

    # создаем переключатель подключенный к mqtt
    swMqtt = swMqtt + [csSmartSwitchMqtt(switchTmp, mqttc, mqttEvents, eventsCollector, cfg)]

#  logging.debug('csMqttVar')
#  var1 = csMqttVarLocal(mqttc, mqttEvents, 'test')

#  if debug:
#      logging.debug('DEBUG!')
#      swMqtt1.time_disable_start1=14
#      swMqtt1.time_disable_len1=0
#      swMqtt1.time_disable_start2=14
#      swMqtt1.time_disable_len2=12
#      #logging.debug(swMqtt1.is_disable_hour(swMqtt1.get_current_hour()))
#      #scheduler.run(False)
#      #swMqtt1.run()
#      return
#
  mqttc.connect(options['--mqtt'])

  while True:
    # loop_start и sleep не используется. (используется ожидание одного пакета и быстрое начало обработки)
    #OFF: time.sleep(1)
    scheduler.run(False)
    for sw in swMqtt:
      sw.run()
    mqttc.loop(timeout=1.0, max_packets=1)
    scheduler.run(False)
    for sw in swMqtt:
      sw.run()

  #mqttc.loop_stop(force=False)
  mqttc.disconnect()





if __name__ == "__main__":
  main()

