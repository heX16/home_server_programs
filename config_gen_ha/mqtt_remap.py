import sys
import re
import io
import csv
import paho.mqtt.client as mqtt
from CaseInsensitiveDict import *
from math import * # inport to global namespace

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
    for row in datareader:
      # выкачиваем все строки в signals_list
      if first_line:
        first_line = False
        continue
      if (len(row)==5):
        a,r,dr,path,recalc = row
      elif (len(row)==4):
        a,r,dr,path = row
        recalc = ''
      else:
        continue

      a = int(a)
      r = int(r)
      print(a, r, dr, path)
      if dr=='->':
        i = remapToMqtt.get( (a,r), [])
        i.append( (path, recalc) )
        remapToMqtt[(a,r)] = i;
      if dr=='<-':
        i = remapToExtbus.get( path, [])
        i.append( (a, r, recalc) )
        remapToExtbus[path] = i;

# The callback for when the client receives a CONNACK response from the server.
def on_connect(client, userdata, flags, rc):
    print("Connected with result code "+str(rc))
    # Subscribing in on_connect() means that if we lose the connection and
    # reconnect then subscriptions will be renewed.
    client.subscribe("extbus/+/+/w")
    client.subscribe("extbus/+/+/r")
    for i in remapToExtbus.keys():
      print('subscribe: ', i)
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
        if iomode=='r':
          # data from device
          print('a=%s r=%s io=%s d=%s' % (a,r,iomode,d))
          # ищем по ключу "адрес,регистр"
          if (a,r) in remapToMqtt:
            # результат поиска это массив - идем по массиву
            for i in remapToMqtt[(a,r)]:
              # в каждом элементе массива два элемента - "путь" и "пересчет"
              newpath = i[0]
              recalc = i[1]
              value = d
              # пересчет
              if recalc!='':
                v = value
                value = eval(recalc)
              print('-> ', newpath, '=', value)
              client.publish(newpath, value, retain=True)
      except:
        return # Fail - пришли плохие входные данные, или не отработал eval, игнорим
    # парсинг extbus не удался - значит это какойто другой путь, пробуем поискать в ремапинге
    elif msg.topic.lower() in remapToExtbus:
      # Если нашли ремап - тогда вперед!
      for i in remapToExtbus[msg.topic.lower()]:
        # (1,2,'v*2')
        a = i[0]
        r = i[1]
        recalc = i[2]
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
          client.publish('extbus/%s/%s/w' % (a, r), value, retain=True)
          print(msg.topic, '-> ', 'extbus/%s/%s/w' % (a, r), '=', value)

### MAIN: ###

load_config('table.csv')
print(remapToExtbus)

client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message

#msg = mqtt.MQTTMessage()
#msg.topic = b'extbus/8/1/r'
#msg.payload = b'400'
#on_message(client, None, msg)

if len(sys.argv)>1 and sys.argv[1]=='run':
  client.connect("192.168.1.19", 1883, 60)
  client.loop_forever() # <- Blocking call!

