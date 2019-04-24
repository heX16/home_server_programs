from aiomqtt.client import *
from asyncio import *
import logging
from paho.mqtt.client import MQTTMessage
import sys

class bool_int(int):
    ''' https://jfine-python-classes.readthedocs.io/en/latest/subclass-int.html '''

    def __new__(cls, value=0):
      return int.__new__(cls, bool(int(value)))

    def __repr__(self):
      return 'bool_int.' + ['0', '1'][self]

    def __str__(self):
      return '1' if self else '0'



class OurClient(Client):
    messages = {}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


loop = get_event_loop()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class Reader:
    _path_to_receive = None

    def __init__(self, path_to_receive):
        self._path_to_receive = path_to_receive


class Sender:
    _client = None
    _path_to_send = None
    _topic_receiver = None
    _value_to_send = None
    _eval_func = None
    _type_to_conv = None
    _pause = None
    _task = None

    def __init__(self, path_to_send, topic_receiver, eval_func, pause, type_to_conv):
        print(path_to_send, type_to_conv)
        assert isinstance(pause, int) or isinstance(pause, float), 'размер паузы должен быть числом'
        assert not type_to_conv or type_to_conv in ('int', 'float', 'bool', 'str', 'bool_int'), 'Неверный тип для конвертирования'

        self._path_to_send = path_to_send
        self._topic_receiver = topic_receiver
        self._eval_func = eval_func
        self._type_to_conv = type_to_conv
        self._pause = pause

    def __repr__(self):
        return '<Sender({0})>'.format(self._path_to_send)

    @property
    def path_to_send(self):
        return self._path_to_send

    @property
    def task(self):
        return self._task

    def init(self, client):
        self._client = client

    def convert(self, value):
        if not self._type_to_conv:
            return value
        if self._type_to_conv=='bool_int':
          class_type = bool_int
        else:
          class_type = getattr(sys.modules['builtins'], self._type_to_conv)

        if value is None:
            return class_type()
        try:
            return class_type(value)  # конвертируем
        except (ValueError, TypeError):
            return class_type()  # если не получилось, то возвращаем дефолтное значение для данного типа

    def get_value_to_send(self, reciever_value):
        """
        :param reciever_value:  Значение, которое пришло из switch_read
        :return: Значение, которое нужно отправить
        """
        value = self._client.messages.get(self._topic_receiver)

        value = self.convert(value)  # mqtt_read
        reciever_value = self.convert(reciever_value)  # switch_read

        if self._eval_func:
            logger.debug('{0} _eval_func'.format(self))
            v = value
            s = reciever_value
            value = eval(self._eval_func)

            if isinstance(value, bool):
                value = int(value)

            logger.warning('{0} После формулы value = {1}'.format(self, value))

        return value

    def __publish(self, reciever_value):
        self._task = loop.call_later(self._pause, self._client.publish, self._path_to_send, str(self.get_value_to_send(reciever_value)))

    def publish(self, reciever_value):
        logger.warning('{0} Отправка в {1} через {2} с'.format(self, self._path_to_send, self._pause))
        self.__publish(reciever_value)


class Receiver:
    _receive_path = ''
    # senders - словарь, где ключ - то, на что трегирримся, значение - пути к топикам
    # Если в пути нет триггера, то в senders только ключь None со списокм Sender
    senders = {None: []}

    def __init__(self, receive_path):

        self._receive_path = receive_path

    def init(self, client: Client):
        assert self.senders, 'Ни один приёмник неопределён'
        client.subscribe(self._receive_path)  # Подписываемся
        logger.warning('{0} Подписался'.format(self._receive_path))
        client.message_callback_add(self._receive_path, self.receive)
        assert self.senders and isinstance(self.senders, dict)
        for sender_list in self.senders.items():
            for sender in sender_list[1]:
                sender.init(client)

    @property
    def receive_path(self):
        return self._receive_path

    def __repr__(self):
        return '<Receiver({0})>'.format(self._receive_path)

    def receive(self, client, user_data, message: MQTTMessage):
        message = message.payload.decode()

        # Если в Receiver'e нет Sender'ов, которые реагируют на все значения и пришло не то, на которое нужно реагировать
        if not self.senders.get(None) and not self.senders.get(message):
            return

        # Если пришел триггер, то берем sender'ы по нему, иначе берем те, которые реагируют на всё

        sender_list = self.senders.get(message, self.senders.get(None))

        logger.warning('{0} Тригернулся на = {1}'.format(self, message))
        for sender in sender_list:  # Пришли новые данные - отменяем отправку прошлых даных, которые еще не отправлены
            if sender.task:
                sender.task.cancel()
            sender.publish(message)


