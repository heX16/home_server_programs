#!/bin/bash

update-alternatives --install /usr/bin/python python /usr/bin/python3 1

apt install python3-pip
pip3 install --upgrade setuptools
python3 -m pip install --upgrade pip

sudo pip install OrangePi.GPIO

# транслитерация
pip3 install transliterate
# YAML
pip3 install pyyaml
# MQTT
pip3 install paho-mqtt
# MQTT async
pip3 install aiomqtt
# формат ODS - LibreOffice
pip3 install pyexcel
pip3 install pyexcel-ods
# параметры коммандной строки http://docopt.org/
pip3 install docopt
# уведомления об изменении файлов
# https://github.com/gorakhargosh/watchdog
pip3 install watchdog
# https://github.com/paul-nameless/pyfswatch
# https://github.com/emcrisostomo/fswatch
pip3 install fswatch

# управление роутером openwrt (в роутер нужно установить luci-mod-rpc)
#pip3 install openwrt-remote-manager - пакет устарел

