#!/usr/bin/env python3

#todo: use async io

import paho.mqtt.client as paho  # pip install paho-mqtt
import yaml  # pip3 install pyyaml
import math
import time
import sched
import logging
import sys
import io
import pprint
from copy import copy, deepcopy
from docopt import docopt
import datetime
from smart_motion_control_lib import *
import sunset_lib

usage = '''
Usage: install_service.py [--config=FILE] [--mqtt=HOST] [--quiet] [--verbose] [--show]

Options:
  --config=FILE  config file       [default: config.yaml]
  --mqtt=HOST    MQTT server name  [default: localhost]
  --quiet        print less text
  --verbose      print more text
  --show         show config info, not run daemon
'''

debug = True

mqttEvents = None


def s(b):
    return b.decode("utf-8")


class csMotionDetectorOptions:
    """ Опции """

    def __init__(self):
        self.name = ''            # "человеческое" имя
        self.relay_r = ''         # mqtt путь к реле (чтение)
        self.relay_w = ''         # mqtt путь к реле (запись)
        self.mot_det_r = ''       # mqtt путь к ДД (чтение)
        self.time_motion = 60     # длительность включения света от сработки ДД (в секундах)
        self.time_switch_off = 5  # длительность отключения самого ДД при выключении вручную (смартфоном или включателем) (в секундах)
        self.time_off_start1 = 0  # указывается час начиная с которого отключается ДД. (указывается в часах 0..24)
        self.time_off_len1 = 0    # продолжительность отключения. (указывается в часах 0..24)
        self.time_off_start2 = 0  # идентично time_off_start1
        self.time_off_len2 = 0    # идентично time_off_len1
        self.enabled_on_day = 0   # включен днем. если 0 то значит режим выключен и учитывается закат/восход солнца. если 1 значит режим включен и ДД работает круглосуточно.
        self.sunset = -0.5        # активация ДД после захода солнца. если 0 то значит сразу после захода. другое число указывает смещение в часах от начала захода. по умолчанию -0.5 (за полчаса до захода). (указывается в часах -24..+24)
        self.sunrise = 0.5        # снятие активации после восхода солнца. если 0 то значит сразу после захода. другое число указывает смещение в часах. по умолчанию 0.5 (через полчаса после восхода).
        self.switch_r = ''        # (НЕРАБОТАЕТ) mqtt путь включатель кнопочный (чтение)
        # self.disable_r=''       # (НЕРАБОТАЕТ) mqtt путь - отключить ДД


class csMqttEventCollector:
    ''' Вызывает события при событии (проблема в том что у MQTT объекта только один "слот" для события. А мне нужно много. '''

    # todo: избавится от csMqttEventCollector ИЛИ csMqttEvents - должен остаться только один...

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


class csMotionDetectorMqtt:
    ''' Принимаем данные от MQTT и передаем их в алгоритм.
      Также получаем результаты от алгоритма и передаем их в MQTT.
  '''

    def __init__(self, switch_obj, mqtt_client, event_list, events_list2, cfg: csMotionDetectorOptions):
        self.mqtt_client = mqtt_client
        self.switch = switch_obj
        self.cfg = cfg
        self.prev_switch = None
        self.prev_mot_det = None
        self.prev_out_enabled = None
        self.prev_state = 0  # предыдущее состояние
        self.event_list = event_list
        self.events_list2 = events_list2
        # bool filter: lambda m: True if m=='1' else False)
        self.events_list2.add_connect_event(self.event_connect)
        self.events_list2.add_disconnect_event(self.event_disconnect)

    def event_connect(self, client, userdata, flags, rc):
        def sub(path, event):
            if type(path) == str and path != '':
                self.mqtt_client.subscribe(path)
                # todo: ??? - он проверяет на повторное добавление??? или будет двойной вызов?
                self.mqtt_client.message_callback_add(path, event)

        # добавляем обработчики изменений топиков MQTT
        sub(self.cfg.relay_r, self.event_relay)
        sub(self.cfg.mot_det_r, self.event_mot_det)
        sub(self.cfg.switch_r, self.event_switch)
        # "дергаем" обьекты чтобы они подписались на топики
        #todo: ??? self.event_list.connect_event()
        logging.debug("ReConnect: " + self.cfg.name)

    def event_disconnect(self, client, userdata, rc):
        if rc != paho.MQTT_ERR_SUCCESS:
            logging.debug('mqtt dissconect detected')
            time.sleep(2)
            client.reconnect()

    def event_relay(self, client, userdata, msg):
        ''' Изменение: состояния реле (удаленного включателя) '''

        # 'парсим' входящие данные
        d = True if s(msg.payload) == '1' else False

        logging.debug('event_relay d=' + str(d) + ' name=' + self.cfg.name)

        # передаем данные в алгоритм
        self.switch.data_in.relay = d

    def event_switch(self, client, userdata, msg):
        ''' Изменение: состояния механического включателя '''

        # 'парсим' входящие данные
        d = True if s(msg.payload) == '1' else False
        logging.debug('event_switch d=' + str(d) + ' name=' + self.cfg.name)

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
        d = True if s(msg.payload) == '1' else (False if s(msg.payload) == '0' else None)
        logging.debug('event_mot_det d=' + str(d) + ' name=' + self.cfg.name)

        if d!=None:
          # 'инициализируем' (если это первое обращение к данным)
          if self.prev_mot_det is None:
              self.prev_mot_det = not d

          # если данные изменились - передаем их в алгоритм, но передаем только если 0->1
          # ВНИМАНИЕ: снимать флаг 'self.switch.data_in.motion' нужно 'снаружи' (вручную)
          if self.prev_mot_det != d:
              self.prev_mot_det = d
              if d == True:
                  logging.debug('mot_det: 0->1 ' + str(d) + ' name=' + self.cfg.name)
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
            # обычная проверка (причем если диапазон выходит за 24 часа то нас это не заботит - ошибки не будет)
            if hour >= start and hour < start + length:
                return True
        return False

    def get_current_hour(self):
        return datetime.datetime.now().hour + datetime.datetime.now().minute / 60  # 0.0 - 23.99
        # return datetime.now().hour # 0..23

    def is_disable_hour(self, hour):
        ''' Проверка времени - True значит мы попали в "запрещенные часы" '''

        if self.check_time(hour, self.cfg.time_off_start1, self.cfg.time_off_len1):
            return True
        if self.check_time(hour, self.cfg.time_off_start2, self.cfg.time_off_len2):
            return True
        if self.cfg.enabled_on_day:
            return False
        else:
           t_begin = datetime.datetime.combine(datetime.datetime.today(), sun.sunset())  + datetime.timedelta(hours=self.cfg.sunset)
           t_end   = datetime.datetime.combine(datetime.datetime.today(), sun.sunrise()) + datetime.timedelta(hours=self.cfg.sunrise, days=1)
           t_begin2= datetime.datetime.combine(datetime.datetime.today(), sun.sunset())  + datetime.timedelta(hours=self.cfg.sunset, days=-1)
           t_end2  = datetime.datetime.combine(datetime.datetime.today(), sun.sunrise()) + datetime.timedelta(hours=self.cfg.sunrise)
           t = datetime.datetime.now()
           if (t > t_begin and t < t_end) or (t > t_begin2 and t < t_end2):
             return False
           else:
             return True


    def run(self):
        ''' Запуск системы '''

        if self.is_disable_hour(self.get_current_hour()):
            # настал "тихий час" когда датчик движения не срабатывает
            self.switch.data_in.motion = False

        # алгоритм
        self.switch.run()

        # если вывод изменился - тогда обрабатываем
        if self.switch.data_out.enabled != self.prev_out_enabled:
            self.prev_out_enabled = self.switch.data_out.enabled
            if self.switch.data_out.ignore_change or (self.cfg.switch_r=='' and self.switch.data_out.enabled_by_switch):
                # если есть флага "игнорирование"
                # или если включен через включатель но при этом мы этот включатель не обслуживаем
                # тогда ничего не делаем
                # но сбрасываем флаг - он внутри алгоритма не сбрасывается.
                self.switch.data_out.ignore_change = False
            else:
                d = self.switch.data_out.enabled
                logging.debug('write to relay: ' + str(d) + ' mqtt_path=' + self.cfg.relay_w)
                # также вручную и "тихо" изменяем состояние реле в памяти - чтобы после записи в mqtt оно проигнорировало это событие
                self.switch.data_in.relay = d
                # высылаем команду ('0' или '1')
                self.mqtt_client.publish(self.cfg.relay_w, str(int(d)))

        # сбрасываем флаг
        self.switch.data_in.motion = False

        # логгируем состояние
        if self.switch.state != self.prev_state:
            self.prev_state = self.switch.state
            logging.debug('state: ' + str(self.prev_state))


def dict_to_object(config_dict: dict, obj):
    ''' Присваивает словарь в обьект '''
    for k, v in config_dict.items():
        setattr(obj, k, v)


def load_config(filename: str):
    # Read YAML file
    with open(filename, 'r', encoding='utf8') as stream:
        data = yaml.safe_load(stream)

    if 'default' in data:
        cfg_def = data['default']
    else:
        cfg_def = {}

    conf_list = []
    for i in data['motion_detectors']:
        conf = csMotionDetectorOptions()
        dict_to_object(cfg_def, conf)
        dict_to_object(i, conf)
        conf_list = conf_list + [conf]

    if 'config' in data:
        config = data['config']
    else:
        config = {}

    return (conf_list, config)


def main():
    global sun

    # параметры
    options = docopt(usage)

    if options['--quiet']:
        level = logging.NOTSET
    elif options['--verbose']:
        level = logging.DEBUG
    else:
        level = logging.ERROR
    logging.basicConfig(stream=sys.stderr, level=level)

    # конфиг
    cfg_list, config = load_config(options['--config'])

    sun = sunset_lib.sun(config['lat'], config['lon'])

    # события
    #todo: удалить эту хрень отовсюду
    mqttEvents = None

    # расписание
    scheduler = sched.scheduler()

    # todo: ... opt.switch_r='extbus/2/25/r', - не работает, входит в бесконечное переключение. отладить нехватает времени, да и нет нужды особой...

    # initialise MQTT broker connection
    #mqttc = paho.Client('smartswitch01')
    mqttc = paho.Client()

    eventsCollector = csMqttEventCollector(mqttc)

    swMqtt = []

    # создаем переключатели
    for cfg in cfg_list:
        logging.info("Cfg name:" + cfg.name)
        # создаем переключатель
        switchTmp = MotionDetectorAlgo(scheduler, cfg.time_motion, cfg.time_switch_off)

        # создаем переключатель подключенный к mqtt
        swMqtt = swMqtt + [csMotionDetectorMqtt(switchTmp, mqttc, mqttEvents, eventsCollector, deepcopy(cfg))]

    debug = False
    if debug:
        logging.debug('DEBUG MODE!')

        switchTmp = MotionDetectorAlgo(scheduler, 30, 5)
        swMqtt1 = csMotionDetectorMqtt(switchTmp, mqttc, mqttEvents, eventsCollector, cfg)

        logging.debug('DD disable: ' + str(swMqtt1.is_disable_hour(swMqtt1.get_current_hour())))
        # scheduler.run(False)
        # swMqtt1.run()
        return

    if options['--show']:
        logging.basicConfig(stream=sys.stderr, level=logging.INFO)
        for sw in swMqtt:
            t_begin = datetime.datetime.combine(datetime.datetime.today(), sun.sunset())  + datetime.timedelta(hours=sw.cfg.sunset)
            t_end   = datetime.datetime.combine(datetime.datetime.today(), sun.sunrise()) + datetime.timedelta(hours=sw.cfg.sunrise, days=1)
            logging.info('Switch: '+str(sw.cfg.name))
            logging.info('  Sunset begin: '+str(t_begin))
            logging.info('  Sunset end: '+str(t_end))
        return

    mqttc.connect(options['--mqtt'])

    try:
        while True:
            # loop_start и sleep не используется. (используется ожидание одного пакета и быстрое начало обработки)
            # OFF: time.sleep(1)
            scheduler.run(False)
            for sw in swMqtt:
                sw.run()
            mqttc.loop(timeout=2.0, max_packets=1)
            scheduler.run(False)
            for sw in swMqtt:
                sw.run()
    finally:
        # mqttc.loop_stop(force=False)
        mqttc.disconnect()

sun = None

if __name__ == "__main__":
    main()
