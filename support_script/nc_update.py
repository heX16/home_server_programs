#!/usr/bin/env python3
# coding: utf-8

import glob
import os
import sys
from pathlib import Path
import subprocess

# ЕСЛИ:
#
#     СОДЕРЖИТ:
#     ActiveState=active
#     SubState=waiting
#     StateChangeTimestamp=??? - я не уверен но кажется это время посленего изменения состояния
# ТОГДА: не запускаем сканирование и не запускаем обслуживание.

#for ff in glob.glob('*.odt'):
#    f = Path(ff).stem ...

mountname = 'media-data2tb'

# shell_lib
def str_present(target_str: str, find_substr: str) -> bool:
    return False if target_str.find(find_substr) == -1 else True

# shell_lib
def sh2(command):
    '''
    return CompletedProcess object.
    CompletedProcess contain: returncode, stdout, stderr.

    stdout_as_str_array = sh2(...).stdout.splitlines()
    '''

    return subprocess.run([command], shell=True, universal_newlines=True, stdout=subprocess.PIPE)

# shell_lib
def sh(command):
    os.system(command)





r = sh2('systemctl show {0}.automount'.format(mountname)).stdout

r1=str_present(r, 'ActiveState=active')
r2=str_present(r, 'SubState=waiting')

hdd_is_sleep = r1 and r2

print(r)
print('HDD Sleep: ', hdd_is_sleep, 'data r1 r2:', r1, r2)

if not hdd_is_sleep:
    print('can be run... WIP...')
    # sh('sudo -u www-data php -f /var/www/nextcloud/cron.php')

