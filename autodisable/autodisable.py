#!/usr/bin/env python3
# coding: utf-8

"""
После включения реле эта программа отключает его через некоторое время.
Например: через 4 часа для света, и через 10 минут для вентилятора.
Эта программа считывает конфиг _____.ods - и следит только за "регистрами" которые описаны в конфиге.
"""

usage = """
Usage: autodisable.py --config=FILE [--mqtt=HOST] [--quiet | --verbose]

Options:
  --config=FILE  ODS file with config
  --mqtt=HOST    MQTT server name  [default: localhost]
  --quiet        print less text
  --verbose      print more text
"""

import sys
import re
import io
import os
import csv
import time
import sched
import logging
from pathlib import Path
import glob
import pyexcel as pe # pip install pyexcel & pip install pyexcel-ods
import paho.mqtt.client as mqtt # pip install paho-mqtt
from docopt import docopt
from math import *
from pprint import *

from mqtt_variable import *
from easy_timer import *

def find_signature(names_list, signature):
  for v in names_list:
    if v.lower().find(signature.lower()) != -1:
      return v

def find_signature_index(names_list, signature):
  for i,v in enumerate(names_list):
    if v.lower().find(signature.lower()) != -1:
      return i

def load_from_sheet(book, page_name):
  data = []

  sh = book.sheet_by_name(page_name)
  for row in sh.rows():
    data.append([])
    for c in row:
      data[-1] = data[-1] + [str(c)]
  return data

class csMqttVarAutodisable(csMqttVarRemove):
  ''' Класс MQTT переменной который при появлении "1" (включении), по истечению времени пишет "0" (выключает). '''

  def __init__(self, mqtt_client, event_list: csMqttEvents, sheduler, path: str, default = None, filter_proc = None, on_change = None, desc = '', off_time = 0):
    super().__init__(mqtt_client = mqtt_client, event_list = event_list, path = path, default = default, filter_proc = filter_proc, on_change = on_change, desc = desc)
    self.sheduler = sheduler
    self.timer_off = TimerEvent(self.sheduler, float(off_time) * 60, self.do_disable)

  def change_event(self, new_value):
    super().change_event(new_value)
    if new_value == '1':
      if self.timer_off.time > 0:
        self.timer_off.start()
        logging.debug(self.path + ' timer enabled (' + str(self.timer_off.time / 60) + 'm)')
    else:
      self.timer_off.stop()

  def do_disable(self):
    if self.timer_off.time > 0:
      self.set_value('0')
      logging.debug(self.path + ' disabled by time')



def main():
  # параметры
  options = docopt(usage)

  # сообщения
  if options['--quiet']:
    level=logging.NOTSET
  elif options['--verbose']:
    level=logging.DEBUG
  else:
    level=logging.ERROR
  logging.basicConfig(stream=sys.stderr, level=level)

  # загрузить файл и извлечь конфиг
  logging.info('load ODS file')
  book = pe.get_book(file_name = options['--config'])
  names = book.sheet_names()
  page_name = find_signature(names, 'sig')
  page_data = load_from_sheet(book, page_name)
  book = None

  idx_desc = find_signature_index(page_data[0], '(desc)')
  idx_time = find_signature_index(page_data[0], '(time)')
  idx_mqtt = find_signature_index(page_data[0], '(mqtt)')

  logging.info('init')

  # расписание
  scheduler = sched.scheduler()

  # события
  mqttEvents = csMqttEvents()
  # initialise MQTT broker connection
  mqttClient = paho.Client('autodisable01')
  mqttClient.on_connect = mqttEvents.connect_event_slot

  mqttVars = []

  my_iter = iter(page_data)
  next(my_iter)
  for row in my_iter:
    if row[idx_time]!='' and row[idx_mqtt]!='':
      logging.info('name:' + row[idx_desc] + ' time:' + row[idx_time] + ' mqtt:' + row[idx_mqtt])
      mqttVars.append( csMqttVarAutodisable(mqttClient, mqttEvents, scheduler, row[idx_mqtt], desc = row[idx_desc], off_time = float(row[idx_time])) )

  page_data = None

  logging.info('mqtt connect')

  mqttClient.connect(options['--mqtt'])

  logging.info('run')
  while True:
    scheduler.run(False)
    mqttClient.loop(timeout=1.0, max_packets=1)

  mqttClient.disconnect()


if __name__ == "__main__":
  main()


