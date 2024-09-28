#!/usr/bin/env python3
from flask import Flask, jsonify, send_from_directory, request
from system_info import get_system_status, get_disk_info
from wsgiref.handlers import CGIHandler

app = Flask(__name__, static_folder='.')

@app.route('/')
def index():
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/api/system_status')
def system_status():
    return jsonify(get_system_status())

@app.route('/api/disk')
def disk_info():
    return jsonify(get_disk_info())

if __name__ == '__main__':
    CGIHandler().run(app)
