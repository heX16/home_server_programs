
import sched

class EasyTimer:
  def __init__(self, scheduler, time):
    self.scheduler = scheduler # расписание (то что хранит таймеры)
    self.event_ptr = None   # экземпляр таймера
    self.time = time # время работы таймера
    self.Q = False # флаг сработки таймера

  def timer_event(self):
    self.Q = True
    self.event_ptr = None

  def enabled(self):
    return False if self.event_ptr is None else True

  def start_once(self):
    if not self.enabled():
      self.Q = False
      self.event_ptr = self.scheduler.enter(self.time, 1, self.timer_event)

  def stop(self):
    if self.enabled():
      self.Q = False
      try:
        self.scheduler.cancel(self.event_ptr)
      finally:
        self.event_ptr = None

  def start(self):
    self.stop()
    self.start_once()

  def run():
    pass

class TimerEvent(EasyTimer):
  ''' Таймер который при сработке вызывает процедуру "on_timer" '''

  def __init__(self, scheduler, time, event):
    super().__init__(scheduler, time)
    self.on_timer = event

  def timer_event(self):
    super().timer_event()
    self.on_timer()


