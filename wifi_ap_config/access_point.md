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

### 1. Create Virtual Interface with udev Rules

Instead of manually creating virtual interfaces each time, use udev rules to automate this:

```bash
# Get MAC address
MAC_ADDRESS="$(cat /sys/class/net/wlan0/address)"

# Create udev rule
sudo bash -c "cat > /etc/udev/rules.d/70-persistent-net.rules" << EOF
SUBSYSTEM=="ieee80211", ACTION=="add|change", ATTR{macaddress}=="${MAC_ADDRESS}", KERNEL=="phy0", \\
  RUN+="/sbin/iw phy phy0 interface add ap0 type __ap", \\
  RUN+="/bin/ip link set ap0 address ${MAC_ADDRESS}"
EOF
```

### 2. Configure Static IP for AP Interface

Edit dhcpcd configuration:

```bash
sudo nano /etc/dhcpcd.conf
```

Add the following at the end:

```
# Configuration for AP
interface ap0
    static ip_address=192.168.4.1/24
    nohook wpa_supplicant
```

### 3. Configure DHCP Server (dnsmasq)

Backup original config and create new:

```bash
sudo mv /etc/dnsmasq.conf /etc/dnsmasq.conf.orig
sudo nano /etc/dnsmasq.conf
```

Add the following:

```
# AP DHCP Server Configuration
interface=ap0
no-dhcp-interface=lo,wlan0
bind-interfaces
dhcp-range=192.168.4.2,192.168.4.20,255.255.255.0,12h
domain=wlan
address=/gw.wlan/192.168.4.1
address=/#/192.168.4.1

# Redirect all DNS queries to us
bogus-priv
no-resolv
no-poll
server=8.8.8.8

# DHCP options
# Option 114 - URL to configuration page
dhcp-option=114,http://192.168.4.1/wifi
# Option 72 - Default web server
dhcp-option=72,192.168.4.1
```

### 4. Configure Access Point (hostapd)

Create hostapd configuration:

```bash
sudo nano /etc/hostapd/hostapd.conf
```

Add the following:

```
# AP Configuration
ctrl_interface=/var/run/hostapd
ctrl_interface_group=0
interface=ap0
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
wpa_pairwise=TKIP CCMP
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

### 5. Configuring WiFi Client Connection

Use wpa_supplicant to manage the client connection with support for hidden networks:

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
    scan_ssid=1
    id_str="AP1"
    priority=100
}
```

The `scan_ssid=1` parameter enables connection to hidden networks.

### 6. Configure Network Routing and Masquerading

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

### 7. Create Startup Script

Create a script to handle proper startup sequence:

```bash
sudo nano /usr/local/bin/ap_client_mode.sh
```

Add the following:

```bash
#!/bin/bash

echo 'Starting Wifi AP and client...'
# Wait for network interfaces to be ready
sleep 30

# Force restart interfaces in correct order
sudo ifdown --force wlan0
sudo ifdown --force ap0
sudo ifup ap0
sudo ifup wlan0

# Ensure wpa_supplicant is running for client mode
sudo wpa_supplicant -B -i wlan0 -c /etc/wpa_supplicant/wpa_supplicant.conf

# Enable IP forwarding
sudo sysctl -w net.ipv4.ip_forward=1

# Configure NAT
sudo iptables -t nat -A POSTROUTING -s 192.168.4.0/24 ! -d 192.168.4.0/24 -j MASQUERADE

# Allow established connections
sudo iptables -A FORWARD -i wlan0 -o ap0 -m state --state RELATED,ESTABLISHED -j ACCEPT
sudo iptables -A FORWARD -i ap0 -o wlan0 -j ACCEPT

# Redirect HTTP traffic to our server
sudo iptables -t nat -A PREROUTING -i ap0 -p tcp --dport 80 -j DNAT --to-destination 192.168.4.1:80
sudo iptables -t nat -A PREROUTING -i ap0 -p tcp --dport 443 -j DNAT --to-destination 192.168.4.1:443

# Save iptables rules
sudo iptables-save > /etc/iptables/rules.v4

# Restart DHCP service
sudo systemctl restart dnsmasq
```

Make the script executable:

```bash
sudo chmod +x /usr/local/bin/ap_client_mode.sh
```

### 8. Autostart Configuration

You can choose between two methods to autostart the configuration:

#### Option A: Using systemd (more modern)

Create a service:

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
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
```

Enable the service:

```bash
sudo systemctl enable ap-client-mode.service
```

#### Option B: Using cron (simpler)

Add a cron job to run the script at boot:

```bash
crontab -e
```

Add this line:

```
@reboot /usr/local/bin/ap_client_mode.sh
```

## Network Configuration Options

You can choose between two approaches for network configuration:

### Option A: Using dhcpcd (for newer Raspberry Pi OS)

As already described in the "Configure Static IP" section above.

### Option B: Using /etc/network/interfaces (for older Raspberry Pi OS)

If you prefer the traditional network interfaces approach:

```bash
sudo nano /etc/network/interfaces
```

Replace with:

```
source-directory /etc/network/interfaces.d

auto lo
auto ap0
auto wlan0
iface lo inet loopback

allow-hotplug ap0
iface ap0 inet static
    address 192.168.4.1
    netmask 255.255.255.0
    hostapd /etc/hostapd/hostapd.conf

allow-hotplug wlan0
iface wlan0 inet manual
    wpa-roam /etc/wpa_supplicant/wpa_supplicant.conf
iface AP1 inet dhcp
```

## Important Notes

1. **Channel Matching**: Both AP and client must use the same channel. If your client connects to a router on channel 6, update hostapd.conf to use channel=6.

2. **Performance Considerations**: Running both AP and client on a single radio will reduce bandwidth since they share the same channel and radio.

3. **Web Server**: Configure your Flask application to serve on port 80 to provide the WiFi configuration interface.

4. **Debugging**:
   - Check AP status: `sudo systemctl status hostapd`
   - Check DHCP status: `sudo systemctl status dnsmasq`
   - View logs: `sudo journalctl -xe`
   - Check interface status: `ip a`
   - Test connectivity: `ping -I wlan0 8.8.8.8`

## Integrating with Your WiFi Configuration Tool

Your existing Flask application should:

1. Listen on all interfaces (0.0.0.0) on port 80
2. Provide the interface for adding/modifying WiFi networks
3. Include functionality to update wpa_supplicant.conf
4. Restart the networking service after changes

## Script-Based Installation

For a more automated installation, you could create a script that:

1. Takes parameters for SSID and password for both AP and client
2. Handles error checking
3. Performs all the configuration steps automatically

This would be useful for deploying multiple devices or for users less familiar with Linux commands.