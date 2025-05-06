#!/usr/bin/env python3

import os
import logging
import sys
from typing import Optional, Tuple
from wifi_config import WiFiManager, configure_logging

# Configure logging
logger = configure_logging()

WIFI_CONFIG_FILE = "/boot/wifi.txt"

def read_wifi_credentials() -> Optional[Tuple[str, str]]:
    """
    Read SSID and password from /boot/wifi.txt
    Returns a tuple of (ssid, password) if file exists and has two lines,
    otherwise returns None
    """
    if not os.path.exists(WIFI_CONFIG_FILE):
        logger.info(f"WiFi config file {WIFI_CONFIG_FILE} not found")
        return None

    try:
        with open(WIFI_CONFIG_FILE, 'r') as f:
            lines = [line.strip() for line in f.readlines() if line.strip()]

        if len(lines) >= 2:
            ssid = lines[0]
            password = lines[1]
            logger.info(f"Found WiFi credentials for SSID: {ssid}")
            return (ssid, password)
        else:
            logger.warning(f"WiFi config file doesn't contain enough lines (found {len(lines)}, need at least 2)")
            return None
    except Exception as e:
        logger.error(f"Error reading WiFi config file: {str(e)}")
        return None

def main():
    """
    Main function that reads WiFi credentials from /boot/wifi.txt
    and applies them using WiFiManager
    """
    logger.info("Starting boot WiFi setup script")

    # Read WiFi credentials
    credentials = read_wifi_credentials()
    if not credentials:
        logger.info("No valid WiFi credentials found. Exiting.")
        return

    ssid, password = credentials

    # Configure WiFi
    try:
        wifi_manager = WiFiManager()
        result = wifi_manager.add_or_update_network(ssid, password)

        if result["success"]:
            logger.info(f"Successfully configured WiFi network: {ssid}")

            # Remove the credentials file after successful configuration
            try:
                os.remove(WIFI_CONFIG_FILE)
                logger.info(f"Removed {WIFI_CONFIG_FILE} after successful configuration")
            except Exception as e:
                logger.error(f"Error removing {WIFI_CONFIG_FILE}: {str(e)}")
        else:
            logger.error(f"Failed to configure WiFi: {result['message']}")

    except Exception as e:
        logger.error(f"Error configuring WiFi: {str(e)}")

if __name__ == "__main__":
    main()