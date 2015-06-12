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

from baremetal_neutron_extension.tests import base


class TestIronicDriverManager(base.IronicMl2MechanismTestCase):
    """End to end tests that ensure that hardware drivers are called
    with the correct data and the hardware driver manager functions
    correctly.
    """

    _dummy_data = True

    def _assert_switchinfo_equals(self, manager_port, switch, switchport):
        self.assertEqual(
            manager_port.switch_host, switch['host'])
        self.assertEqual(
            manager_port.switch_username, switch['username'])
        # the API response does not include the password
        self.assertEqual(
            manager_port.switch_password, 'bar')
        self.assertEqual(
            manager_port.interface, switchport['port'])

    def _assert_netinfo_equals(self, manager_port, port, network):
        self.assertEqual(
            manager_port.hardware_id, port['switch:hardware_id'])
        self.assertEqual(
            manager_port.ip, port['fixed_ips'][0]['ip_address'])
        self.assertEqual(
            manager_port.mac_address, port['mac_address'])
        self.assertEqual(
            manager_port.trunked, port['trunked'])
        self.assertEqual(
            manager_port.vlan_id, network['provider:segmentation_id'])

    def _get_switch_info_from_manager_port(self, manager_port,
                                           switches, switchports):
        switch_host = manager_port.switch_host
        switch = None
        for s in switches:
            if switch_host == s['switch']['host']:
                switch = s
                break
        self.assertNotEqual(switch, None)

        switch_id = switch['switch']['id']
        switchport = None
        for s in switchports:
            if switch_id == s['switch_id']:
                switchport = s
                break
        self.assertNotEqual(switchport, None)

        return switch, switchport

    def test_create(self):
        switchports = self._make_switchports(
            self.fmt, [self.switch1, self.switch2],
            self.hardware_id, ['eth1/1', 'eth1/1'], ['eth0', 'eth1']
        )
        port = self._make_port_with_switchports(
            network=self.net1['network']['id'],
            switchports=switchports,
            commit=True)

        # assert that switch hardware driver was called for each switchport
        self.assertHWDriverNotCalled(exclude='create')
        self.assertEqual(self.hw_driver.create.call_count, 2)

        mport1 = self.hw_driver.create.call_args_list[0][0][0]
        mport2 = self.hw_driver.create.call_args_list[1][0][0]

        for manager_port in [mport1, mport2]:
            switch, switchport = self._get_switch_info_from_manager_port(
                manager_port, [self.switch1, self.switch2],
                switchports['switchports']
            )

            self._assert_switchinfo_equals(
                manager_port, switch['switch'], switchport)
            self._assert_netinfo_equals(
                manager_port, port['port'], self.net1['network'])

    def test_attach(self):
        switchports = self._make_switchports(
            self.fmt, [self.switch1, self.switch2],
            self.hardware_id, ['eth1/1', 'eth1/1'], ['eth0', 'eth1']
        )
        self._make_port_with_switchports(
            network=self.net1['network']['id'],
            switchports=switchports,
            commit=True,
            trunked=True)

        # assert that switch hardware driver was called for each switchport
        self.assertHWDriverNotCalled(exclude='create')
        self.assertEqual(self.hw_driver.create.call_count, 2)

        port = self._make_port_with_switchports(
            network=self.net2['network']['id'],
            switchports=switchports,
            commit=True,
            trunked=True)

        # assert that switch hardware driver was called for each switchport
        self.assertHWDriverNotCalled(exclude=['create', 'attach'])
        self.assertEqual(self.hw_driver.attach.call_count, 2)
        self.assertEqual(self.hw_driver.create.call_count, 2)

        mport1 = self.hw_driver.attach.call_args_list[0][0][0]
        mport2 = self.hw_driver.attach.call_args_list[1][0][0]

        for manager_port in [mport1, mport2]:
            switch, switchport = self._get_switch_info_from_manager_port(
                manager_port, [self.switch1, self.switch2],
                switchports['switchports']
            )

            self._assert_switchinfo_equals(
                manager_port, switch['switch'], switchport)
            self._assert_netinfo_equals(
                manager_port, port['port'], self.net2['network'])

    def test_delete(self):
        switchports = self._make_switchports(
            self.fmt, [self.switch1, self.switch2],
            self.hardware_id, ['eth1/1', 'eth1/1'], ['eth0', 'eth1']
        )
        port = self._make_port_with_switchports(
            network=self.net1['network']['id'],
            switchports=switchports,
            commit=True,
            trunked=False)

        # assert that switch hardware driver was called for each switchport
        self.assertHWDriverNotCalled(exclude='create')
        self.assertEqual(self.hw_driver.create.call_count, 2)

        self._delete('ports', port['port']['id'])

        self.assertHWDriverNotCalled(exclude=['create', 'delete'])
        self.assertEqual(self.hw_driver.create.call_count, 2)
        self.assertEqual(self.hw_driver.delete.call_count, 2)

        mport1 = self.hw_driver.delete.call_args_list[0][0][0]
        mport2 = self.hw_driver.delete.call_args_list[1][0][0]

        for manager_port in [mport1, mport2]:
            switch, switchport = self._get_switch_info_from_manager_port(
                manager_port, [self.switch1, self.switch2],
                switchports['switchports']
            )

            self._assert_switchinfo_equals(
                manager_port, switch['switch'], switchport)
            self._assert_netinfo_equals(
                manager_port, port['port'], self.net1['network'])

    def test_detach(self):
        switchports = self._make_switchports(
            self.fmt, [self.switch1, self.switch2],
            self.hardware_id, ['eth1/1', 'eth1/1'], ['eth0', 'eth1']
        )
        self._make_port_with_switchports(
            network=self.net1['network']['id'],
            switchports=switchports,
            commit=True,
            trunked=True)

        # assert that switch hardware driver was called for each switchport
        self.assertHWDriverNotCalled(exclude='create')
        self.assertEqual(self.hw_driver.create.call_count, 2)

        port = self._make_port_with_switchports(
            network=self.net2['network']['id'],
            switchports=switchports,
            commit=True,
            trunked=True)

        # assert that switch hardware driver was called for each switchport
        self.assertHWDriverNotCalled(exclude=['create', 'attach'])
        self.assertEqual(self.hw_driver.attach.call_count, 2)
        self.assertEqual(self.hw_driver.create.call_count, 2)

        self._delete('ports', port['port']['id'])

        self.assertHWDriverNotCalled(exclude=['create', 'attach', 'detach'])
        self.assertEqual(self.hw_driver.attach.call_count, 2)
        self.assertEqual(self.hw_driver.create.call_count, 2)
        self.assertEqual(self.hw_driver.detach.call_count, 2)

        mport1 = self.hw_driver.detach.call_args_list[0][0][0]
        mport2 = self.hw_driver.detach.call_args_list[1][0][0]

        for manager_port in [mport1, mport2]:
            switch, switchport = self._get_switch_info_from_manager_port(
                manager_port, [self.switch1, self.switch2],
                switchports['switchports']
            )

            self._assert_switchinfo_equals(
                manager_port, switch['switch'], switchport)
            self._assert_netinfo_equals(
                manager_port, port['port'], self.net2['network'])
