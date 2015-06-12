# Copyright (c) 2014 OpenStack Foundation.
# (c) Copyright 2015 Hewlett-Packard Development Company, L.P.
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

import eventlet
import mock

import unittest
import xml.etree.ElementTree as ET

from baremetal_neutron_extension.drivers import base as base_driver
from baremetal_neutron_extension.drivers.cisco import driver
from baremetal_neutron_extension.tests.unit.drivers.cisco import fixtures


class FakeNcClientResponse(object):

    def __init__(self, data):
        self._root = ET.fromstring(data)


class TestCiscoDriver(unittest.TestCase):

    _dummy_data = True

    def setUp(self):
        self.ncclient_manager = mock.Mock()
        self.ncclient = mock.Mock()
        self.ncclient_manager.connect.return_value = self.ncclient
        self.ncclient.connected = True
        mock.patch.object(driver.CiscoDriver,
                          '_import_ncclient',
                          return_value=self.ncclient_manager).start()

        self.driver = driver.CiscoDriver(save_queue_max_age=0,
                                         save_queue_get_wait=0)

    def _get_called_commands(self, pos=0):
        return self.ncclient.command.call_args_list[pos][0][0]

    def test_save(self):

        self.ncclient.command.side_effect = [
            # save commands
            FakeNcClientResponse(fixtures.ok())
        ]

        port = base_driver.PortInfo(
            switch_host='switch1.host.com',
            switch_username='user1',
            switch_password='pass',
            interface='eth1/1',
            hardware_id='hardware1',
            vlan_id=1,
            ip='10.0.0.2',
            mac_address='ff:ff:ff:ff:ff:ff',
            trunked=True)

        self.driver.save(port)
        eventlet.sleep(0)

        self.assertEqual(self.ncclient.command.call_count, 1)
        save_cmd = self._get_called_commands(0)

        save_expected = ['copy running-config startup-config']

        self.assertEqual(save_cmd, save_expected)

    def test_save_combines_same_host(self):

        self.ncclient.command.side_effect = [
            # save commands
            FakeNcClientResponse(fixtures.ok())
        ]

        self.driver = driver.CiscoDriver(save_queue_max_age=.01,
                                         save_queue_get_wait=0)

        port = base_driver.PortInfo(
            switch_host='switch1.host.com',
            switch_username='user1',
            switch_password='pass',
            interface='eth1/1',
            hardware_id='hardware1',
            vlan_id=1,
            ip='10.0.0.2',
            mac_address='ff:ff:ff:ff:ff:ff',
            trunked=True)

        self.driver.save(port)
        self.driver.save(port)
        eventlet.sleep(.02)

        self.assertEqual(self.ncclient.command.call_count, 1)
        save_cmd = self._get_called_commands(0)

        save_expected = ['copy running-config startup-config']

        self.assertEqual(save_cmd, save_expected)

    def test_save_different_hosts(self):

        self.ncclient.command.side_effect = [
            # save commands
            FakeNcClientResponse(fixtures.ok())
        ]

        self.driver = driver.CiscoDriver(save_queue_max_age=.01,
                                         save_queue_get_wait=0)

        port = base_driver.PortInfo(
            switch_host='switch1.host.com',
            switch_username='user1',
            switch_password='pass',
            interface='eth1/1',
            hardware_id='hardware1',
            vlan_id=1,
            ip='10.0.0.2',
            mac_address='ff:ff:ff:ff:ff:ff',
            trunked=True)

        port2 = base_driver.PortInfo(
            switch_host='switch2.host.com',
            switch_username='user1',
            switch_password='pass',
            interface='eth1/1',
            hardware_id='hardware1',
            vlan_id=1,
            ip='10.0.0.2',
            mac_address='ff:ff:ff:ff:ff:ff',
            trunked=True)

        self.driver.save(port)
        self.driver.save(port2)
        eventlet.sleep(.02)

        self.assertEqual(self.ncclient.command.call_count, 2)
        save_cmd = self._get_called_commands(0)
        save_cmd2 = self._get_called_commands(1)

        save_expected = ['copy running-config startup-config']

        self.assertEqual(save_cmd, save_expected)
        self.assertEqual(save_cmd2, save_expected)

    def test_save_retries(self):

        self.ncclient.command.side_effect = [
            # first save exception
            Exception("failed save"),
            # second save works
            FakeNcClientResponse(fixtures.ok())
        ]

        port = base_driver.PortInfo(
            switch_host='switch1.host.com',
            switch_username='user1',
            switch_password='pass',
            interface='eth1/1',
            hardware_id='hardware1',
            vlan_id=1,
            ip='10.0.0.2',
            mac_address='ff:ff:ff:ff:ff:ff',
            trunked=True)

        self.driver.save(port)
        eventlet.sleep(.02)

        self.assertEqual(self.ncclient.command.call_count, 2)
        save_cmd = self._get_called_commands(0)
        save_cmd2 = self._get_called_commands(1)

        save_expected = ['copy running-config startup-config']

        self.assertEqual(save_cmd, save_expected)
        self.assertEqual(save_cmd2, save_expected)

    def test_save_aborts(self):

        self.ncclient.command.side_effect = [
            Exception("failed save"),
            Exception("failed save"),
            Exception("failed save")
        ]

        port = base_driver.PortInfo(
            switch_host='switch1.host.com',
            switch_username='user1',
            switch_password='pass',
            interface='eth1/1',
            hardware_id='hardware1',
            vlan_id=1,
            ip='10.0.0.2',
            mac_address='ff:ff:ff:ff:ff:ff',
            trunked=True)

        eventlet.spawn(self.driver.save, port).wait()
        eventlet.sleep(.02)

        self.assertEqual(self.ncclient.command.call_count, 3)
        save_cmd = self._get_called_commands(0)
        save_cmd2 = self._get_called_commands(1)
        save_cmd3 = self._get_called_commands(2)

        save_expected = ['copy running-config startup-config']

        self.assertEqual(save_cmd, save_expected)
        self.assertEqual(save_cmd2, save_expected)
        self.assertEqual(save_cmd3, save_expected)

    def test_create_trunked(self):

        self.ncclient.command.side_effect = [
            # list dhcp bindings to clear
            FakeNcClientResponse(fixtures.show_dhcp(1)),
            # run dhcp binding delete commands
            FakeNcClientResponse(fixtures.ok()),
            # run clear commands
            FakeNcClientResponse(fixtures.ok()),
            # run create commands
            FakeNcClientResponse(fixtures.ok()),
            # run add vpc commands
            FakeNcClientResponse(fixtures.ok()),
            # save commands
            FakeNcClientResponse(fixtures.ok())
        ]

        port = base_driver.PortInfo(
            switch_host='switch1.host.com',
            switch_username='user1',
            switch_password='pass',
            interface='eth1/1',
            hardware_id='hardware1',
            vlan_id=1,
            ip='10.0.0.2',
            mac_address='ff:ff:ff:ff:ff:ff',
            trunked=True)

        eventlet.spawn(self.driver.create, port).wait()

        self.assertEqual(self.ncclient.command.call_count, 6)
        show_bindings_cmd = self._get_called_commands(0)
        remove_bindings_cmd = self._get_called_commands(1)
        clear_port_cmd = self._get_called_commands(2)
        create_port_cmd = self._get_called_commands(3)
        add_vpc_cmd = self._get_called_commands(4)
        save_cmd = self._get_called_commands(5)

        show_bindings_expected = ['show running dhcp | egrep port-channel1$']

        remove_bindings_expected = [
            'configure terminal',
            'interface port-channel 1',
            ('no ip source binding 10.0.0.1 FFFF.FFFF.FFFF.FFFF '
             'vlan 1 interface port-channel1')
        ]

        clear_port_expected = [
            'configure terminal',
            'interface port-channel 1',
            'no ip verify source dhcp-snooping-vlan',
            'no interface port-channel 1',
            'configure terminal',
            'default interface ethernet 1/1',
            'configure terminal',
            'interface ethernet 1/1',
            'shutdown'
        ]

        create_port_expected = [
            'configure terminal',
            'interface port-channel 1',

            'configure terminal',
            ('ip source binding 10.0.0.2 ff:ff:ff:ff:ff:ff '
             'vlan 1 interface port-channel1'),

            'configure terminal',
            'interface ethernet 1/1',
            'channel-group 1 mode active',
            'spanning-tree bpduguard enable',
            'no lldp transmit',
            'no cdp enable',
            'no shutdown',

            'configure terminal',
            'interface port-channel 1',
            'description CUSThardware1-host',
            'switchport mode trunk',
            'switchport trunk allowed vlan 1',
            'spanning-tree port type edge trunk',
            'ip verify source dhcp-snooping-vlan',
            'switchport block unicast',
            'no shutdown'
        ]

        add_vpc_expected = [
            'configure terminal',
            'interface port-channel 1',
            'vpc 1'
        ]

        save_expected = ['copy running-config startup-config']

        self.assertEqual(show_bindings_cmd, show_bindings_expected)
        self.assertEqual(remove_bindings_cmd, remove_bindings_expected)
        self.assertEqual(clear_port_cmd, clear_port_expected)
        self.assertEqual(create_port_cmd, create_port_expected)
        self.assertEqual(add_vpc_cmd, add_vpc_expected)
        self.assertEqual(save_cmd, save_expected)

    def test_create_access(self):

        self.ncclient.command.side_effect = [
            # list dhcp bindings to clear
            FakeNcClientResponse(fixtures.show_dhcp(1)),
            # run dhcp binding delete commands
            FakeNcClientResponse(fixtures.ok()),
            # run clear commands
            FakeNcClientResponse(fixtures.ok()),
            # run create commands
            FakeNcClientResponse(fixtures.ok()),
            # run save commands
            FakeNcClientResponse(fixtures.ok()),
        ]

        port = base_driver.PortInfo(
            switch_host='switch1.host.com',
            switch_username='user1',
            switch_password='pass',
            interface='eth1/1',
            hardware_id='hardware1',
            vlan_id=1,
            ip='10.0.0.2',
            mac_address='ff:ff:ff:ff:ff:ff',
            trunked=False)

        eventlet.spawn(self.driver.create, port).wait()

        self.assertEqual(self.ncclient.command.call_count, 5)
        show_bindings_cmd = self._get_called_commands(0)
        remove_bindings_cmd = self._get_called_commands(1)
        clear_port_cmd = self._get_called_commands(2)
        create_port_cmd = self._get_called_commands(3)
        save_cmd = self._get_called_commands(4)

        show_bindings_expected = ['show running dhcp | egrep port-channel1$']

        remove_bindings_expected = [
            'configure terminal',
            'interface port-channel 1',
            ('no ip source binding 10.0.0.1 FFFF.FFFF.FFFF.FFFF '
             'vlan 1 interface port-channel1'),
        ]

        clear_port_expected = [
            'configure terminal',
            'interface port-channel 1',
            'no ip verify source dhcp-snooping-vlan',
            'no interface port-channel 1',
            'configure terminal',
            'default interface ethernet 1/1',
            'configure terminal',
            'interface ethernet 1/1',
            'shutdown'
        ]

        create_port_expected = [
            'configure terminal',
            'interface ethernet 1/1',
            'description CUSThardware1-host',
            'switchport mode access',
            'switchport access vlan 1',
            'spanning-tree port type edge',
            'spanning-tree bpduguard enable',
            'lldp transmit',
            'cdp enable',
            'ip verify source dhcp-snooping-vlan',
            'no ip verify source dhcp-snooping-vlan',
            'no shutdown'
        ]

        save_expected = ['copy running-config startup-config']

        self.assertEqual(show_bindings_cmd, show_bindings_expected)
        self.assertEqual(remove_bindings_cmd, remove_bindings_expected)
        self.assertEqual(clear_port_cmd, clear_port_expected)
        self.assertEqual(create_port_cmd, create_port_expected)
        self.assertEqual(save_cmd, save_expected)

    def test_attach(self):
        self.ncclient.command.side_effect = [
            # run attach commands
            FakeNcClientResponse(fixtures.ok()),
            # save commands
            FakeNcClientResponse(fixtures.ok())
        ]

        port = base_driver.PortInfo(
            switch_host='switch1.host.com',
            switch_username='user1',
            switch_password='pass',
            interface='eth1/1',
            hardware_id='hardware1',
            vlan_id=1,
            ip='10.0.0.2',
            mac_address='ff:ff:ff:ff:ff:ff',
            trunked=True)

        eventlet.spawn(self.driver.attach, port).wait()

        self.assertEqual(self.ncclient.command.call_count, 2)
        attach_cmd = self._get_called_commands(0)
        save_cmd = self._get_called_commands(1)

        attach_expected = [
            'configure terminal',
            'interface port-channel 1',

            'configure terminal',
            ('ip source binding 10.0.0.2 ff:ff:ff:ff:ff:ff '
             'vlan 1 interface port-channel1'),

            'configure terminal',
            'interface port-channel 1',
            'switchport trunk allowed vlan add 1',
        ]

        save_expected = ['copy running-config startup-config']

        self.assertEqual(attach_cmd, attach_expected)
        self.assertEqual(save_cmd, save_expected)

    def test_detach(self):
        self.ncclient.command.side_effect = [
            # run detach commands
            FakeNcClientResponse(fixtures.ok()),
            # run remove ip binding commands
            FakeNcClientResponse(fixtures.ok()),
            # save commands
            FakeNcClientResponse(fixtures.ok())
        ]

        port = base_driver.PortInfo(
            switch_host='switch1.host.com',
            switch_username='user1',
            switch_password='pass',
            interface='eth1/1',
            hardware_id='hardware1',
            vlan_id=1,
            ip='10.0.0.2',
            mac_address='ff:ff:ff:ff:ff:ff',
            trunked=True)

        eventlet.spawn(self.driver.detach, port).wait()

        self.assertEqual(self.ncclient.command.call_count, 3)
        detach_cmd = self._get_called_commands(0)
        remove_binding_cmd = self._get_called_commands(1)
        save_cmd = self._get_called_commands(2)

        detach_expected = [
            'configure terminal',
            'interface port-channel 1',
            'switchport trunk allowed vlan remove 1'
        ]

        remove_binding_cmd = [
            'configure terminal',
            'interface port-channel 1',
            'configure terminal',
            ('no ip source binding 10.0.0.2 ff:ff:ff:ff:ff:ff '
             'vlan 1 interface port-channel1')
        ]

        save_expected = ['copy running-config startup-config']

        self.assertEqual(detach_cmd, detach_expected)
        self.assertEqual(remove_binding_cmd, remove_binding_cmd)
        self.assertEqual(save_cmd, save_expected)

    def test_delete(self):
        self.ncclient.command.side_effect = [
            # list dhcp bindings to clear
            FakeNcClientResponse(fixtures.show_dhcp(1)),
            # run remove dhcp binding commands
            FakeNcClientResponse(fixtures.ok()),
            # run clear commands
            FakeNcClientResponse(fixtures.ok()),
            # save commands
            FakeNcClientResponse(fixtures.ok())
        ]

        port = base_driver.PortInfo(
            switch_host='switch1.host.com',
            switch_username='user1',
            switch_password='pass',
            interface='eth1/1',
            hardware_id='hardware1',
            vlan_id=1,
            ip='10.0.0.2',
            mac_address='ff:ff:ff:ff:ff:ff',
            trunked=True)

        eventlet.spawn(self.driver.delete, port).wait()

        self.assertEqual(self.ncclient.command.call_count, 4)
        show_bindings_cmd = self._get_called_commands(0)
        remove_bindings_cmd = self._get_called_commands(1)
        clear_port_cmd = self._get_called_commands(2)
        save_cmd = self._get_called_commands(3)

        show_bindings_expected = ['show running dhcp | egrep port-channel1$']

        remove_bindings_expected = [
            'configure terminal',
            'interface port-channel 1',
            ('no ip source binding 10.0.0.1 FFFF.FFFF.FFFF.FFFF '
             'vlan 1 interface port-channel1')
        ]

        clear_port_expected = [
            'configure terminal',
            'interface port-channel 1',
            'no ip verify source dhcp-snooping-vlan',
            'no interface port-channel 1',
            'configure terminal',
            'default interface ethernet 1/1',
            'configure terminal',
            'interface ethernet 1/1',
            'shutdown'
        ]

        save_expected = ['copy running-config startup-config']

        self.assertEqual(show_bindings_cmd, show_bindings_expected)
        self.assertEqual(remove_bindings_cmd, remove_bindings_expected)
        self.assertEqual(clear_port_cmd, clear_port_expected)
        self.assertEqual(save_cmd, save_expected)

    def test_running_config_trunked(self):
        self.ncclient.command.side_effect = [
            FakeNcClientResponse(fixtures.show_dhcp(1)),
            FakeNcClientResponse(fixtures.show_ethernet_config_trunked(1)),
            FakeNcClientResponse(fixtures.show_port_channel_config_trunked(1))
        ]

        port = base_driver.PortInfo(
            switch_host='switch1.host.com',
            switch_username='user1',
            switch_password='pass',
            interface='eth1/1',
            hardware_id='hardware1',
            vlan_id=1,
            ip='10.0.0.2',
            mac_address='ff:ff:ff:ff:ff:ff',
            trunked=True)

        res = self.driver.running_config(port)
        expected_res = {
            'switch': {
                'interface': 'eth1/1',
                'hostname': 'switch1.host.com'
            },
            'running-config': {
                'dhcp': [
                    ('ip source binding 10.0.0.1 FFFF.FFFF.FFFF.FFFF '
                     'vlan 1 interface port-channel1')
                ],
                'port-channel': [
                    ('description '
                     'CUST39a8365c-3b84-4169-bc1a-1efa3ab20e04-host'),
                    'switchport mode trunk',
                    'switchport trunk allowed vlan 1,2',
                    'ip verify source dhcp-snooping-vlan',
                    'spanning-tree port type edge trunk',
                    'no negotiate auto',
                    'vpc 1'
                ],
                'ethernet': [
                    ('description '
                     'CUST39a8365c-3b84-4169-bc1a-1efa3ab20e04-host'),
                    'no lldp transmit',
                    'switchport mode trunk',
                    'switchport trunk allowed vlan 1,2',
                    'spanning-tree port type edge trunk',
                    'spanning-tree bpduguard enable',
                    'channel-group 1 mode active'
                ]
            }
        }
        self.assertEqual(self.ncclient.command.call_count, 3)
        self.assertEqual(res, expected_res)

    def test_running_config_access(self):
        self.ncclient.command.side_effect = [
            FakeNcClientResponse(fixtures.show_dhcp(1)),
            FakeNcClientResponse(fixtures.show_ethernet_config_trunked(1)),
            Exception('Syntax Error')
        ]

        port = base_driver.PortInfo(
            switch_host='switch1.host.com',
            switch_username='user1',
            switch_password='pass',
            interface='eth1/1',
            hardware_id='hardware1',
            vlan_id=1,
            ip='10.0.0.2',
            mac_address='ff:ff:ff:ff:ff:ff',
            trunked=True)

        res = self.driver.running_config(port)
        expected_res = {
            'switch': {
                'interface': 'eth1/1',
                'hostname': 'switch1.host.com'
            },
            'running-config': {
                'dhcp': [
                    ('ip source binding 10.0.0.1 FFFF.FFFF.FFFF.FFFF '
                     'vlan 1 interface port-channel1')
                ],
                'port-channel': ['no port-channel'],
                'ethernet': [
                    ('description '
                     'CUST39a8365c-3b84-4169-bc1a-1efa3ab20e04-host'),
                    'no lldp transmit',
                    'switchport mode trunk',
                    'switchport trunk allowed vlan 1,2',
                    'spanning-tree port type edge trunk',
                    'spanning-tree bpduguard enable',
                    'channel-group 1 mode active'
                ]
            }
        }
        self.assertEqual(self.ncclient.command.call_count, 3)
        self.assertEqual(res, expected_res)

    def test_interface_status(self):
        self.ncclient.command.side_effect = [
            FakeNcClientResponse(fixtures.show_ethernet_status(1)),
            FakeNcClientResponse(fixtures.show_port_channel_status(1))
        ]

        port = base_driver.PortInfo(
            switch_host='switch1.host.com',
            switch_username='user1',
            switch_password='pass',
            interface='eth1/1',
            hardware_id='hardware1',
            vlan_id=1,
            ip='10.0.0.2',
            mac_address='ff:ff:ff:ff:ff:ff',
            trunked=True)

        res = self.driver.interface_status(port)
        expected_res = {
            'switch': {
                'interface': 'eth1/1',
                'hostname': 'switch1.host.com'
            },
            'interface-status': {
                'ethernet': {
                    'interface': 'ethernet1/1',
                    'state': 'up'
                },
                'port-channel': {
                    'interface': 'port-channel1',
                    'state': 'up', 'vpc_status':
                    'vPC Status: Up, vPC number: 1'
                }
            }
        }
        self.assertEqual(self.ncclient.command.call_count, 2)
        self.assertEqual(res, expected_res)
