import glob, os, sys
from pathlib import Path
from subprocess import *

services = [
'home-autodisable',
'home-extbus-uart',
'home-extbus-udp',
'home-lamp-scen',
'home-motion-detector',
'home-remap',
'home-watcher',
'syncthing',
]

#for ff in glob.glob('*.odt'):
#    f = Path(ff).stem ...

for s in services:
  r = call("systemctl is-active --quiet {0}".format(s), shell=True)
  if r==0:
    print(s+': ok')
  elif r==3:
    print(s+': off')
  elif r==4:
    print(s+': NONE')
  else:
    print(s+': DEAD')



