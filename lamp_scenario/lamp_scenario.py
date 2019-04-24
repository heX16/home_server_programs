#!/usr/bin/env python3
# coding: utf-8

"""
Ламповые сценарии. =)

При изменении MQTT переменной выполняется изменение других MQTT переменных.

Скрипты изменения умеют следующее:
1. Условия сработки.
Может срабатывать при любом изменении указаной переменной.
Может срабатывать при определенном значении переменной.
OFF: Срабатывать по сложному условию (комбинации переменных).
Срабатывать по таймеру (анимация).
OFF: Срабатывать по времени (расписание).

2. Устанавливать значения с указанной задержкой.
Например при включении: включается три лампы, причем каждая включается на пол-секунды позже предыдущей.

2.1. Новые значение (вкл/выкл) могут интеллектуально вычислятся.


---- ----

3. OFF: Режим ожидания подтверждения - следующая команда посылается после подтвр. предыдущей или через некоторый таймаут.
Подтверждение - это когда от mqtt_read прилетает число которое записали в mqtt_write.

4. OFF: Поддержка плавного включения света.
В переменную пишется не 0/1, а число (0-255/0-65535/0.0-1.0).

5. OFF: Анимации.
Повтор сценария с указанной переодичностью.

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
import paho.mqtt.client as mqtt  # pip install paho-mqtt
# later - import pyexcel as pe # pip install pyexcel & pip install pyexcel-ods
from docopt import docopt
from math import *
from pprint import *
from io import StringIO
import asyncio
import aiomqtt  # pip install aiomqtt
import datetime
import random

from mqtt_variable import *
from easy_timer import *

usage = """
Usage: lamp_scen.csv --config=FILE [--mqtt=HOST] [--quiet | --verbose]

Options:
  --config=FILE  ODS (or CSV) file with config
  --mqtt=HOST    MQTT server name  [default: localhost]
  --quiet        print less text
  --verbose      print more text
"""


def retype(value, typename: str, default=None):
    """
    value - любое значение
    typename - bool, int, float, str
    default - значение которое подставляется если не удалось конвертировать
    """
    if default == None:
        value = default

    try:
        if typename == 'int':
            value = int(value)
        elif typename == 'float':
            value = float(value)
        elif typename == 'bool':
            value = bool(int(value))
        elif typename == 'str':
            value = str(value)
        elif typename == '' or typename == None:
            value = value
        else:
            value = default
    except ValueError:
        value = default
    return value


def retype_default(value, typename: str):
    """ если в процессе конвартирования в функции retype значение стало None (конвертирование не удалось)
  тогда эта функция может превратить None в типизированное нулевое значение.
  """
    if value != None:
        return value
    else:
        if typename == 'int':
            value = 0
        elif typename == 'float':
            value = 0.0
        elif typename == 'bool':
            value = False
        elif typename == 'str':
            value = ''
        else:
            value = ''
    return value


class ScenElem:
    """ элемент сценария """

    def __init__(self):
        # config:
        self.mqtt_write = ''  # куда записывать данные
        self.mqtt_read = ''  # откуда считывать значения (могут понадобится для recalc)
        self.recalc = ''  # формула, через которую пропускается значение которое требуется отправить. recalc (eval).
        self.pause = 0  # пауза перед записью
        self.desc = ''  # описание
        self.value_mqtt = None  # csMqttVarRemove2
        self.retype = ''  # тип в который нужно ретипизировать значение

    def setup(self, mqtt_client, event_list):
        self.value_mqtt = csMqttVarRemove2(mqtt_client, event_list, self.mqtt_read, self.mqtt_write)

    def get_value(self, value_from_trigger) -> str:
        # подготавливаем данные
        value = retype(self.value_mqtt.value, self.retype)
        # если ретипизация не удалась (там None), тогда делаем значение по умолчанию
        value = retype_default(value, self.retype)

        if self.recalc != '':
            # чтобы в eval можно было использовать сокращенные варианты
            v = value  # значение от "mqtt_switch_read"
            s = value_from_trigger # предыдущее значение записанное в "mqtt_write".
            try:
                # пробуем вычислить
                value = eval(self.recalc)
            except:
                value = None
            del v
            del s
        try:
            value = int(value)
        except ValueError:
            value = None

        return value


class ScenGroup:
    """ содержит сценарий который активируется при сработке определенного event """

    def __init__(self, mqtt_switch_read):
        self.mqtt_trigger_read = ''  # переменная которая активирует сценарий
        self.elements = []  # массив элементов
        self.desc = ''  # описание
        self.pause_mode = ''  # режим паузы ['wait', 'pause']
        self.value_mqtt = csMqttVarRemove2()  # переменная от который запускается сценарий

    def trigger_change(self):
        """ сработал триггер - начинаем сценарий """
        # нужно пройтись по всем элементам и выполнить их "предназначение" или добавить их в расписание

        if len(self.elements) > 0:
            for e in self.elements:
                if e.pause == 0:
                    pass #e.set
            pass
        else:
            pass

    def setup(self, mqtt_client, event_list):
        self.mqtt_client = mqtt_client
        self.event_list = event_list

    def add_element(self, mqtt_write, value, pause, mqtt_read, desc):
        e = ScenElem()
        e.mqtt_write = mqtt_write
        e.value = value
        e.pause = pause
        e.mqtt_read = mqtt_read
        e.desc = desc
        self.elements.append(e)


class MainObject:
    def __init__(self, loop):
        pass

    def on_connect(self, client, userdata, flags, rc):
        #connected.set()
        pass

    def on_message(self, client, userdata, message):
        #print("Got message:", message.topic, message.payload)
        pass

    def on_disconnect(self, client, userdata, rc):
        #disconnected.set()
        pass

def load_from_sheet(book, page_name):
    """ читаем таблицу ODS/XLS/XLSX """
    data = []

    sh = book.sheet_by_name(page_name)
    for row in sh.rows():
        data.append([])
        for c in row:
            data[-1] = data[-1] + [str(c)]
    return data


def load_csv(csv_stream):
    """ читаем весь csv построчно в массив """
    datareader = csv.reader(csv_stream, delimiter=';', quotechar='"')
    data = []
    for row in datareader:
        ###logging.info(str(row))
        data = data + [row]
    return data


def load_config(filename: str):
    """ загрузить файл и извлечь конфиг """

    ff, ext = os.path.splitext(filename)

    if ext.lower() == '.csv':
        with open(filename, newline='', encoding='utf-8') as csvfile:
            data = load_csv(csvfile)
    elif ext.lower() == '.ods':
        # try
        #   import import pyexcel as pe
        #   ...
        #   load_from_sheet(...
        logging.error('ods loading not implement!')
        return None
    else:
        logging.error('cant load config - format not support!')
        return None

    # todo: add head detection
    #    idx_desc = find_signature_index(page_data[0], '(desc)')
    #    idx_time = find_signature_index(page_data[0], '(time)')
    #    idx_mqtt = find_signature_index(page_data[0], '(mqtt)')
    del data[0]  # del head
    i_mqtt_switch_read = 0
    i_mqtt_write = 1
    i_value = 2
    i_pause = 3
    i_mqtt_read = 4
    i_type = 5
    i_desc = 6

    imax = len(data)
    scen_list = []
    scen_group = None
    for i, v in enumerate(data):

        if (v[i_mqtt_switch_read] != ''):
            if (scen_group != None):
                scen_list += [scen_group]
            scen_group = ScenGroup(v[i_mqtt_switch_read])
            scen_group.desc = v[i_desc]
            if v[i_mqtt_write] != '':
                scen_group.add_element(v[i_mqtt_write], v[i_value], v[i_pause], v[i_mqtt_read], v[i_desc])
        else:
            if (scen_group != None) and v[i_mqtt_write] != '':
                scen_group.add_element(v[i_mqtt_write], v[i_value], v[i_pause], v[i_mqtt_read], v[i_desc])
            else:
                logging.warn('config skip line number ' + str(i + 1 + 1))
    if (scen_group != None):
        scen_list += [scen_group]

    logging.info('csv loaded.')
    return scen_list



async def demo():
    """ пример использования aiomqtt """
    loop = asyncio.get_event_loop()

    c = aiomqtt.Client(loop)
    c.loop_start()

    connected = asyncio.Event(loop=loop)

    def on_connect(client, userdata, flags, rc):
        connected.set()

    c.on_connect = on_connect

    await c.connect("localhost")
    await connected.wait()

    print("Connected!")

    subscribed = asyncio.Event(loop=loop)

    def on_subscribe(client, userdata, mid, granted_qos):
        subscribed.set()

    c.on_subscribe = on_subscribe

    c.subscribe("my/test/path")

    def write_event(client, userdata, msg):
        print("Got message (by path):", msg.topic, msg.payload)
    def write_event2(client, userdata, msg):
        print("Got message (by path):", msg.topic, msg.payload)

    c.message_callback_add("my/test/path", write_event)
    c.message_callback_add("my/test/path", write_event2)
    c.message_callback_add("my/test/path", write_event)

    await subscribed.wait()

    print("Subscribed to my/test/path")

    def on_message(client, userdata, message):
        print("Got message (all msg):", message.topic, message.payload)

    c.on_message = on_message

    message_info = c.publish("my/test/path", "Hello, world")
    await message_info.wait_for_publish()

    print("Message published!")

    await asyncio.sleep(1, loop=loop)
    print("Disconnecting...")

    disconnected = asyncio.Event(loop=loop)

    def on_disconnect(client, userdata, rc):
        disconnected.set()

    c.on_disconnect = on_disconnect
    c.disconnect()
    await disconnected.wait()

    print("Disconnected")

    await c.loop_stop()
    print("MQTT loop stopped!")


def main():
    #asyncio.get_event_loop().run_until_complete(demo())

    #return

    ### test
    print('TEST!!!')
    logging.basicConfig(stream=sys.stderr, level=logging.DEBUG)
    cfg_list = load_config('D:\Sync\House0-programs\lamp_scenario\lamp_scen-config_example.csv')
    print('cfg_list:')
    for i in cfg_list:
        print('  Z:' + str(i.desc))
        for i2 in i.elements:
            print('     ' + str(i2.mqtt_write))
    return

    ### реальная программа ###

    # параметры
    options = docopt(usage)

    # сообщения
    if options['--quiet']:
        level = logging.NOTSET
    elif options['--verbose']:
        level = logging.DEBUG
    else:
        level = logging.ERROR
    logging.basicConfig(stream=sys.stderr, level=level)

    # scen = ScenGroup()
    # scen.setup( ...!!!!.... )
    # scen.add_element('extbus/1/1/w', 1, 3, '', 'test')

    # cl = loop.call_later(1, test)

    # loop = asyncio.get_event_loop()

    # loop.run_until_complete(demo())


if __name__ == "__main__":
    main()
