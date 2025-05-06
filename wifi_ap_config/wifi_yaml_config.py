#!/usr/bin/env python3

import os
import yaml
import argparse
from wifi_config import WiFiManager, configure_logging

logger = configure_logging()

def configure_networks(yaml_file):
    # Load YAML config
    with open(yaml_file, 'r') as f:
        config = yaml.safe_load(f)

    if not config or 'networks' not in config:
        print(f"Error: No networks found in the YAML configuration file {yaml_file}")
        return

    wifi_manager = WiFiManager()
    config_changed = False

    for network in config['networks']:
        if not isinstance(network, dict) or not network.get('ssid') or network.get('done', False):
            continue

        ssid = network.get('ssid')
        password = network.get('password')

        result = wifi_manager.add_or_update_network(ssid, password)

        if result["success"]:
            network['done'] = True
            config_changed = True
        else:
            print(f"Error: Failed to configure WiFi network {ssid}: {result['message']}")

    if config_changed:
        # Save YAML config
        with open(yaml_file, 'w') as f:
            yaml.dump(config, f, default_flow_style=False)

def main():
    parser = argparse.ArgumentParser(description='Configure WiFi networks from YAML file')
    parser.add_argument('yaml_file', help='Path to YAML file containing WiFi networks')
    configure_networks(parser.parse_args().yaml_file)

if __name__ == "__main__":
    main()