# Copyright (c) 2014 OpenStack Foundation.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import re


def _configure():
    return ['configure terminal']


def _make_ethernet_interface(interface):
    """Ethernet port ids from LLDP look like 'Eth1/1' or 'Ethernet1/1'."""
    return re.sub("[^0-9/]", "", interface)


def _make_portchannel_interface(interface):
    interface = _make_ethernet_interface(interface)

    split = interface.split('/')

    if len(split) == 1:
        return split[0]
    else:
        return split[-1]


def _configure_interface(type, interface):
    return (
        _configure() +
        ['interface %s %s' % (type, interface)]
    )


# shared port-channel/ethernet interface configuration for trunked interfaces
def _base_trunked_configuration(hardware_id, interface, vlan_id):
    return [
        'description CUST%s-host' % hardware_id,
        'switchport mode trunk',
        'switchport trunk allowed vlan %s' % vlan_id,
        'spanning-tree port type edge trunk',
    ]


# shared port-channel/ethernet interface configuration for access interfaces
def _base_access_configuration(hardware_id, interface, vlan_id):
    return [
        'description CUST%s-host' % hardware_id,
        'switchport mode access',
        'switchport access vlan %s' % vlan_id,
        'spanning-tree port type edge',
    ]


def _default_interface(type, interface):
    return [
        'default interface %s %s' % (type, interface)
    ]


def _add_vpc(interface):
    return [
        'vpc %s' % interface,
    ]


def _add_channel_group(interface):
    return [
        'channel-group %s mode active' % interface,
    ]


def _add_ipsg():
    return [
        'ip verify source dhcp-snooping-vlan'
    ]


def _block_unicast():
    return [
        'switchport block unicast'
    ]


def _remove_ipsg():
    return [
        'no ip verify source dhcp-snooping-vlan'
    ]


def _add_lldp():
    return [
        'lldp transmit'
    ]


def _remove_lldp():
    return [
        'no lldp transmit'
    ]


def _add_cdp():
    return [
        'cdp enable'
    ]


def _remove_cdp():
    return [
        'no cdp enable'
    ]


def _add_bpduguard():
    return [
        'spanning-tree bpduguard enable'
    ]


def _bind_ip(ip, mac_address, vlan_id, interface):
    return (
        _configure() +
        [('ip source binding %s %s vlan %s '
          'interface port-channel%s' % (ip, mac_address, vlan_id, interface))]
    )


def _unbind_ip(ip, mac_address, vlan_id, interface):
    return (
        _configure() +
        [('no ip source binding %s %s vlan %s '
          'interface port-channel%s' % (ip, mac_address, vlan_id, interface))]
    )


def _delete_port_channel_interface(interface):
    return (
        # we configure it first to ensure it exists, otherwise
        # 'no interface po X' will fail and we don't want to have
        # to check beforehand.
        _configure_interface("port-channel", interface) +
        # this still works without it enabled, ensuring that
        # all the member interfaces get this setting removed.
        _remove_ipsg() +
        ['no interface port-channel %s' % (interface)]
    )


def _delete_ethernet_interface(interface):
    return (
        _configure() +
        _default_interface('ethernet', interface) +
        _configure_interface('ethernet', interface) +
        ['shutdown']
    )


def copy_running_config():
    return ['copy running-config startup-config']


def show_interface(type, interface):
    if type == 'ethernet':
        interface = _make_ethernet_interface(interface)
    elif type == 'port-channel':
        interface = _make_portchannel_interface(interface)
    return ['show interface %s %s' % (type, interface)]


def show_interface_configuration(type, interface):
    if type == 'ethernet':
        interface = _make_ethernet_interface(interface)
    elif type == 'port-channel':
        interface = _make_portchannel_interface(interface)
    return ['show running interface %s %s' % (type, interface)]


def show_dhcp_snooping_configuration(interface):
    return ['show running dhcp | egrep port-channel%s$' % (interface)]


def unbind_ip(interface, vlan_id, ip, mac_address, trunked):
    portchan_int = _make_portchannel_interface(interface)

    if trunked:
        return (
            # port-channel
            _configure_interface('port-channel', portchan_int) +
            # This will fail if no binding exists
            _unbind_ip(ip, mac_address, vlan_id, portchan_int)
        )
    else:
        return []  # TODO(morgabra) throw? This is a no-op


def create_port(hardware_id, interface, vlan_id, ip, mac_address, trunked):

    portchan_int = _make_portchannel_interface(interface)
    eth_int = _make_ethernet_interface(interface)

    conf = []
    if trunked:
        conf = (
            # create port-channel
            _configure_interface('port-channel', portchan_int) +

            # add mac/ip to the dhcp snooping table
            _bind_ip(ip, mac_address, vlan_id, portchan_int) +

            # add physical interface to port channel
            _configure_interface('ethernet', eth_int) +
            _add_channel_group(portchan_int) +

            # set physical interface options
            _add_bpduguard() +
            _remove_lldp() +
            _remove_cdp() +
            ['no shutdown'] +

            # configure port-channel
            _configure_interface('port-channel', portchan_int) +
            _base_trunked_configuration(hardware_id, portchan_int, vlan_id) +
            _add_ipsg() +
            _block_unicast() +
            ['no shutdown']
        )
    else:
        conf = (
            _configure_interface('ethernet', eth_int) +
            _base_access_configuration(hardware_id, portchan_int, vlan_id) +
            _add_bpduguard() +
            _add_lldp() +
            _add_cdp() +

            # This fixes a known bug where member interfaces of a port-channel
            # still have this enabled silently. It appears even removing it
            # from the port-channel ahead of time isn't good enough.
            _add_ipsg() +
            _remove_ipsg() +

            ['no shutdown']
        )

    return conf


def add_vlan(interface, vlan_id, ip, mac_address, trunked):
    portchan_int = _make_portchannel_interface(interface)

    if trunked:
        return (
            # add mac/ip to the dhcp snooping table
            _configure_interface('port-channel', portchan_int) +
            _bind_ip(ip, mac_address, vlan_id, portchan_int) +

            # add port-channel to vlan
            _configure_interface('port-channel', portchan_int) +
            ['switchport trunk allowed vlan add %s' % (vlan_id)]
        )
    else:
        return []  # TODO(morgabra) throw? This is a no-op


def remove_vlan(interface, vlan_id, ip, mac_address, trunked):
    portchan_int = _make_portchannel_interface(interface)

    if trunked:
        return (
            _configure_interface('port-channel', portchan_int) +
            ['switchport trunk allowed vlan remove %s' % (vlan_id)]
        )
    else:
        return []  # TODO(morgabra) throw? This is a no-op
