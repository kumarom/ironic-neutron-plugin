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
from ironic_neutron_plugin.extensions import switch as switch_extension

import mock

from neutron import context
from neutron.tests.unit import test_db_plugin

import os
from oslo.config import cfg

import webob

PLUGIN_NAME = "ironic_neutron_plugin.plugin.IronicPlugin"


class IronicPluginTestCase(test_db_plugin.NeutronDbPluginV2TestCase):

    fmt = 'json'

    def setUp(self):

        extensions_path = os.path.dirname(os.path.realpath(__file__))
        cfg.CONF.set_override(
            "api_extensions_path",
            os.path.join(extensions_path, "../../extensions")
        )

        ext_mgr = switch_extension.Switch()
        super(IronicPluginTestCase, self).setUp(PLUGIN_NAME,
                                                ext_mgr=ext_mgr)

        self.context = context.get_admin_context()

    def tearDown(self):
        super(IronicPluginTestCase, self).tearDown()

    def _create_default_network(self, name):
        """We require the provider and switch extensions
        for networks, so we have a helper with sane defaults.
        """

        arg_list = (
            "switch:trunked",
            "provider:segmentation_id",
            "provider:network_type",
            "provider:physical_network"
        )

        kwargs = {
            "switch:trunked": True,
            "provider:segmentation_id": 100,
            "provider:network_type": "vlan",
            "provider:physical_network": "snet"
        }

        return self._create_network(
            self.fmt, name, True, arg_list=arg_list, **kwargs)

    def _create_switch(self, fmt, ip, arg_list=None, **kwargs):

        data = {'switch': {'ip': ip,
                           'username': 'foo',
                           'password': 'bar',
                           'type': 'dummy'}}

        for arg in (arg_list or ()):
            # Arg must be present
            if arg in kwargs:
                data['port'][arg] = kwargs[arg]
        switch_req = self.new_create_request('switches', data, fmt)
        if (kwargs.get('set_context') and 'tenant_id' in kwargs):
            # create a specific auth context for this request
            switch_req.environ['neutron.context'] = context.Context(
                '', kwargs['tenant_id'])

        switch_res = switch_req.get_response(self.ext_api)
        return switch_res

    def _create_portmap(self, fmt, switch_id, device_id, port, primary,
                        arg_list=None, **kwargs):

        data = {'portmap': {'switch_id': switch_id,
                            'device_id': device_id,
                            'port': port,
                            'primary': primary}}

        for arg in (arg_list or ()):
            # Arg must be present
            if arg in kwargs:
                data['port'][arg] = kwargs[arg]
        portmap_req = self.new_create_request('portmaps', data, fmt)
        if (kwargs.get('set_context') and 'tenant_id' in kwargs):
            # create a specific auth context for this request
            portmap_req.environ['neutron.context'] = context.Context(
                '', kwargs['tenant_id'])

        portmap_res = portmap_req.get_response(self.ext_api)
        return portmap_res


class TestNetworks(IronicPluginTestCase):

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


class TestPorts(IronicPluginTestCase):

    def setUp(self):

        # mock out the driver manager
        self.driver_manager_mock = mock.Mock()
        self.driver_manager_patch = mock.patch(
            'ironic_neutron_plugin.plugin.manager',
            self.driver_manager_mock)
        self.driver_manager_patch.start()

        super(TestPorts, self).setUp()

    def tearDown(self):
        self.driver_manager_patch.stop()
        super(IronicPluginTestCase, self).tearDown()

    def _create_dummy_data(self):

        self.network = self.deserialize(
            self.fmt,
            self._create_default_network('net1')
        )
        self.network_id = self.network['network']['id']

        self.switch1 = self.deserialize(
            self.fmt,
            self._create_switch(self.fmt, '1.2.3.4')
        )
        self.switch2 = self.deserialize(
            self.fmt,
            self._create_switch(self.fmt, '5.6.7.8')
        )

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

    def _get_mock(self):
        return self.driver_manager_mock.DriverManager()

    def test_device_id_is_required(self):
        self._create_dummy_data()

        port_res = self._create_port(self.fmt, self.network_id)

        self.assertEqual(port_res.status_int, webob.exc.HTTPBadRequest.code)

    def test_create_calls_attach(self):
        self._create_dummy_data()

        self._create_port(self.fmt, self.network_id, device_id='device')

        self._get_mock().attach.assertCalledOnce()


class TestSwitches(IronicPluginTestCase):

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


class TestPortMaps(IronicPluginTestCase):

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
