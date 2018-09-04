#!/bin/bash

apt install python3-pip
pip3 install --upgrade setuptools
python3 -m pip install --upgrade pip

# транслитерация
pip3 install transliterate
# YAML
pip3 install pyyaml
# MQTT
pip3 install paho-mqtt
# формат ODS - LibreOffice
pip3 install pyexcel
pip3 install pyexcel-ods
# параметры коммандной строки http://docopt.org/
pip3 install docopt
# уведомления об изменении файлов
pip3 install watchdog
