#!/usr/bin/env python3

from flask import Flask, jsonify, send_from_directory, request
from wifi_config import WiFiManager
from wsgiref.handlers import CGIHandler

app = Flask(__name__, static_folder='static')

# Serve the index.html file when accessing the root
@app.route('/')
def index():
    return send_from_directory(app.static_folder, 'index.html')

# Serve static files like *.js
@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory(app.static_folder, filename)

# API endpoint for WiFi configuration
@app.route('/api/wifi', methods=['GET', 'POST'])
def wifi_config():
    wifi_manager = WiFiManager()

    if request.method == 'POST':
        data = request.get_json()
        ssid = data.get('ssid')
        password = data.get('password')

        if not ssid or not password:
            return jsonify({'success': False, 'message': 'SSID and password are required'}), 400

        result = wifi_manager.add_or_update_network(ssid, password)
        return jsonify(result)

    # GET method returns list of configured networks
    networks = wifi_manager.get_networks()
    return jsonify({'networks': networks})


if __name__ == '__main__':
    CGIHandler().run(app)
