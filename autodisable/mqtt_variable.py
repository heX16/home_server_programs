import paho.mqtt.client as paho   # pip install paho-mqtt
import math
import time
import logging
import sys

#TODO: решить чтото csMqttEvents и его дублем!

def s(b):
  return b.decode("utf-8")

class csMqttEvents:
  ''' Этот обьект заведует только одной функций - при повторном подключении вызвать у зарегистрированных обьектов событие "connect_event" '''

  def __init__(self):
    logging.debug('csMqttEvents.create ok')
    self.connect_events = []

  def reg(self, obj):
    self.connect_events = self.connect_events + [obj]

  def connect_event(self):
    logging.debug('csMqttEvents.connect_event')
    for e in self.connect_events:
      e.connect_event()

  def connect_event_slot(self, client, userdata, flags, result):
    self.connect_event()


#### #### #### #### #### #### #### #### #### #### #### #### #### #### #### ####

class csMqttVar:
  ''' Переменная (абстрактная) '''

  def __init__(self, mqtt_client, event_list: csMqttEvents, path: str, default = None, filter_proc = None, on_change = None, desc = ''):
    #raise NotImplementedError('csMqttVar is abstract')
    self.path = path
    self.desc = desc
    self.value = default
    self.mqtt_client = mqtt_client
    self.filter_proc = filter_proc
    self.on_change = on_change
    event_list.reg(self)

  def path_write(self):
    return self.path+'/w'

  def path_read(self):
    return self.path+'/p'

  def connect_event(self):
    ''' процедура вызывается из csMqttEvents '''
    return

  def write_event(self, client, userdata, msg):
    return

  def change_event(self, new_value):
    if self.on_change != None:
      self.on_change(self, v)

  def set_value(self, value):
    return

class csMqttVarRemove(csMqttVar):
  ''' Удаленная переменная (наблюдатель).
  только следит за '.../r' - слушает сообщения устройства и запонимает текущее состояние. '''

  def connect_event(self):
    logging.debug('csMqttVar.connect_event sub: '+self.path_read())
    self.mqtt_client.subscribe(self.path_read())
    # todo: ??? - он проверяет на повторное добавление??? или будет двойной вызов?
    self.mqtt_client.message_callback_add(self.path_read(), self.write_event)

  def write_event(self, client, userdata, msg):
    v = s(msg.payload).strip()
    # make type transformation and value filter
    if self.filter_proc != None:
      try:
        v = self.filter_proc(v)
      except ValueError:
        logging.error('csMqttVar.write_event invalid value "'+str(v)+'"')
        return
    self.change_event(v)
    logging.debug('csMqttVar.write_event '+str(v))
    # публикуем сообщение - это знак того что переменна принята и обработана (ну и так "принято" в mqtt)
    self.value = v
    return self.value

  def set_value(self, value):
    ''' Пишем в удаленную переменную '''
    if type(value)==str:
      self.mqtt_client.publish(self.path_write(), value)



class csMqttVarLocal(csMqttVar):
  ''' Местная переменная (устройство).
  следит за '/w' и само отписывается на '.../r' - само является устройством и _воспринимает_ записи состояния. '''

  def connect_event(self):
    logging.debug('csMqttVar.connect_event sub: '+self.path_write())
    self.mqtt_client.subscribe(self.path_write())
    # todo: ??? - он проверяет на повторное добавление??? или будет двойной вызов?
    self.mqtt_client.message_callback_add(self.path_write(), self.write_event)

  def write_event(self, client, userdata, msg):
    v = s(msg.payload).strip()
    # make type transformation and value filter
    if self.filter_proc != None:
      try:
        v = self.filter_proc(v)
      except ValueError:
        logging.error('csMqttVar.write_event invalid value "'+str(v)+'"')
        return
    self.change_event(v)
    logging.debug('csMqttVar.write_event '+str(v))
    # публикуем сообщение - это знак того что переменна принята и обработана (ну и так "принято" в mqtt)
    self.value = v
    if type(v)==bool:
      v = 1 if v == True else 0
    self.mqtt_client.publish(self.path_read(), str(v))
    return self.value

  def set_value(self, value):
    ''' Запоминаем новое значение и высылаем нотификацию о смене значения '''
    if type(value)==str:
      self.value = value
      self.mqtt_client.publish(self.path_read(), value)

