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
        'no shutdown'
    ]


# shared port-channel/ethernet interface configuration for access interfaces
def _base_access_configuration(hardware_id, interface, vlan_id):
    return [
        'description CUST%s-host' % hardware_id,
        'switchport mode access',
        'switchport access vlan %s' % vlan_id,
        'spanning-tree port type edge',
        'no shutdown'
    ]


# TODO(morgabra) Ideally a switch would support 'default interface eth 1/X'
# or something similar, but for some reason the 3172s do not for physical
# interfaces so you have to manually unset everything.
def _delete_access_configuration(vlan_id):
    return [
        'no description',
        'no switchport mode access',
        'no switchport access vlan %s' % (vlan_id),
        'no spanning-tree port type edge',
        'shutdown'
    ]


def _delete_trunked_configuration():
    return [
        'no description',
        'no switchport mode trunk',
        'no switchport trunk allowed vlan all',
        'no spanning-tree port type edge trunk',
        'shutdown'
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
        _configure_interface("port-channel", interface) +
        ['no interface port-channel %s' % (interface)]
    )


def _delete_ethernet_interface(interface, trunked, vlan_id=None):
    cmd = None
    if trunked:
        cmd = _delete_trunked_configuration()
    else:
        cmd = _delete_access_configuration(vlan_id)

    return (
        _configure_interface('ethernet', interface) +
        cmd
    )


def show_interface_configuration(type, interface):
    return ['show running interface %s %s' % (type, interface)]


def show_dhcp_snooping_configuration(interface):
    return ['show running dhcp | i port-channel%s' % (interface)]

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
            # port-channel
            _configure_interface('port-channel', portchan_int) +
            _base_trunked_configuration(hardware_id, portchan_int, vlan_id) +
            _add_vpc(portchan_int) +
            _add_ipsg() +

            # add mac/ip to the dhcp snooping table
            _bind_ip(ip, mac_address, vlan_id, portchan_int) +

            # ethernet
            _configure_interface('ethernet', eth_int) +
            _base_trunked_configuration(hardware_id, eth_int, vlan_id) +
            _add_channel_group(portchan_int) +
            # TODO(morgabra) We're assuming an access port allows LLDP
            # and a trunked port does not. This is not a correct assumption
            # in the general case.
            # It seems overkill to include LLDP as a flag on the network
            # object or something but I can't think of a better way.
            _remove_lldp()
        )
    else:
        conf = (
            _configure_interface('ethernet', eth_int) +
            _base_access_configuration(hardware_id, portchan_int, vlan_id) +
            _add_lldp() +
            # If this interface belonged to a portchannel that has IPSG
            # enabled and you drop the portchannel, the IPSG still sticks.
            _add_ipsg() +
            _remove_ipsg()
        )

    return conf


def delete_port(interface, trunked, vlan_id=None):

    portchan_int = _make_portchannel_interface(interface)
    eth_int = _make_ethernet_interface(interface)

    return (
        # TODO(morgabra) this will leave orphaned ip bindings if trunked!
        # Make sure you remove all vlans before deleting a port
        _delete_port_channel_interface(portchan_int) +
        _delete_ethernet_interface(eth_int, trunked, vlan_id=vlan_id)
    )


def add_vlan(interface, vlan_id, ip, mac_address, trunked):
    portchan_int = _make_portchannel_interface(interface)

    if trunked:
        return (
            # port-channel
            _configure_interface('port-channel', portchan_int) +
            ['switchport trunk allowed vlan add %s' % (vlan_id)] +

            # add mac/ip to the dhcp snooping table
            _bind_ip(ip, mac_address, vlan_id, portchan_int)
        )
    else:
        return []  # TODO(morgabra) throw? This is a no-op


def remove_vlan(interface, vlan_id, ip, mac_address, trunked):
    portchan_int = _make_portchannel_interface(interface)

    if trunked:
        return (
            # port-channel
            _configure_interface('port-channel', portchan_int) +
            ['switchport trunk allowed vlan remove %s' % (vlan_id)]
        )
    else:
        return []  # TODO(morgabra) throw? This is a no-op
