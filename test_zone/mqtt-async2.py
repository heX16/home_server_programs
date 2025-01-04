# pip install aiomqtt
import asyncio
import aiomqtt
import datetime
import random

loop = asyncio.get_event_loop()

async def my_sleep_func():
    await asyncio.sleep(random.randint(0, 5))

async def display_date(num, loop):
    end_time = loop.time() + 50.0
    while True:
        print("Loop: {} Time: {}".format(num, datetime.datetime.now()))
        if (loop.time() + 1.0) >= end_time:
            break
        await my_sleep_func()

def test():
  print("call test!")



async def demo():
    #asyncio.ensure_future(display_date(1, loop))
    #asyncio.ensure_future(display_date(2, loop))

    c = loop.call_later(1, test)
    c = loop.call_later(5, test)
    c = loop.call_later(10, test)


    c = aiomqtt.Client(loop)
    c.loop_start()  # See "About that loop..." below.

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
    await subscribed.wait()
    print("Subscribed to my/test/path")

    def on_message(client, userdata, message):
        print("Got message:", message.topic, message.payload)
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

loop.run_until_complete(demo())



