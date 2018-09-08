from enum import Enum
import sched
import pprint
from easy_timer import *

class SmartMotDetSwitch:
  ''' Smart Motion Detect Switch
  Алгоритм включения света с датчиком движения.
  Алгоритм, краткое описание:
    Если свет включен вручную то датчик движения игнорируется.
    Если свет включен датчиком движения то свет можно выключить вручную.
    Дополнительные условия:
      Датчик движения включает свет на 60 секунд,
      если в течении этого времени есть повторное движение то таймер начитает отсчет сначала.
      Если свет включен автоматически но затем выключен вручную, то датчик движения игнорируется 5 секунд.
  '''

  class States(Enum):
    ''' subclass: Состояния автомата (см процедуру automate)'''
    init = 0                # 0. Инициализация.
    disable = 1             # 1. Свет отключен.
    enable_by_switch = 2    # 2. Свет включен кнопкой.
    enable_by_dist = 22     # 2.2 Свет включен смартфоном.
    enable_auto = 3         # 3. Свет включен автоматически.
    disable_lock_motdet = 4 # 4. Свет отключен, игнор ДД 10 секунд.

  class DataIn:
    ''' subclass: Входные данные для алгоритма '''
    def __init__(self):
      self.relay = None # новое состояние реле. ВНИМАНИЕ: эта переменная принимает True или False на один цикл при изменении. а затем всегда ==None.
      self.motion = False # движение вызывающее сработку
      self.motion_low = False # слабое движение - поддерживает сработавший датчик
      self.switch = False # нажатие кнопки (включателя или смартфоном)
      self.t_motdet_ignore = False # сработка таймера "время выключения света при автоматическом включении"
      self.t_light_off = False # сработка таймера "время игнорирования данных от датчика движения"
      self.auto_off = False # автоматика отключена. только ручное управление

  class DataOut:
    ''' subclass: Выходные данные для алгоритма '''
    def __init__(self):
      self.enabled = False # состояние реле (True - включить свет)
      self.ignore_change = False # флаг 'не высылать команду при изменении enabled'. ВНИМАНИЕ: снимать флаг нужно 'снаружи' (вручную)

  def __init__(self, scheduler, time_light_active = 60, time_motdet_ignore = 5):
    self.state = self.States.init # состояние алгоритма
    self.t_light_off = EasyTimer(scheduler, time_light_active)  # время выключения света при автоматическом включении
    self.t_motdet_ignore = EasyTimer(scheduler, time_motdet_ignore) # время игнорирования данных от датчика движения
    self.data_in = self.DataIn() # входные данные
    self.data_out = self.DataOut() # выходные данные

  def enabled(self):
    return self.data_out.enabled

  def automate(self, data_in, data_out):
    ''' Автомат (Конечный автомат)
    Switch-технология — https://ru.wikipedia.org/wiki/Switch-технология
    '''

    st = self.States # сокращение идентификатора (для удобства чтения)

    # 0. Инициализация.
    if self.state==st.init:
        if data_in.relay == False:
          self.state=st.disable
        if data_in.relay == True:
          self.state=st.enable_by_switch

    # 1. Свет отключен.
    elif self.state==st.disable:
        # останавливаем таймеры - они тут не нужны
        self.t_light_off.stop()
        self.t_motdet_ignore.stop()

        # При нажатии кнопки (включателя или смартфоном) свет включается. Данные от ДД начинают полностью игнорироваться.
        if data_in.switch:
          self.state = st.enable_by_switch
        if data_in.relay == True:
          data_out.ignore_change = True
          self.state = st.enable_by_dist

        # При сработке ДД. Свет включается.
        if data_in.motion:
          self.state = st.enable_auto

    # 2. Свет включен кнопкой.
    elif self.state==st.enable_by_switch or self.state==st.enable_by_dist:
        # Выдаем флаг что свет нужно включить
        data_out.enabled = True
        # останавливаем таймеры
        self.t_light_off.stop()
        self.t_motdet_ignore.stop()

        # При нажатии кнопки (включателя или смартфоном) свет выключается.
        if data_in.switch:
          self.state = st.disable_lock_motdet
        if data_in.relay == False:
          data_out.ignore_change = True
          self.state = st.disable_lock_motdet

    # 3. Свет включен автоматически.
    elif self.state==st.enable_auto:
        data_out.enabled = True
        self.t_light_off.start_once()
        self.t_motdet_ignore.stop()

        # При завершении таймера свет отключается.
        if data_in.t_light_off:
          self.state = st.disable

        # При нажатии кнопки свет выключается
        if data_in.switch:
          self.state = st.disable_lock_motdet

        # Если реле выключилось - значит ктото его выключил (включателем или смартфоном)
        if data_in.relay == False:
          data_out.ignore_change = True
          self.state = st.disable_lock_motdet

        # При сработке ДД таймер перезапускается (начинается отсчет сначала).
        if data_in.motion or data_in.motion_low:
          self.t_light_off.start()

    # 4. Свет отключен, игнор ДД 10 секунд.
    elif self.state==st.disable_lock_motdet:
        self.t_light_off.stop()
        self.t_motdet_ignore.start_once()

        # При нажатии кнопки (включателя или смартфоном) включаем свет.
        if data_in.switch:
          self.state = st.enable_by_switch
        if data_in.relay == True:
          data_out.ignore_change = True
          self.state = st.enable_by_switch

        # При завершении таймера начинаем учитывать данные от ДД.
        if data_in.t_motdet_ignore:
          self.state = st.disable

  def run(self):
    # подготовка данных
    if self.data_in.auto_off:
      self.data_in.motion = False
    self.data_out.enabled = False
    self.data_in.t_light_off = self.t_light_off.Q
    self.data_in.t_motdet_ignore = self.t_motdet_ignore.Q
    # алгоритм
    self.automate(self.data_in, self.data_out)
    # зачистка
    if self.data_in.relay != None:
      self.data_in.relay = None
    self.data_in.switch = False
    self.data_in.motion = False



def test():
  scheduler = sched.scheduler()
  sw = SmartMotDetSwitch(scheduler)
  sw.run()
  pprint.pprint(sw.state)

  def print_time(name):
    print('time test:', name)

  scheduler.enter(2, 1, print_time, argument=('test123',))

  Ended = False
  while (not Ended):
    scheduler.run(False)
    sw.run()
    #print(len(scheduler.queue))
    if sw.data_out.enabled:
      print('enabled!')
    s = input(sw.state)
    # сбрасываем входные данные
    sw.data_in = SmartMotDetSwitch.DataIn()
    # выставляем
    if s=='s':
      sw.data_in.switch=True
    elif s=='d':
      sw.data_in.motion=True
    elif s=='x':
      Ended=True



