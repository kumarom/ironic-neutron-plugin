# Copyright 2013 OpenStack Foundation
# All rights reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.


def _configure():
    return ['configure terminal']


def _configure_interface(type, interface):
    return (
        _configure() +
        ['interface %s %s' % (type, interface)]
    )


# shared port-channel/ethernet interface configuration for trunked interfaces
def _base_trunked_configuration(device_id, interface, vlan_id):
    return [
        'description CUST%s-host' % device_id,
        'switchport mode trunk',
        'switchport trunk allowed vlan %s' % vlan_id,
        'spanning-tree port type edge trunk',
        'no shutdown'
    ]


# shared port-channel/ethernet interface configuration for access interfaces
def _base_access_configuration(device_id, interface, vlan_id):
    return [
        'description CUST%s-host' % device_id,
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
        _configure() +
        ['no interface port-channel %s' % (interface)]
    )


def _delete_ethernet_interface(interface, trunked, vlan_id=None):
    cmd = None
    if trunked:
        cmd = _delete_trunked_configuration()
    else:
        cmd = _delete_access_configuration(vlan_id)

    return (
        _configure_interface('ethernet', '1/%s' % (interface)) +
        cmd
    )


def show_interface_configuration(type, interface):
    return ['show running interface %s %s' % (type, interface)]


def create_port(device_id, interface, vlan_id, ip, mac_address, trunked):

    conf = []
    if trunked:
        conf = (
            # port-channel
            _configure_interface('port-channel', interface) +
            _base_trunked_configuration(device_id, interface, vlan_id) +
            _add_vpc(interface) +

            # IPSG
            _bind_ip(ip, mac_address, vlan_id, interface) +

            # ethernet
            _configure_interface('ethernet', '1/%s' % (interface)) +
            _base_trunked_configuration(device_id, interface, vlan_id) +
            _add_channel_group(interface)
        )
    else:
        conf = (
            _configure_interface('ethernet', '1/%s' % (interface)) +
            _base_access_configuration(device_id, interface, vlan_id)
        )

    return conf


def delete_port(interface, trunked, vlan_id=None):

    return (
        # TODO(morgabra) this will leave orphaned ip bindings if trunked!
        # Make sure you remove all vlans before deleting a port
        _delete_port_channel_interface(interface) +
        _delete_ethernet_interface(interface, trunked, vlan_id=vlan_id)
    )


def add_vlan(interface, vlan_id, ip, mac_address, trunked):
        if trunked:
            return (
                # port-channel
                _configure_interface('port-channel', interface) +
                ['switchport trunk allowed vlan add %s' % (vlan_id)] +

                # IPSG
                _bind_ip(ip, mac_address, vlan_id, interface)
            )
        else:
            return []  # TODO(morgabra) throw? This is a no-op


def remove_vlan(interface, vlan_id, ip, mac_address, trunked):
    if trunked:
        return (
            # port-channel
            _configure_interface('port-channel', interface) +
            ['switchport trunk allowed vlan remove %s' % (vlan_id)] +

            # IPSG
            _unbind_ip(ip, mac_address, vlan_id, interface)
        )
    else:
        return []  # TODO(morgabra) throw? This is a no-op
