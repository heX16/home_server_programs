#!/usr/bin/env python3
# coding: utf-8

#todo: add 'ping' support

"""
Эта программа считывает конфиг ___.csv
и на его основе делает переадресацию (реммапинг) данных внутри MQTT
также может пересчитать данные (изменить число или изменить тип данных).

Направления:
">" - переадресация из extbus в mqtt дерево
  допускается множество адресов mqtt дерева - при подступлении данных произойдет запись во множество путей mqtt
  (для каждого адреса может быть свой пересчет)
"<" - переадресация из mqtt в extbus
  допускается множество адресов extbus - при одной записи в mqtt дерево произойдет множество записей в extbus адреса
  (для каждого адреса может быть свой пересчет)

"""

usage = """
Usage: mqtt_remap.py --config=FILE [--mqtt=HOST] [--quiet | --verbose] [--test]

Options:
  --config=FILE  ODS file with config
  --mqtt=HOST    MQTT server name  [default: localhost]
  --quiet        print less text
  --verbose      print more text
  --test         test (debug) mode
"""

#todo: сделать поддержку JSON путей в данных топика
#todo: сделать поддержку удаления данных из retain (?)

import sys
import re
import io
import csv
import logging
import paho.mqtt.client as mqtt # pip install paho-mqtt
from CaseInsensitiveDict import *
from math import *
from docopt import docopt

# не подходит, умеет только структуры парсить и отдавать (ну и еще подсчитывать константы типа 2+2)
# from ast import literal_eval

# global vars:

v = 1

remapToMqtt = dict()
#remapToMqtt = {
#  (8,1): [('home/temper1', 'round(v*0.065, 1)')],
#  (8,1): [('home/temper1', '"one" if v==1 else "not one"')],
#  (2,4): [('home/newpath2', 'v')] }

remapToExtbus = CaseInsensitiveDict( {} )
# remapToExtbus = {'pathfind': [(1,2, 'v*2'), (1,2, '1 if v=="one" else 0')] }

parseTopic = re.compile('extbus/(.+)/(.+)/(.+)')

# global end.

# address;register;direction;mqtt_path;calc
def load_config(filename):
  global remapToMqtt
  global remapToExtbus
  with open(filename, newline='', encoding="utf-8") as csvfile:
    datareader = csv.reader(csvfile, delimiter=';', quotechar='"')
    first_line = True
    # читаем весь csv построчно
    logging.info('csv:')
    for row in datareader:
      logging.info(str(row))
      # выкачиваем все строки в signals_list
      if first_line:
        first_line = False
        continue

      a,r,dr,path,recalc, save_in_mem, comment = ('','','','','','','')
      if (len(row)>6):
        save_in_mem = row[5].strip()
      if (len(row)>5):
        recalc = row[4].strip()
      if (len(row)>4):
        a = row[0].strip()
        r = row[1].strip()
        dr = row[2].strip()
        path = row[3].strip()
      else:
        logging.info('Skip:' + str(row))
        continue

      a = int(a)
      r = int(r)
      if dr=='>' or dr=='R>':
        i = remapToMqtt.get( (a,r), [])
        i.append( (path, recalc, dr) )
        remapToMqtt[(a,r)] = i;
      if dr=='<' or dr=='<W':
        i = remapToExtbus.get( path, [])
        i.append( (a, r, recalc, dr) )
        remapToExtbus[path] = i;

# The callback for when the client receives a CONNACK response from the server.
def on_connect(client, userdata, flags, rc):
    logging.info("Connected with result code "+str(rc))
    # Subscribing in on_connect() means that if we lose the connection and
    # reconnect then subscriptions will be renewed.
    client.subscribe("extbus/+/+/r")
    client.subscribe("extbus/+/+/w")
    #client.subscribe("extbus/+/+/p")
    for i in remapToExtbus.keys():
      logging.info('subscribe: ' + str(i))
      client.subscribe(i)

def isInt(s):
    try:
        int(s)
        return True
    except ValueError:
        return False

# The callback for when a PUBLISH message is received from the server.
def on_message(client, userdata, msg):
    global v
    #print(msg.topic+"="+str(msg.payload))
    reres = parseTopic.match(msg.topic)
    if reres != None:
      a,r,iomode = (reres.group(1), reres.group(2), reres.group(3))
      try:
        a = int(a)
        r = int(r)
        d = int(msg.payload)
        # если данные записывают в extbus-устройство - значит их нужно "перенести" и записать в mqtt-устройство
        # data from device
        logging.info('a=%s r=%s io=%s d=%s' % (a,r,iomode,d))
        # ищем по ключу "адрес,регистр"
        if (a,r) in remapToMqtt:
          # результат поиска это массив - идем по массиву
          for i in remapToMqtt[(a,r)]:
            # в каждом элементе массива два элемента - "путь" и "пересчет"
            newpath = i[0]
            recalc = i[1]
            dirMode = i[2]
            if (dirMode=='>' and iomode=='w') or (dirMode=='R>' and iomode=='r'):
              value = d
              # пересчет
              if recalc!='':
                v = value
                value = eval(recalc)
              logging.info('-> ' + newpath + '=' + str(value))
              client.publish(newpath, value, retain=False)
      except:
        return # Fail - пришли плохие входные данные, или не отработал eval, игнорим
    # парсинг extbus не удался - значит это какойто другой путь, пробуем поискать в ремапинге
    elif msg.topic.lower() in remapToExtbus:
      # если данные сообщает mqtt-устройство - значит их нужно "перенести" и сообщить от лица extbus-устройства.
      # Если нашли ремап - тогда вперед!
      for i in remapToExtbus[msg.topic.lower()]:
        # (1,2,'v*2','<')
        a = i[0]
        r = i[1]
        recalc = i[2]
        dirMode = i[3]

        # подготавливаем данные
        try:
          # чистим от типа str (если возможно)
          value = float(msg.payload)
        except ValueError:
          value = msg.payload
        if recalc!='':
          v = value # copy to "v"
          try:
            # пробуем вычислить
            value = eval(recalc)
          except:
            value = None
        try:
          value = int(value)
        except ValueError:
          value = None

        # публикуем
        if value != None:
          if dirMode=='<':
            client.publish('extbus/%s/%s/p' % (a, r), value, retain=False)
            client.publish('extbus/%s/%s/r' % (a, r), value, retain=True)
          if dirMode=='<W':
            client.publish('extbus/%s/%s/w' % (a, r), value, retain=False)
          logging.info(msg.topic + ' -> ' + 'extbus/%s/%s/r' % (a, r) + ' = ' + str(value))

### MAIN: ###

def main():
  # параметры
  options = docopt(usage)

  if options['--quiet']:
    level=logging.NOTSET
  elif options['--verbose']:
    level=logging.DEBUG
  else:
    level=logging.ERROR
  logging.basicConfig(stream=sys.stderr, level=level)

  load_config(options['--config'])
  logging.info('remapToExtbus='+str(remapToExtbus))
  logging.info('remapToMqtt='+str(remapToMqtt))

  client = mqtt.Client()
  client.on_connect = on_connect
  client.on_message = on_message

  #msg = mqtt.MQTTMessage()
  #msg.topic = b'extbus/8/1/r'
  #msg.payload = b'400'
  #on_message(client, None, msg)

  if options['--test']:
    os.exit(1)

  client.connect(options['--mqtt'], 1883, 60)
  client.loop_forever() # <- Blocking call!



if __name__ == "__main__":
  main()

