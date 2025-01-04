#!/usr/bin/python
import sys
import logging
logging.basicConfig(level=logging.INFO)

instance = sys.argv[1]

# The connected socket is duplicated to stdin/stdout
data = sys.stdin.readline().strip()
logging.info('soc-test-service: at instance %s, got request: %s', instance, data)
sys.stdout.write(data.upper() + '\r\n')
