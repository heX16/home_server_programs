#!/usr/bin/env python3
# coding: utf-8

from pathlib import Path
import os
import stat

# shell_lib
def sh(command):
    os.system(command)

# shell_lib
def get_perm(p: Path)->str:
    # TODO: WARN: Linux only
    return oct(p.stat().st_mode)[2:]

# shell_lib
def perm_only_base(perm: str)->str:
    return perm[-3:]

p = Path.cwd()
o_g = '{o}:{g}'.format(o=p.owner(), g=p.group())
print('Path:', str(p))
print('Owner and Group:', o_g)

perm = perm_only_base(get_perm(p))
print('Permissions:', perm)

sh('chown -R {0} *'.format(o_g))
# sh('chmod -R {0} *'.format(perm)) - WIP!!!
