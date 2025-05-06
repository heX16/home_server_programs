# WiFi AP Configuration Tool

A simple web-based utility for Raspberry Pi that allows adding and managing WiFi networks through a web interface.

## Features

- Add new WiFi networks with SSID and password
- Update passwords for existing networks
- View list of configured networks
- Scan for available WiFi networks
- Remove unwanted WiFi networks
- Automatically restart WiFi service after changes

## Requirements

- Raspberry Pi with Raspbian/Raspberry Pi OS
- Python 3
- Flask
- Apache with CGI support

## Installation

1. Clone this repository to your Raspberry Pi:

```bash
git clone https://github.com/yourusername/wifi_ap_config.git
cd wifi_ap_config
```

2. Install required dependencies:

```bash
pip3 install flask
```

3. Make the script executable:

```bash
chmod +x flask_cgi_backend.exec.py
```

4. Configure Apache to serve the CGI application:

```bash
sudo cp wifi_config.conf /etc/apache2/sites-available/wifi_config.conf
sudo a2ensite wifi_config.conf
sudo systemctl reload apache2
```

5. Make sure the application has permission to modify the WiFi configuration:

```bash
sudo chown www-data:www-data /etc/wpa_supplicant/wpa_supplicant.conf
sudo chmod 664 /etc/wpa_supplicant/wpa_supplicant.conf
```

## Example wpa_supplicant.conf

A typical wpa_supplicant.conf file has the following structure:

```
ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
update_config=1
country=RU

network={
    ssid="MyHomeWiFi"
    psk="MySecurePassword"
    key_mgmt=WPA-PSK
}

network={
    ssid="MyWorkWiFi"
    psk="AnotherPassword"
    key_mgmt=WPA-PSK
}

network={
    ssid="OpenNetwork"
    key_mgmt=NONE
}
```

The file typically contains:
- Global settings at the top (ctrl_interface, update_config, country code)
- One or more network blocks, each containing:
  - SSID: The name of the WiFi network
  - PSK: The pre-shared key (password) for the network
  - Key management settings and other optional parameters

This application manages these network entries automatically.

## Usage

1. Access the web interface by navigating to: http://your-raspberry-pi-ip/wifi

2. Enter WiFi details:
   - Enter the WiFi network name (SSID)
   - Enter the WiFi password
   - Click "Save Network"

3. The application will:
   - Add the network if it doesn't exist
   - Update the password if the network exists with a different password
   - Do nothing if the network already exists with the same password

4. API endpoints:
   - `/api/wifi` - Main endpoint for WiFi network management:
     - GET: List all configured WiFi networks
     - POST: Add or update a WiFi network (requires SSID and password in JSON body)
     - DELETE: Remove a configured WiFi network (requires SSID as query parameter)
   - GET `/api/wifi_scan` - Scan for available WiFi networks in range

## Security Considerations

This tool modifies system files and restarts system services. For security reasons:

1. Run it only on a private network
2. Consider adding authentication
3. Use HTTPS if accessed remotely

## Troubleshooting

- Check Apache error logs: `sudo tail -f /var/log/apache2/sysmon_error.log`
- Ensure the www-data user has write permissions to wpa_supplicant.conf
- Verify the location of wpa_supplicant.conf on your Raspberry Pi version
