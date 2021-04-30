import csv
from mqtt_dev_lib import *
from docopt import docopt
import logging as log

usage = """
Usage: autodisable.py --config=FILE [--mqtt=HOST] [--quiet | --verbose]

Options:
  --config=FILE  ODS file with config
  --mqtt=HOST    MQTT server name  [default: localhost]
  --quiet        print less text
  --verbose      print more text
"""

def loadConfig(filename):
    #todo: move to function result
    global receivers_objects
    global topic_mqtt_read
    global mqtt_read_paths
    data = []
    with open(filename) as csvfile:
        data = list(csv.reader(csvfile, delimiter=';'))[1:]
    assert data

    #todo: auto find index?
    index_mqtt_switch_read = 0
    index_mqtt_write = 1
    index_value = 2
    index_pause = 3
    index_mqtt_read = 4
    index_type = 5
    index_desc = 6

    receivers = []
    mqtt_read_paths = set()

    rec = None
    trigger_value = None

    for index, row in enumerate(data):
        logger.debug('CONFIG LINE {0}: {1}. CellsInRow={2}'.format(index, row, len(row)))

        if not row[index_mqtt_switch_read] and not row[index_mqtt_write]:
            # Если есть данные для mqtt_write, но их некуда записывать
            logger.warn('Пропускаем строку {0}'.format(index))
            continue

        if not row[index_mqtt_switch_read] and not row[index_mqtt_write]:
            # Пустая строка
            logger.warn('Пропускаем строку {0}'.format(index))
            continue

        if row[index_type]:
            type_to_conv = row[index_type]

        if row[index_mqtt_switch_read]:
            rec = list(filter(lambda receiver: receiver['path'] == row[index_mqtt_switch_read].split('==')[index_mqtt_switch_read], receivers))
            split_path = row[index_mqtt_switch_read].split('==')
            trigger_value = split_path[1] if len(split_path) == 2 else None
            if not rec:
                receivers.append({'senders': {trigger_value: []}, 'path': split_path[0]})
            else:
                assert not rec[0]['senders'].get(trigger_value), 'receiver с таким путем и триггерным значением уже существует'
                rec[0]['senders'][trigger_value] = []

        if row[index_mqtt_write]:

            path_to_receive = row[index_mqtt_read] if row[index_mqtt_read] else None
            if path_to_receive:
                mqtt_read_paths.add(path_to_receive)

            eval_func = row[index_value] if row[index_value] else None
            pause = float(row[index_pause]) if row[index_pause] else 0

            sender = (row[index_mqtt_write], path_to_receive, eval_func, pause, type_to_conv)
            if not rec:
                receivers[-1]['senders'][trigger_value].append(sender)
            else:
                rec[0]['senders'][trigger_value].append(sender)

    receivers_objects = []
    for receiver in receivers:
        rec_obj = Receiver(receiver['path'])
        rec_obj.senders = {trigger_val: [Sender(*args) for args in senders] for trigger_val, senders in receiver['senders'].items()}
        receivers_objects.append(rec_obj)

    for receiver in receivers_objects:
        logger.debug(receiver)
        for trigger in receiver.senders.items():
            logger.debug('    <trigger>({0})'.format(trigger[0]))
            for sender in trigger[1]:
                logger.debug('       <Sender>(path={0})'.format(sender))


async def main():
    # параметры
    options = docopt(usage)
    #todo: move to local vars
    global receivers_objects
    global topic_mqtt_read
    global mqtt_read_paths

    # сообщения
    if options['--quiet']:
      level=logging.NOTSET
    elif options['--verbose']:
      level=logging.DEBUG
    else:
      level=logging.ERROR
    logging.basicConfig(stream=sys.stderr, level=level)

    # загрузить файл и извлечь конфиг
    loadConfig(options['--config'])

    c = OurClient()

    #todo: user,pass
    #if options['--mqtt_user']:
    #  c.username_pw_set(options['--mqtt_user'], options['--mqtt_pass'])
    await c.connect(options['--mqtt'])

    def on_message(client, userdata, message: MQTTMessage):
        # save to 'mem'
        client.messages[message.topic] = message.payload.decode()
        logger.warning('{0} Получил значение {1}'.format(message.topic, client.messages[message.topic]))

    c.on_message = on_message

    logger.debug(str(mqtt_read_paths))

    for topic_mqtt_read in mqtt_read_paths:
        logger.warning('{0} Подписался'.format(topic_mqtt_read))
        c.subscribe(topic_mqtt_read)

    for x in receivers_objects:
        x.init(c)

    #todo: timeout=60.0
    await c.loop_forever(timeout=1.0, max_packets=1, retry_first_connection=False)

loop.run_until_complete(main())
