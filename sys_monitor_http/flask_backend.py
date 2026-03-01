from flask import Flask, jsonify, send_from_directory
from system_info import get_system_status, get_disk_info, get_rpi_vcgencmd_available, get_rpi_temperature, get_rpi_throttled

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


@app.route('/api/rpi/vcgencmd_available')
def rpi_vcgencmd_available():
    return jsonify(get_rpi_vcgencmd_available())


@app.route('/api/rpi/temperature')
def rpi_temperature():
    return jsonify(get_rpi_temperature())


@app.route('/api/rpi/throttled')
def rpi_throttled():
    return jsonify(get_rpi_throttled())


if __name__ == '__main__':
    app.run(debug=True)
