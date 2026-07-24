#!/usr/bin/env python3
# coding: utf-8

"""Collect first values from MQTT topics and exit.

Usage:
  mqtt_collect.py [-m HOST] [-p PORT] [--user=USER] [--password=PASS]
                 [--topics=TOPICS] [--topics-file=FILE] [--timeout=SECONDS]
  mqtt_collect.py (-h | --help)

Options:
  -m HOST, --mqtt=HOST, --mqttserver=HOST   MQTT broker host/address [default: localhost]
  -p PORT, --port=PORT                      MQTT broker port number [default: 1883]
  --user=USER                               MQTT username
  --password=PASS                           MQTT password
  -t TOPICS, --topics=TOPICS                Comma-separated list of topics to read (exact topic names)
  --topics-file=FILE                        Path to a text file with topics (one topic per line)
  --timeout=SECONDS                         Timeout in seconds to wait for all topics [default: 5]

Output:
  Prints collected values to stdout as:
    topic: value
"""

from __future__ import annotations

import sys
import time
import threading
from typing import Dict, List

from docopt import docopt


def eprint(*args) -> None:
    print(*args, file=sys.stderr)


def parse_topics_csv(raw: str) -> List[str]:
    topics: List[str] = []
    for part in str(raw).split(','):
        t = part.strip()
        if not t:
            continue
        topics.append(t)
    return topics


def read_topics_file(path: str) -> List[str]:
    topics: List[str] = []
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            t = line.strip()
            if not t:
                continue
            if t.startswith('#'):
                continue
            topics.append(t)
    return topics


def dedupe_keep_order(items: List[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for x in items:
        if x in seen:
            continue
        seen.add(x)
        out.append(x)
    return out


def main() -> int:
    args = docopt(__doc__)

    host = args['--mqttserver'].strip()
    port = int(args['--port'])

    user = args.get('--user')
    password = args.get('--password')
    if password and not user:
        eprint('Error: --password requires --user')
        return 1

    timeout_s = float(args['--timeout'])

    topics: List[str] = []
    if args.get('--topics'):
        topics += parse_topics_csv(args['--topics'])
    if args.get('--topics-file'):
        try:
            topics += read_topics_file(args['--topics-file'])
        except Exception as ex:
            eprint(f'Error: cannot read --topics-file: {ex}')
            return 1

    topics = dedupe_keep_order([t for t in topics if t])
    if not topics:
        eprint('Error: no topics provided. Use --topics=... and/or --topics-file=...')
        return 1

    collected: Dict[str, str] = {}
    done = threading.Event()
    connected = threading.Event()
    connect_failed: Dict[str, str] = {}
    lock = threading.Lock()

    def maybe_done() -> None:
        if len(collected) >= len(topics):
            done.set()

    def on_connect(client, userdata, flags, rc) -> None:
        if rc != 0:
            connect_failed['reason'] = f'MQTT connect failed (rc={rc})'
            connected.set()
            done.set()
            return

        for t in topics:
            try:
                client.subscribe(t, qos=0)
            except Exception:
                continue
        connected.set()

    def on_message(client, userdata, msg) -> None:
        topic = str(getattr(msg, 'topic', '') or '')
        if topic not in topics:
            return

        payload_bytes = getattr(msg, 'payload', b'')
        try:
            value = payload_bytes.decode('utf-8', errors='replace')
        except Exception:
            value = str(payload_bytes)

        with lock:
            if topic in collected:
                return
            collected[topic] = value.strip()
            maybe_done()

    try:
        import paho.mqtt.client as mqtt
    except ImportError:
        eprint('Error: missing dependency "paho-mqtt". Install it with: pip install paho-mqtt')
        return 1

    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message
    if user:
        client.username_pw_set(user, password=password)

    try:
        client.connect(host, port, keepalive=60)
    except Exception as ex:
        eprint(f'Error: cannot connect to MQTT broker {host}:{port}: {ex}')
        return 1

    client.loop_start()

    deadline = time.monotonic() + timeout_s

    def remaining() -> float:
        return max(0.0, deadline - time.monotonic())

    if not connected.wait(timeout=remaining()):
        eprint('Error: MQTT connect timeout')
        try:
            client.loop_stop()
        except Exception:
            pass
        return 1

    if connect_failed.get('reason'):
        eprint(f'Error: {connect_failed.get("reason")}')
        try:
            client.loop_stop()
        except Exception:
            pass
        return 1

    ok = done.wait(timeout=remaining())

    for t in topics:
        if t in collected:
            print(f'{t}: {collected[t]}')

    missing = [t for t in topics if t not in collected]
    if missing:
        for t in missing:
            eprint(f'Missing: {t}')

    try:
        client.disconnect()
    except Exception:
        pass
    try:
        client.loop_stop()
    except Exception:
        pass

    return 0 if ok and not missing else 2


if __name__ == '__main__':
    raise SystemExit(main())

