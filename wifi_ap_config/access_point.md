# Raspberry Pi 4B: Simultaneous AP and Client Configuration

This guide outlines how to configure a Raspberry Pi 4B to function simultaneously as both a WiFi access point (AP) and a WiFi client (STA) on Raspberry Pi OS (Buster or newer).

## Prerequisites

- Raspberry Pi 4B with Raspberry Pi OS
- Working internet connection (initially)
- User with sudo privileges

## Installation

Install required packages:

```bash
sudo apt update
sudo apt install -y hostapd dnsmasq iw iptables-persistent
```

Stop services initially for configuration:

```bash
sudo systemctl stop hostapd
sudo systemctl stop dnsmasq
```

## Network Configuration

### 1. Configure Static IP for AP Interface

Edit dhcpcd configuration:

```bash
sudo nano /etc/dhcpcd.conf
```

Add the following at the end:

```
# Configuration for AP
interface wlan0
    static ip_address=192.168.4.1/24
    nohook wpa_supplicant
```

### 2. Configure DHCP Server (dnsmasq)

Backup original config and create new:

```bash
sudo mv /etc/dnsmasq.conf /etc/dnsmasq.conf.orig
sudo nano /etc/dnsmasq.conf
```

Add the following:

```
# AP DHCP Server Configuration
interface=wlan0
dhcp-range=192.168.4.2,192.168.4.20,255.255.255.0,24h
domain=wlan
address=/gw.wlan/192.168.4.1
address=/#/192.168.4.1

# Redirect all DNS queries to us
bogus-priv
no-resolv
no-poll

# DHCP options
# Option 114 - URL to configuration page
dhcp-option=114,http://192.168.4.1/wifi
# Option 72 - Default web server
dhcp-option=72,192.168.4.1
```

### 3. Configure Access Point (hostapd)

Create hostapd configuration:

```bash
sudo nano /etc/hostapd/hostapd.conf
```

Add the following:

```
# AP Configuration
interface=wlan0
driver=nl80211
ssid=RPi_Setup_AP
hw_mode=g
channel=7
wmm_enabled=0
macaddr_acl=0
auth_algs=1
ignore_broadcast_ssid=0
wpa=2
wpa_passphrase=raspberry
wpa_key_mgmt=WPA-PSK
wpa_pairwise=TKIP
rsn_pairwise=CCMP
country_code=US
```

Enable hostapd configuration:

```bash
sudo nano /etc/default/hostapd
```

Update to:

```
DAEMON_CONF="/etc/hostapd/hostapd.conf"
```

### 4. Configure Simultaneous AP and Client Mode

Create a script to enable both AP and client functionality:

```bash
sudo nano /usr/local/bin/ap_client_mode.sh
```

Add the following:

```bash
#!/bin/bash

# Create virtual interface for AP
sudo iw phy phy0 interface add ap0 type __ap
sudo ip link set ap0 up

# Update hostapd configuration to use ap0
sudo sed -i 's/interface=wlan0/interface=ap0/g' /etc/hostapd/hostapd.conf
sudo sed -i 's/interface=wlan0/interface=ap0/g' /etc/dnsmasq.conf

# Configure wlan0 for client mode
sudo ip link set wlan0 up

# Restart services
sudo systemctl restart hostapd
sudo systemctl restart dnsmasq

# Ensure wpa_supplicant is running for client mode
sudo wpa_supplicant -B -i wlan0 -c /etc/wpa_supplicant/wpa_supplicant.conf
```

Make the script executable:

```bash
sudo chmod +x /usr/local/bin/ap_client_mode.sh
```

### 5. Configure Network Routing and Masquerading

Enable IPv4 forwarding:

```bash
sudo nano /etc/sysctl.conf
```

Uncomment:

```
net.ipv4.ip_forward=1
```

Apply the change:

```bash
sudo sysctl -p
```

Add iptables rules:

```bash
sudo nano /usr/local/bin/iptables_setup.sh
```

Add the following:

```bash
#!/bin/bash

# Clear existing rules
iptables -F
iptables -t nat -F

# Enable NAT
iptables -t nat -A POSTROUTING -o wlan0 -j MASQUERADE

# Allow established connections
iptables -A FORWARD -i wlan0 -o ap0 -m state --state RELATED,ESTABLISHED -j ACCEPT
iptables -A FORWARD -i ap0 -o wlan0 -j ACCEPT

# Redirect HTTP traffic to our server
iptables -t nat -A PREROUTING -i ap0 -p tcp --dport 80 -j DNAT --to-destination 192.168.4.1:80
iptables -t nat -A PREROUTING -i ap0 -p tcp --dport 443 -j DNAT --to-destination 192.168.4.1:443

# Save rules
iptables-save > /etc/iptables/rules.v4
```

Make executable:

```bash
sudo chmod +x /usr/local/bin/iptables_setup.sh
```

### 6. Autostart Configuration

Create a service to start the dual mode:

```bash
sudo nano /etc/systemd/system/ap-client-mode.service
```

Add:

```
[Unit]
Description=AP and Client Mode Service
After=network.target

[Service]
Type=oneshot
ExecStart=/usr/local/bin/ap_client_mode.sh
ExecStartPost=/usr/local/bin/iptables_setup.sh
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
```

Enable the service:

```bash
sudo systemctl enable ap-client-mode.service
```

## Configuring WiFi Client Connection

Use wpa_supplicant to manage the client connection:

```bash
sudo nano /etc/wpa_supplicant/wpa_supplicant.conf
```

Example configuration:

```
ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
update_config=1
country=US

network={
    ssid="HomeNetwork"
    psk="password"
    key_mgmt=WPA-PSK
}
```

## Important Notes

1. **Channel Matching**: Both AP and client must use the same channel. If your client connects to a router on channel 6, update hostapd.conf to use channel=6.

2. **Performance Considerations**: Running both AP and client on a single radio will reduce bandwidth since they share the same channel and radio.

3. **Web Server**: Configure your Flask application to serve on port 80 to provide the WiFi configuration interface.

4. **Debugging**:
   - Check AP status: `sudo systemctl status hostapd`
   - Check DHCP status: `sudo systemctl status dnsmasq`
   - View logs: `sudo journalctl -xe`

## Integrating with Your WiFi Configuration Tool

Your existing Flask application should:

1. Listen on all interfaces (0.0.0.0) on port 80
2. Provide the interface for adding/modifying WiFi networks
3. Include functionality to update wpa_supplicant.conf
4. Restart the networking service after changes