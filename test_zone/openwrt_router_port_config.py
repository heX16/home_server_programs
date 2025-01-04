
# Luci RPC APIs:
# https://htmlpreview.github.io/?https://raw.githubusercontent.com/openwrt/luci/master/docs/api/index.html

# https://openwrt-luci-rpc.readthedocs.io/en/latest/
# https://github.com/fbradyirl/openwrt-luci-rpc
# https://readthedocs.org/projects/openwrt-luci-rpc/downloads/pdf/stable/

'''
on OpenWrt router:
opkg update
opkg install luci-mod-rpc
'''

from openwrt_luci_rpc import OpenWrtRpc
from pprint import pprint

router = OpenWrtRpc('192.168.1.1', 'root', 'mypassword')
result = router.get_all_connected_devices(only_reachable=True)

for device in result:
   mac = device.mac
   name = device.hostname

   # convert class to a dict
   device_dict = device._asdict()

pprint(device_dict)

# OLD:
'''
# https://github.com/jumpscale7/openwrt-remote-manager
# Note: This module requires that the package luci-mod-rpc is installed on all your managed OpenWRT installations
import openwrt # pip install openwrt-remote-manager

manager = openwrt.create_manager(hostname='192.168.1.19', username='root', password='____')

port_forwarding_rules = manager.port_forwarding.all
for rule in port_forwarding_rules:
    print(rule)

'''
