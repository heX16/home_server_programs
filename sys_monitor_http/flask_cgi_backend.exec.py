#!/usr/bin/env python3

from wsgiref.handlers import CGIHandler
from flask_app import app

if __name__ == '__main__':
    CGIHandler().run(app)
