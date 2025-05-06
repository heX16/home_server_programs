#!/usr/bin/env python3

import subprocess
import time
import logging
from typing import List, Dict, Optional, Any

# Configure logging
def configure_logging(level=logging.INFO) -> logging.Logger:
    """Configure logging for the wifi_config module"""
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    return logging.getLogger(__name__)

logger = configure_logging()

class WiFiManager:
    """Manages WiFi network configurations using wpa_cli commands"""

    def __init__(self, interface: str = 'wlan0'):
        self.interface = interface

    def _run_wpa_cli(self, *args) -> str:
        """Run wpa_cli with given arguments and return output"""
        cmd = ['wpa_cli', '-i', self.interface] + list(args)
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            error_msg = f"Error running wpa_cli command: {e}"
            logger.error(error_msg)
            raise Exception(error_msg)

    def get_networks(self) -> List[Dict[str, str]]:
        """Get list of configured networks"""
        try:
            output = self._run_wpa_cli('list_networks')

            networks = []
            lines = output.split('\n')[1:]  # Skip header line

            for line in lines:
                if not line.strip():
                    continue

                parts = line.split('\t')
                if len(parts) >= 3:
                    network_id = parts[0]
                    ssid = parts[1]

                    networks.append({
                        'network_id': network_id,
                        'ssid': ssid
                    })

            return networks
        except Exception as e:
            logger.error(f"Failed to get networks: {str(e)}")
            return []

    def network_exists(self, ssid: str) -> bool:
        """Check if network with given SSID exists"""
        networks = self.get_networks()
        return any(network.get('ssid') == ssid for network in networks)

    def add_or_update_network(self, ssid: str, password: str) -> Dict[str, Any]:
        """Add a new network or update existing one using wpa_cli"""
        try:
            # Check if network exists
            networks = self.get_networks()
            network_id = None

            for network in networks:
                if network.get('ssid') == ssid:
                    network_id = network.get('network_id')
                    break

            # If network doesn't exist, add it
            if network_id is None:
                network_id = self._run_wpa_cli('add_network')
                logger.info(f"Added new network with ID {network_id}")
                message = "Network added"
            else:
                logger.info(f"Updating existing network with ID {network_id}")
                message = "Network updated"

            # Configure the network
            self._run_wpa_cli('set_network', network_id, 'ssid', f'"{ssid}"')
            self._run_wpa_cli('set_network', network_id, 'psk', f'"{password}"')

            # Enable the network
            self._run_wpa_cli('enable_network', network_id)

            # Save the configuration
            self._run_wpa_cli('save_config')

            return {"success": True, "message": message, "changed": True}
        except Exception as e:
            logger.exception(f"Error in add_or_update_network: {str(e)}")
            return {"success": False, "message": f"Error: {str(e)}", "changed": False}

    def remove_network(self, ssid: str) -> Dict[str, Any]:
        """Remove a network configuration by SSID using wpa_cli"""
        try:
            # Find network ID by SSID
            networks = self.get_networks()
            network_id = None

            for network in networks:
                if network.get('ssid') == ssid:
                    network_id = network.get('network_id')
                    break

            if network_id is None:
                logger.info(f"Network {ssid} does not exist, cannot remove")
                return {"success": False, "message": "Network does not exist", "changed": False}

            # Remove the network
            self._run_wpa_cli('remove_network', network_id)

            # Save the configuration
            self._run_wpa_cli('save_config')

            return {"success": True, "message": "Network removed", "changed": True}
        except Exception as e:
            logger.exception(f"Error in remove_network: {str(e)}")
            return {"success": False, "message": f"Error: {str(e)}", "changed": False}

    def scan_networks(self) -> List[Dict[str, str]]:
        """Scan for available WiFi networks"""
        try:
            # Trigger scan
            self._run_wpa_cli('scan')

            # Wait for scan results
            time.sleep(2)

            # Get scan results
            output = self._run_wpa_cli('scan_results')

            networks = []
            lines = output.split('\n')[1:]  # Skip header line

            for line in lines:
                if not line.strip():
                    continue

                parts = line.split('\t')
                if len(parts) >= 5:
                    bssid = parts[0]
                    signal = parts[1]
                    frequency = parts[2]
                    flags = parts[3]
                    ssid = parts[4]

                    networks.append({
                        'bssid': bssid,
                        'signal': signal,
                        'frequency': frequency,
                        'flags': flags,
                        'ssid': ssid
                    })

            return networks
        except Exception as e:
            logger.error(f"Failed to scan networks: {str(e)}")
            return []
