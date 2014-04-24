# Copyright 2014 Rackspace, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from ironic_neutron_plugin.db import db as ironic_db
from ironic_neutron_plugin.tests import base

import mock

import webob


class TestNetworks(base.IronicPluginTestCase):

    def setUp(self):
        super(TestNetworks, self).setUp()

        self.network = self.deserialize(
            self.fmt,
            self._create_default_network('net1')
        )

    def test_create(self):
        net_id = self.network['network']['id']
        ironic_network = ironic_db.get_network(net_id)

        n_req = self.new_show_request('networks', net_id)
        n_res = n_req.get_response(self.api)
        n = self.deserialize(self.fmt, n_res)

        # assert the ironic network model is created and returned added to the
        # network response
        for key in ['segmentation_id', 'network_type', 'physical_network']:
            self.assertEqual(ironic_network[key],
                             n['network']['provider:%s' % key])
        self.assertEqual(ironic_network['trunked'],
                         n['network']['switch:trunked'])

    def test_delete(self):
        # assert ironic network model is created
        net_id = self.network['network']['id']
        ironic_network = ironic_db.get_network(net_id)
        self.assertEqual(ironic_network['network_id'], net_id)

        # delete the network
        del_req = self.new_delete_request('networks', net_id)
        del_res = del_req.get_response(self.api)

        # assert response code == 204
        self.assertEqual(del_res.status_int, webob.exc.HTTPNoContent.code)

        # assert the ironic network model is deleted
        ironic_network = ironic_db.get_network(net_id)
        self.assertEqual(ironic_network, None)

        # assert the neutron network is actually deleted
        n_req = self.new_show_request('networks', net_id)
        n_res = n_req.get_response(self.api)
        self.assertEqual(n_res.status_int, webob.exc.HTTPNotFound.code)

    def test_update(self):

        req = self.new_update_request(
            'networks', {}, self.network['network']['id'])
        res = req.get_response(self.api)

        self.assertEqual(res.status_int, webob.exc.HTTPBadRequest.code)


class TestPortsBase(base.IronicPluginTestCase):

    def _create_dummy_data(self, with_portmaps=True):

        self.network = self.deserialize(
            self.fmt,
            self._create_default_network('net1')
        )
        self.network_id = self.network['network']['id']

        self.access_network = self.deserialize(
            self.fmt,
            self._create_default_network('net2', False))
        self.access_network_id = self.access_network['network']['id']

        self.switch1 = self.deserialize(
            self.fmt,
            self._create_switch(self.fmt, '1.2.3.4')
        )
        self.switch2 = self.deserialize(
            self.fmt,
            self._create_switch(self.fmt, '5.6.7.8')
        )

        if with_portmaps:
            self._create_portmaps()

    def _create_portmaps(self):
        self.portmap1 = self.deserialize(
            self.fmt,
            self._create_portmap(
                fmt=self.fmt,
                switch_id=self.switch1['switch']['id'],
                device_id='device',
                port='1',
                primary=True)
        )
        self.portmap2 = self.deserialize(
            self.fmt,
            self._create_portmap(
                fmt=self.fmt,
                switch_id=self.switch2['switch']['id'],
                device_id='device',
                port='1',
                primary=False)
        )


class TestPorts(TestPortsBase):

    def test_create_with_same_network_raises(self):
        self._create_dummy_data()

        port_kwargs = {"device_id": "device",
                       "switch:portmaps": []}
        port_arg_list = ('switch:portmaps',)
        port_res = self._create_port(
            self.fmt, self.network_id,
            arg_list=port_arg_list, **port_kwargs)

        self.assertEqual(port_res.status_int, 201)

        port_res = self._create_port(
            self.fmt, self.network_id,
            arg_list=port_arg_list, **port_kwargs)

        self.assertEqual(port_res.status_int, 400)

    def test_create_trunked_with_existing_network(self):
        self._create_dummy_data()

        network2 = self.deserialize(
            self.fmt,
            self._create_default_network('net3')
        )
        network_id2 = network2['network']['id']

        port_kwargs = {"device_id": "device",
                       "switch:portmaps": []}
        port_arg_list = ('switch:portmaps',)
        port_res = self._create_port(
            self.fmt, self.network_id,
            arg_list=port_arg_list, **port_kwargs)

        self.assertEqual(port_res.status_int, 201)

        port_res = self._create_port(
            self.fmt, network_id2,
            arg_list=port_arg_list, **port_kwargs)

        self.assertEqual(port_res.status_int, 201)

    def test_create_access_with_existing_trunked_raises(self):
        self._create_dummy_data()

        port_kwargs = {"device_id": "device",
                       "switch:portmaps": []}
        port_arg_list = ('switch:portmaps',)
        port_res = self._create_port(
            self.fmt, self.network_id,
            arg_list=port_arg_list, **port_kwargs)

        self.assertEqual(port_res.status_int, 201)

        port_res = self._create_port(
            self.fmt, self.access_network_id,
            arg_list=port_arg_list, **port_kwargs)

        self.assertEqual(port_res.status_int, 400)

    def test_create_access_with_existing_access_raises(self):
        self._create_dummy_data()

        network2 = self.deserialize(
            self.fmt,
            self._create_default_network('net3', False)
        )
        network_id2 = network2['network']['id']

        port_kwargs = {"device_id": "device",
                       "switch:portmaps": []}
        port_arg_list = ('switch:portmaps',)
        port_res = self._create_port(
            self.fmt, self.access_network_id,
            arg_list=port_arg_list, **port_kwargs)

        self.assertEqual(port_res.status_int, 201)

        port_res = self._create_port(
            self.fmt, network_id2,
            arg_list=port_arg_list, **port_kwargs)

        self.assertEqual(port_res.status_int, 400)


class TestPortsMockedManager(TestPortsBase):

    def setUp(self):
        # mock out the driver manager
        self.driver_manager_mock = mock.Mock()
        self.driver_manager_patch = mock.patch(
            'ironic_neutron_plugin.plugin.manager',
            self.driver_manager_mock)
        self.driver_manager_patch.start()

        super(TestPortsMockedManager, self).setUp()

    def tearDown(self):
        if self.driver_manager_patch:
            self.driver_manager_patch.stop()
        super(TestPortsMockedManager, self).tearDown()

    def _get_mock(self):
        return self.driver_manager_mock.DriverManager()

    def test_device_id_is_required(self):
        self._create_dummy_data()

        port_res = self._create_port(self.fmt, self.network_id)

        self.assertEqual(port_res.status_int, webob.exc.HTTPBadRequest.code)

    def test_create_calls_attach(self):
        self._create_dummy_data()

        port_kwargs = {"device_id": "device",
                       "switch:portmaps": []}
        self._create_port(self.fmt, self.network_id,
                          arg_list=('switch:portmaps',), **port_kwargs)

        self._get_mock().attach.assertCalledOnce()

    def test_create_trunked(self):
        """create_port() with a trunked network, resulting in multiple
        portmaps used.
        """
        self._create_dummy_data()

        port_kwargs = {"device_id": "device",
                       "switch:portmaps": []}
        port_arg_list = ('switch:portmaps',)
        port_res = self._create_port(
            self.fmt, self.network_id,
            arg_list=port_arg_list, **port_kwargs)

        self.assertEqual(port_res.status_int, 201)
        port_res = self.deserialize(self.fmt, port_res)

        # assert correct portmaps were returned in response
        portmaps = port_res['port']['switch:portmaps']
        portmap_ids = set([p['id'] for p in portmaps])
        self.assertEqual(len(portmap_ids), 2)
        self.assertEqual(
            self.portmap1['portmap']['id'] in portmap_ids, True)
        self.assertEqual(
            self.portmap2['portmap']['id'] in portmap_ids, True)

        # assert driver manager was called with correct arguments
        self._get_mock().attach.assertCalledOnce()
        mock_args = self._get_mock().attach.call_args[0]
        port, ironic_network, ironic_ports = mock_args
        self.assertEqual(port_res["port"], port)

        self.assertEqual(
            ironic_db.get_network(self.network_id).as_dict(),
            ironic_network.as_dict()
        )

        ironic_ports_dict = [p.as_dict() for p in ironic_ports]
        self.assertEqual(len(ironic_ports), 2)
        self.assertTrue(self.portmap1['portmap'] in ironic_ports_dict)
        self.assertTrue(self.portmap2['portmap'] in ironic_ports_dict)

    def test_create_access(self):
        """create_port() with an access network, resulting in only
        the primary portmap being used.
        """
        self._create_dummy_data()

        port_kwargs = {"device_id": "device",
                       "switch:portmaps": []}
        port_arg_list = ('switch:portmaps',)
        port_res = self._create_port(
            self.fmt, self.access_network_id,
            arg_list=port_arg_list, **port_kwargs)

        self.assertEqual(port_res.status_int, 201)
        port_res = self.deserialize(self.fmt, port_res)

        portmaps = port_res['port']['switch:portmaps']
        portmap_ids = set([p['id'] for p in portmaps])
        self.assertEqual(len(portmap_ids), 1)
        self.assertEqual(
            self.portmap1['portmap']['id'] in portmap_ids, True)

        # assert driver manager was called with correct arguments
        self._get_mock().attach.assertCalledOnce()
        mock_args = self._get_mock().attach.call_args[0]
        port, ironic_network, ironic_ports = mock_args
        self.assertEqual(port_res["port"], port)

        self.assertEqual(
            ironic_db.get_network(self.access_network_id).as_dict(),
            ironic_network.as_dict()
        )

        ironic_ports_dict = [p.as_dict() for p in ironic_ports]
        self.assertEqual(len(ironic_ports), 1)
        self.assertTrue(self.portmap1['portmap'] in ironic_ports_dict)

    def test_create_trunked_with_existing_portmap(self):
        """Test create_port() while passing in portmap information
        that matches what already exists in the database.
        """
        self._create_dummy_data()

        pm1 = self.portmap1["portmap"].copy()
        pm1.pop("id")

        pm2 = self.portmap2["portmap"].copy()
        pm2.pop("id")

        portmaps = [pm1, pm2]

        port_kwargs = {"device_id": "device",
                       "switch:portmaps": portmaps}
        port_arg_list = ('switch:portmaps',)
        port_res = self._create_port(
            self.fmt, self.network_id,
            arg_list=port_arg_list, **port_kwargs)

        self.assertEqual(port_res.status_int, 201)

        mock_args = self._get_mock().attach.call_args[0]
        port, ironic_network, ironic_ports = mock_args

        ironic_ports_dict = [p.as_dict() for p in ironic_ports]
        self.assertEqual(len(ironic_ports), 2)
        self.assertTrue(self.portmap1['portmap'] in ironic_ports_dict)
        self.assertTrue(self.portmap2['portmap'] in ironic_ports_dict)

    def test_create_access_with_existing_portmap(self):
        """Test create_port() while passing in portmap information
        that matches what already exists in the database.
        """
        self._create_dummy_data()

        pm1 = self.portmap1["portmap"].copy()
        pm1.pop("id")

        pm2 = self.portmap2["portmap"].copy()
        pm2.pop("id")

        portmaps = [pm1, pm2]

        port_kwargs = {"device_id": "device",
                       "switch:portmaps": portmaps}
        port_arg_list = ('switch:portmaps',)
        port_res = self._create_port(
            self.fmt, self.access_network_id,
            arg_list=port_arg_list, **port_kwargs)

        self.assertEqual(port_res.status_int, 201)

        mock_args = self._get_mock().attach.call_args[0]
        port, ironic_network, ironic_ports = mock_args

        ironic_ports_dict = [p.as_dict() for p in ironic_ports]
        self.assertEqual(len(ironic_ports), 1)
        self.assertTrue(self.portmap1['portmap'] in ironic_ports_dict)

    def test_create_trunked_with_new_portmap(self):
        self._create_dummy_data(with_portmaps=False)

        # assert no ports for the device exist
        ports = ironic_db.filter_portmaps(
            device_id="device")
        self.assertEqual(len(list(ports)), 0)

        pm1 = {
            "switch_id": self.switch1["switch"]["id"],
            "device_id": "device",
            "port": "1",
            "primary": True
        }

        pm2 = {
            "switch_id": self.switch2["switch"]["id"],
            "device_id": "device",
            "port": "1",
            "primary": False
        }

        portmaps = [pm1, pm2]

        port_kwargs = {"device_id": "device",
                       "switch:portmaps": portmaps}
        port_arg_list = ('switch:portmaps',)
        port_res = self._create_port(
            self.fmt, self.network_id,
            arg_list=port_arg_list, **port_kwargs)

        self.assertEqual(port_res.status_int, 201)

        # assert a port was created
        ports = ironic_db.filter_portmaps(device_id="device")
        self.assertEqual(len(list(ports)), 2)

        mock_args = self._get_mock().attach.call_args[0]
        port, ironic_network, ironic_ports = mock_args

        ironic_ports_dict = [p.as_dict() for p in ironic_ports]
        self.assertEqual(len(ironic_ports), 2)
        self.assertTrue(ports[0].as_dict() in ironic_ports_dict)
        self.assertTrue(ports[1].as_dict() in ironic_ports_dict)

    def test_create_access_with_new_portmap(self):
        self._create_dummy_data(with_portmaps=False)

        # assert no ports for the device exist
        ports = ironic_db.filter_portmaps(device_id="device")
        self.assertEqual(len(list(ports)), 0)

        pm1 = {
            "switch_id": self.switch1["switch"]["id"],
            "device_id": "device",
            "port": "1",
            "primary": True
        }

        portmaps = [pm1]

        port_kwargs = {"device_id": "device",
                       "switch:portmaps": portmaps}
        port_arg_list = ('switch:portmaps',)
        port_res = self._create_port(self.fmt, self.access_network_id,
                                     arg_list=port_arg_list, **port_kwargs)

        self.assertEqual(port_res.status_int, 201)

        # assert a port was created
        ports = ironic_db.filter_portmaps(device_id="device")
        self.assertEqual(len(list(ports)), 1)

        # assert the port was passed to the driver manager
        mock_args = self._get_mock().attach.call_args[0]
        port, ironic_network, ironic_ports = mock_args

        ironic_ports_dict = [p.as_dict() for p in ironic_ports]
        self.assertEqual(len(ironic_ports), 1)
        self.assertTrue(ports[0].as_dict() in ironic_ports_dict)

    def test_create_with_different_portmap_raises(self):
        """Test create_port() while passing in portmap information
        that matches what already exists in the database.
        """
        self._create_dummy_data()

        pm1 = self.portmap1["portmap"].copy()
        pm1.pop("id")

        pm2 = self.portmap2["portmap"].copy()
        pm2.pop("id")
        pm2["port"] = "5"

        portmaps = [pm1, pm2]

        port_kwargs = {"device_id": "device",
                       "switch:portmaps": portmaps}
        port_arg_list = ('switch:portmaps',)
        port_res = self._create_port(self.fmt, self.network_id,
                                     arg_list=port_arg_list, **port_kwargs)

        self.assertEqual(port_res.status_int, 400)


class TestSwitches(base.IronicPluginTestCase):

    def setUp(self):
        super(TestSwitches, self).setUp()

    def test_get_raises_404(self):
        req = self.new_show_request('switches', 'foobar')
        res = req.get_response(self.ext_api)

        self.assertEqual(res.status_int, webob.exc.HTTPNotFound.code)

    def test_get(self):
        switch = self._create_switch(self.fmt, '1.2.3.4')
        switch = self.deserialize(self.fmt, switch)

        req = self.new_show_request('switches', switch['switch']['id'])
        res = self.deserialize(self.fmt, req.get_response(self.ext_api))

        self.assertEqual(res['switch']['ip'], '1.2.3.4')

    def test_create(self):
        switch = self._create_switch(self.fmt, '1.2.3.4')
        switch = self.deserialize(self.fmt, switch)

        self.assertEqual(switch['switch']['ip'], '1.2.3.4')

    def test_delete(self):
        switch = self.deserialize(
            self.fmt, self._create_switch(self.fmt, '1.2.3.4')
        )
        switch_id = switch['switch']['id']

        req = self.new_delete_request('switches', switch_id)
        res = req.get_response(self.ext_api)

        self.assertEqual(res.status_int, webob.exc.HTTPNoContent.code)

        switch = ironic_db.get_switch(switch_id)
        self.assertEqual(switch, None)

    def test_delete_cascade_delete_portmaps(self):
        switch = self.deserialize(
            self.fmt, self._create_switch(self.fmt, '1.2.3.4')
        )
        switch_id = switch['switch']['id']

        portmap = self._create_portmap(
            fmt=self.fmt,
            switch_id=switch_id,
            device_id='device',
            port='1',
            primary=True)
        portmap = self.deserialize(self.fmt, portmap)
        portmap_id = portmap['portmap']['id']

        # assert portmap is created
        portmap = ironic_db.get_portmap(portmap_id)
        self.assertEqual(portmap['id'], portmap_id)
        self.assertEqual(portmap['switch_id'], switch_id)

        # delete switch
        req = self.new_delete_request('switches', switch_id)
        res = req.get_response(self.ext_api)
        self.assertEqual(res.status_int, webob.exc.HTTPNoContent.code)

        # assert portmap was deleted in the cascade
        portmap = ironic_db.get_portmap(portmap_id)
        self.assertEqual(portmap, None)


class TestPortMaps(base.IronicPluginTestCase):

    def setUp(self):
        super(TestPortMaps, self).setUp()

        self.switch = self.deserialize(
            self.fmt, self._create_switch(self.fmt, '1.2.3.4')
        )
        self.switch_id = self.switch['switch']['id']

    def test_get_raises_404(self):
        req = self.new_show_request('portmaps', 'foobar')
        res = req.get_response(self.ext_api)

        self.assertEqual(res.status_int, webob.exc.HTTPNotFound.code)

    def test_get(self):
        portmap = self._create_portmap(
            fmt=self.fmt,
            switch_id=self.switch_id,
            device_id='device',
            port='1',
            primary=True)
        portmap = self.deserialize(self.fmt, portmap)
        portmap_id = portmap['portmap']['id']

        req = self.new_show_request('portmaps', portmap_id)
        res = self.deserialize(self.fmt, req.get_response(self.ext_api))

        self.assertEqual(res['portmap']['id'], portmap_id)
        self.assertEqual(res['portmap']['switch_id'], self.switch_id)

    def test_create(self):
        portmap1 = self._create_portmap(
            fmt=self.fmt,
            switch_id=self.switch_id,
            device_id='device',
            port='1',
            primary=True)
        portmap1 = self.deserialize(self.fmt, portmap1)

        portmap2 = self._create_portmap(
            fmt=self.fmt,
            switch_id=self.switch_id,
            device_id='device',
            port='2',
            primary=False)
        portmap2 = self.deserialize(self.fmt, portmap2)

        self.assertEqual(
            portmap1['portmap']['switch_id'], self.switch_id)
        self.assertEqual(
            portmap1['portmap']['port'], '1')
        self.assertEqual(
            portmap2['portmap']['switch_id'], self.switch_id)
        self.assertEqual(
            portmap2['portmap']['port'], '2')

    def test_only_one_primary_allowed(self):
        pm1_res = self._create_portmap(
            fmt=self.fmt,
            switch_id=self.switch_id,
            device_id='device',
            port='1',
            primary=True)

        pm2_res = self._create_portmap(
            fmt=self.fmt,
            switch_id=self.switch_id,
            device_id='device',
            port='1',
            primary=True)

        self.assertEqual(pm1_res.status_int, 200)
        self.assertEqual(pm2_res.status_int, webob.exc.HTTPBadRequest.code)

    def test_only_one_map_per_port(self):
        pm1_res = self._create_portmap(
            fmt=self.fmt,
            switch_id=self.switch_id,
            device_id='device',
            port='1',
            primary=True)

        pm2_res = self._create_portmap(
            fmt=self.fmt,
            switch_id=self.switch_id,
            device_id='device',
            port='1',
            primary=False)

        self.assertEqual(pm1_res.status_int, 200)
        self.assertEqual(pm2_res.status_int, webob.exc.HTTPBadRequest.code)

    def test_only_two_maps_per_device(self):

        pm1_res = self._create_portmap(
            fmt=self.fmt,
            switch_id=self.switch_id,
            device_id='device',
            port='1',
            primary=True)

        pm2_res = self._create_portmap(
            fmt=self.fmt,
            switch_id=self.switch_id,
            device_id='device',
            port='2',
            primary=False)

        pm3_res = self._create_portmap(
            fmt=self.fmt,
            switch_id=self.switch_id,
            device_id='device',
            port='3',
            primary=False)

        self.assertEqual(pm1_res.status_int, 200)
        self.assertEqual(pm2_res.status_int, 200)
        self.assertEqual(pm3_res.status_int, webob.exc.HTTPBadRequest.code)

    def test_delete(self):
        portmap = self._create_portmap(
            fmt=self.fmt,
            switch_id=self.switch_id,
            device_id='device',
            port='1',
            primary=True)
        portmap = self.deserialize(self.fmt, portmap)
        portmap_id = portmap['portmap']['id']

        req = self.new_delete_request('portmaps', portmap_id)
        res = req.get_response(self.ext_api)

        self.assertEqual(res.status_int, webob.exc.HTTPNoContent.code)

        portmap = ironic_db.get_portmap(portmap_id)
        self.assertEqual(portmap, None)
