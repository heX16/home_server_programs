# WiFi YAML Configuration Tool

This tool configures multiple WiFi networks from a YAML configuration file.

## Requirements

- Python 3.6+
- PyYAML (`pip install pyyaml`)
- WiFi interface with wpa_cli support (usually Raspberry Pi or Linux systems)

## Installation

1. Make sure the script is executable:
   ```bash
   chmod +x wifi_yaml_config.py
   ```

2. Install required dependencies:
   ```bash
   pip install pyyaml
   ```

## Usage

1. Create a YAML configuration file with your WiFi networks (see example below)
2. Run the script with the path to your YAML file:
   ```bash
   sudo python3 wifi_yaml_config.py /path/to/your/wifi_networks.yaml
   ```

## YAML File Format

The YAML file should have the following structure:

```yaml
networks:
  - ssid: YourWiFiName
    password: YourWiFiPassword
    # No 'done' flag means this network will be configured

  - ssid: AnotherWiFi
    password: AnotherPassword
    done: true  # This network is already configured and will be skipped
```

## How It Works

1. The script loads the WiFi networks from the specified YAML file
2. For each network without a `done: true` flag, it configures the network using wpa_cli
3. After successfully configuring a network, it marks it as `done: true` in the YAML file
4. The updated YAML file is saved, preserving the configuration status

## Troubleshooting

- Make sure to run the script with sudo/root privileges
- Check logs for specific error messages
- Verify your WiFi interface name (default is 'wlan0')
- Ensure wpa_cli is installed and configured correctly on your system