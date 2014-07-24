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

from ironic_neutron_plugin.tests import base
from neutron.tests.unit import test_db_plugin

"""
These are mostly copied wholesale or subclassed where possible
from the upstream ml2 tests.

TODO(morgabra) These aren't very 'unit-y' unit tests.
"""


class TestIronicBasicGet(base.IronicMl2MechanismTestCase,
                         test_db_plugin.TestBasicGet):
    pass


class TestIronicV2HTTPResponse(base.IronicMl2MechanismTestCase,
                               test_db_plugin.TestV2HTTPResponse):
    pass


class TestIronicNetworksV2(base.IronicMl2MechanismTestCase,
                           test_db_plugin.TestNetworksV2):
    pass


class TestIronicSubnetsV2(base.IronicMl2MechanismTestCase,
                          test_db_plugin.TestSubnetsV2):
    pass


class TestIronicPortsV2(base.IronicMl2MechanismTestCase,
                        test_db_plugin.TestPortsV2):
    pass


class TestIronicPlugin(base.IronicMl2MechanismTestCase):
    """Plugin tests that exercise the 'switch', 'commit',
    and 'trunked' extensions.
    """

    _dummy_data = True

    def test_create_no_commit_with_no_switchports(self):
        port = self._make_port_with_switchports(
            network=self.net1['network']['id'],
            commit=False)
        self.assertEqual(
            port['port']['network_id'], self.net1['network']['id'])
        self.assertHWDriverNotCalled()

    def test_create_commit_with_no_switchports_raises(self):
        self._make_port_with_switchports(
            network=self.net1['network']['id'],
            commit=True,
            expected_status_code=400)
        self.assertHWDriverNotCalled()

    def test_create_commit_no_hardware_id(self):
        switchports = self._make_switchports(
            self.fmt, [self.switch1, self.switch2],
            self.hardware_id, ['eth1/1', 'eth1/1'], ['eth0', 'eth1']
        )

        ports = []
        if switchports:
            for swp in switchports['switchports']:
                ports.append(self._make_switchport_req(swp))

        res = self._create_port(
            self.fmt,
            self.net1['network']['id'],
            context=self.context,
            arg_list=('trunked', 'commit', 'switch:ports'),
            **{
                'trunked': False,
                'commit': True,
                'switch:ports': ports,
            }
        )
        self.assertEqual(res.status_code, 400)
        self.assertTrue(
            "switch:ports requires switch:hardware_id" in res.body)

    def test_create_commit_with_switchports(self):
        """Base sanity test for port_create()."""
        switchports = self._make_switchports(
            self.fmt, [self.switch1, self.switch2],
            self.hardware_id, ['eth1/1', 'eth1/1'], ['eth0', 'eth1']
        )

        port = self._make_port_with_switchports(
            network=self.net1['network']['id'],
            switchports=switchports,
            commit=True)

        # assert the response returned extension data
        self.assertEqual(port['port']['switch:hardware_id'],
                         self.hardware_id)
        self.assertEqual(len(port['port']['switch:ports']), 2)
        self.assertContains(switchports['switchports'][0],
                            port['port']['switch:ports'][0])
        self.assertContains(switchports['switchports'][1],
                            port['port']['switch:ports'][1])
        self.assertEqual(port['port']['commit'], True)
        self.assertEqual(port['port']['trunked'], False)

        # assert that the switch hardware driver was called for
        # each switchport
        self.assertHWDriverNotCalled(exclude='create')
        self.assertEqual(self.hw_driver.create.call_count, 2)

    def test_create_no_commit_with_switchports(self):
        switchports = self._make_switchports(
            self.fmt, [self.switch1, self.switch2],
            self.hardware_id, ['eth1/1', 'eth1/1'], ['eth0', 'eth1']
        )

        port = self._make_port_with_switchports(
            network=self.net1['network']['id'],
            switchports=switchports)

        # assert the response returned extension data
        self.assertEqual(port['port']['switch:hardware_id'],
                         self.hardware_id)
        self.assertEqual(len(port['port']['switch:ports']), 2)
        self.assertContains(switchports['switchports'][0],
                            port['port']['switch:ports'][0])
        self.assertContains(switchports['switchports'][1],
                            port['port']['switch:ports'][1])
        self.assertEqual(port['port']['commit'], False)
        self.assertEqual(port['port']['trunked'], False)

        self.assertHWDriverNotCalled()

    def test_update_commit_no_switchports_raises(self):
        port = self._make_port_with_switchports(
            network=self.net1['network']['id'],
            commit=False)

        req = self.new_update_request(
            resource='ports',
            data={"port": {"commit": True}},
            id=port['port']['id'])
        res = req.get_response(self.api)

        self.assertEqual(res.status_code, 400)
        self.assertTrue("no switchports found" in res.body)
        self.assertHWDriverNotCalled()

    def test_update_commit_with_switchports(self):
        switchports = self._make_switchports(
            self.fmt, [self.switch1, self.switch2],
            self.hardware_id, ['eth1/1', 'eth1/1'], ['eth0', 'eth1']
        )

        ports = []
        for swp in switchports['switchports']:
            ports.append(self._make_switchport_req(swp))

        port = self._make_port_with_switchports(
            network=self.net1['network']['id'],
            commit=False)

        req = self.new_update_request(
            resource='ports',
            data={"port": {"commit": True,
                           "switch:ports": ports,
                           "switch:hardware_id": self.hardware_id}},
            id=port['port']['id'])
        res = req.get_response(self.api)
        res_body = res.json.copy()

        self.assertEqual(res.status_code, 200)
        self.assertNotEqual(port['port']['commit'], res_body['port']['commit'])
        port['port'].pop('commit')
        res_body['port'].pop('commit')
        self.assertContains(port['port'], res_body['port'])

        self.assertHWDriverNotCalled(exclude='create')
        self.assertEqual(self.hw_driver.create.call_count, 2)

    def test_update_trunked(self):
        port = self._make_port_with_switchports(
            network=self.net1['network']['id'],
            commit=False)

        req = self.new_update_request(
            resource='ports',
            data={"port": {"trunked": True}},
            id=port['port']['id'])
        res = req.get_response(self.api)

        self.assertEqual(res.status_code, 200)
        self.assertNotEqual(port['port']['trunked'],
                            res.json['port']['trunked'])
        self.assertHWDriverNotCalled()

    def test_update_trunked_when_comitted_raises(self):
        switchports = self._make_switchports(
            self.fmt, [self.switch1, self.switch2],
            self.hardware_id, ['eth1/1', 'eth1/1'], ['eth0', 'eth1']
        )

        port = self._make_port_with_switchports(
            network=self.net1['network']['id'],
            switchports=switchports,
            commit=True)
        self.assertHWDriverNotCalled(exclude='create')
        self.assertEqual(self.hw_driver.create.call_count, 2)

        req = self.new_update_request(resource='ports',
                                      data={"port": {"trunked": True}},
                                      id=port['port']['id'])
        res = req.get_response(self.api)

        self.assertEqual(res.status_code, 400)
        self.assertTrue("cannot update trunked flag" in res.body)
        self.assertHWDriverNotCalled(exclude='create')
        self.assertEqual(self.hw_driver.create.call_count, 2)

    def test_attach_trunked_to_trunked(self):
        switchports = self._make_switchports(
            self.fmt, [self.switch1, self.switch2],
            self.hardware_id, ['eth1/1', 'eth1/1'], ['eth0', 'eth1']
        )

        port1 = self._make_port_with_switchports(
            network=self.net1['network']['id'],
            switchports=switchports,
            trunked=True,
            commit=True)
        self.assertHWDriverNotCalled(exclude='create')
        self.assertEqual(self.hw_driver.create.call_count, 2)

        port2 = self._make_port_with_switchports(
            network=self.net2['network']['id'],
            switchports=switchports,
            trunked=True,
            commit=True)
        self.assertHWDriverNotCalled(exclude=['create', 'attach'])
        self.assertEqual(self.hw_driver.create.call_count, 2)
        self.assertEqual(self.hw_driver.attach.call_count, 2)

        self.assertEqual(port1['port']['network_id'],
                         self.net1['network']['id'])
        self.assertEqual(port1['port']['commit'], True)
        self.assertEqual(port1['port']['trunked'], True)
        self.assertEqual(port2['port']['network_id'],
                         self.net2['network']['id'])
        self.assertEqual(port2['port']['commit'], True)
        self.assertEqual(port2['port']['trunked'], True)

    def test_attach_trunked_to_not_trunked(self):
        switchports = self._make_switchports(
            self.fmt, [self.switch1, self.switch2],
            self.hardware_id, ['eth1/1', 'eth1/1'], ['eth0', 'eth1']
        )

        port1 = self._make_port_with_switchports(
            network=self.net1['network']['id'],
            switchports=switchports,
            trunked=True,
            commit=True)
        self.assertHWDriverNotCalled(exclude='create')
        self.assertEqual(self.hw_driver.create.call_count, 2)

        port2 = self._make_port_with_switchports(
            network=self.net2['network']['id'],
            switchports=switchports,
            trunked=False,
            commit=True,
            expected_status_code=400)
        self.assertHWDriverNotCalled(exclude='create')
        self.assertEqual(self.hw_driver.create.call_count, 2)

        self.assertEqual(port1['port']['network_id'],
                         self.net1['network']['id'])
        self.assertEqual(port1['port']['commit'], True)
        self.assertEqual(port1['port']['trunked'], True)

        msg = 'Cannot attach non-trunked network, port already bound'
        self.assertTrue(msg in str(port2))

    def test_attach_not_trunked_to_trunked(self):
        switchports = self._make_switchports(
            self.fmt, [self.switch1, self.switch2],
            self.hardware_id, ['eth1/1', 'eth1/1'], ['eth0', 'eth1']
        )

        port1 = self._make_port_with_switchports(
            network=self.net1['network']['id'],
            switchports=switchports,
            trunked=False,
            commit=True)
        self.assertHWDriverNotCalled(exclude='create')
        self.assertEqual(self.hw_driver.create.call_count, 2)

        port2 = self._make_port_with_switchports(
            network=self.net2['network']['id'],
            switchports=switchports,
            trunked=True,
            commit=True,
            expected_status_code=400)
        self.assertHWDriverNotCalled(exclude='create')
        self.assertEqual(self.hw_driver.create.call_count, 2)

        self.assertEqual(port1['port']['network_id'],
                         self.net1['network']['id'])
        self.assertEqual(port1['port']['commit'], True)
        self.assertEqual(port1['port']['trunked'], False)

        self.assertTrue('Already attached via non-trunked port' in str(port2))

    def test_attach_not_trunked_to_not_trunked(self):
        switchports = self._make_switchports(
            self.fmt, [self.switch1, self.switch2],
            self.hardware_id, ['eth1/1', 'eth1/1'], ['eth0', 'eth1']
        )

        port1 = self._make_port_with_switchports(
            network=self.net1['network']['id'],
            switchports=switchports,
            trunked=False,
            commit=True)
        self.assertHWDriverNotCalled(exclude='create')
        self.assertEqual(self.hw_driver.create.call_count, 2)

        port2 = self._make_port_with_switchports(
            network=self.net2['network']['id'],
            switchports=switchports,
            trunked=False,
            commit=True,
            expected_status_code=400)
        self.assertHWDriverNotCalled(exclude='create')
        self.assertEqual(self.hw_driver.create.call_count, 2)

        self.assertEqual(port1['port']['network_id'],
                         self.net1['network']['id'])
        self.assertEqual(port1['port']['commit'], True)
        self.assertEqual(port1['port']['trunked'], False)

        msg = 'Cannot attach non-trunked network, port already bound'
        self.assertTrue(msg in str(port2))

    def test_delete(self):
        switchports = self._make_switchports(
            self.fmt, [self.switch1, self.switch2],
            self.hardware_id, ['eth1/1', 'eth1/1'], ['eth0', 'eth1']
        )

        port1 = self._make_port_with_switchports(
            network=self.net1['network']['id'],
            switchports=switchports,
            trunked=True,
            commit=True)
        self.assertHWDriverNotCalled(exclude='create')
        self.assertEqual(self.hw_driver.create.call_count, 2)

        port2 = self._make_port_with_switchports(
            network=self.net2['network']['id'],
            switchports=switchports,
            trunked=True,
            commit=True)
        self.assertHWDriverNotCalled(exclude=['create', 'attach'])
        self.assertEqual(self.hw_driver.create.call_count, 2)
        self.assertEqual(self.hw_driver.attach.call_count, 2)

        self._delete('ports', port1['port']['id'])

        self.assertHWDriverNotCalled(exclude=['create', 'attach', 'detach'])
        self.assertEqual(self.hw_driver.create.call_count, 2)
        self.assertEqual(self.hw_driver.attach.call_count, 2)
        self.assertEqual(self.hw_driver.detach.call_count, 2)

        self._delete('ports', port2['port']['id'])

        self.assertEqual(self.hw_driver.create.call_count, 2)
        self.assertEqual(self.hw_driver.attach.call_count, 2)
        self.assertEqual(self.hw_driver.detach.call_count, 2)
        self.assertEqual(self.hw_driver.delete.call_count, 2)
