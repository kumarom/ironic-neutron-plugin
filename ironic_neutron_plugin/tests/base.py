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

import contextlib
import mock

from neutron import context
from neutron.plugins.ml2 import config as ml2_config
from neutron.tests.unit import test_db_plugin

from ironic_neutron_plugin import config as ironic_config
from ironic_neutron_plugin.drivers import manager
from ironic_neutron_plugin.extensions import switch as switch_extension
from ironic_neutron_plugin import plugin

import webob


ml2_config.cfg.CONF.import_opt('network_vlan_ranges',
                               'neutron.plugins.ml2.drivers.type_vlan',
                               group='ml2_type_vlan')

ML2_PLUGIN = 'ironic_neutron_plugin.plugin.IronicMl2Plugin'


def optional_ctx(obj, fallback):

    @contextlib.contextmanager
    def context_wrapper(val):
        yield val

    if obj:
        return context_wrapper(obj)
    else:
        return fallback()


class IronicMl2MechanismTestCase(test_db_plugin.NeutronDbPluginV2TestCase):

    fmt = 'json'
    _plugin_name = ML2_PLUGIN
    _mechanism_drivers = ['ironic']

    # automatically create fixtures (net1, net2, subnet1, etc)
    _dummy_data = False

    def setUp(self):

        ironic_config.cfg.CONF.set_override(
            'credential_secret',
            'sixteen byte key',
            group='ironic'
        )

        ml2_config.cfg.CONF.set_override('mechanism_drivers',
                                         self._mechanism_drivers,
                                         group='ml2')
        ml2_config.cfg.CONF.set_override('tenant_network_types',
                                         ['vlan'],
                                         group='ml2')

        self.physnet = 'physnet1'
        self.vlan_range = '1:100'
        self.phys_vrange = ':'.join([self.physnet, self.vlan_range])
        ml2_config.cfg.CONF.set_override(
            'network_vlan_ranges',
            [self.phys_vrange],
            group='ml2_type_vlan'
        )

        # Mock the hardware driver calls
        self.hw_driver = mock.Mock()
        mock.patch.object(manager.DriverManager,
                          '_get_driver',
                          return_value=self.hw_driver).start()

        ext_mgr = switch_extension.Switch()
        super(IronicMl2MechanismTestCase, self).setUp(
            self._plugin_name, ext_mgr=ext_mgr)

        self.port_create_status = 'DOWN'
        self.driver = plugin.IronicMl2Plugin()
        self.context = context.get_admin_context()

        if self._dummy_data:
            self._make_dummy_data()

    def _make_dummy_data(self):
        self.net1 = self._make_network(
            self.fmt, 'net1', True)
        self.net2 = self._make_network(
            self.fmt, 'net2', True)

        self.subnet1 = self._make_subnet(
            self.fmt, self.net1,
            '10.0.100.1', '10.0.100.0/24')
        self.subnet2 = self._make_subnet(
            self.fmt, self.net2,
            '10.0.200.1', '10.0.200.0/24')

        self.switch1 = self._make_switch(
            self.fmt, 'switch1', 'switch1.switch.com')
        self.switch2 = self._make_switch(
            self.fmt, 'switch2', 'switch2.switch.com')

        # massage our network a bit to look like a real response
        self.net1['network']['subnets'] = [self.subnet1['subnet']['id']]
        self.net1['network']['router:external'] = False
        self.net2['network']['subnets'] = [self.subnet2['subnet']['id']]
        self.net2['network']['router:external'] = False

        self.hardware_id = 'hardware1'

    def assertContains(self, d1, d2):
        """ensure all the keys in d1 are in and equal to d2."""
        for k, v in d1.items():
            self.assertTrue(k in d2)
            self.assertEqual(v, d2[k])
        return True

    def assertHWDriverNotCalled(self, exclude=None):
        if not exclude:
            exclude = []

        for op in ['create', 'attach', 'delete', 'detach']:
            if op in exclude:
                continue
            self.assertEqual(getattr(self.hw_driver, op).call_count, 0)

    def _make_switchport_req(self, swp):
        return {
            'switch_id': swp['switch_id'],
            'port': swp['port'],
            'name': swp['name']
        }

    def _make_port_with_switchports(self, network, commit=False,
                                    trunked=False, switchports=None,
                                    expected_status_code=201):
        ports = []
        if switchports:
            for swp in switchports['switchports']:
                ports.append(self._make_switchport_req(swp))

        res = self._create_port(
            self.fmt,
            network,
            context=self.context,
            arg_list=('trunked', 'commit',
                      'switch:ports', 'switch:hardware_id'),
            **{
                'trunked': trunked,
                'commit': commit,
                'switch:ports': ports,
                'switch:hardware_id': self.hardware_id
            }
        )
        self.assertEqual(res.status_code, expected_status_code)
        return self.deserialize(self.fmt, res)

    def _create_switch(self, fmt, id, host, arg_list=None, **kwargs):

        data = {'switch': {'id': id,
                           'host': host,
                           'username': 'foo',
                           'password': 'bar',
                           'type': 'dummy'}}

        for arg in (arg_list or ()):
            # Arg must be present
            if arg in kwargs:
                data['switch'][arg] = kwargs[arg]
        switch_req = self.new_create_request('switches', data, fmt)
        if (kwargs.get('set_context') and 'tenant_id' in kwargs):
            # create a specific auth context for this request
            switch_req.environ['neutron.context'] = context.Context(
                '', kwargs['tenant_id'])

        switch_res = switch_req.get_response(self.ext_api)
        return switch_res

    def _make_switch(self, fmt, id, host, **kwargs):
        res = self._create_switch(fmt, id, host, **kwargs)

        if res.status_int >= webob.exc.HTTPClientError.code:
            raise webob.exc.HTTPClientError(code=res.status_int)
        return self.deserialize(fmt, res)

    def _create_switchports(self, fmt, switches, hardware_id, ports, names,
                            arg_list=None, **kwargs):

        data = []

        for i, switch in enumerate(switches):
            data.append({
                'switch_id': switch['switch']['id'],
                'hardware_id': hardware_id,
                'port': ports[i],
                'name': names[i]
            })

        data = {"switchports": data}

        for arg in (arg_list or ()):
            # Arg must be present
            if arg in kwargs:
                data['switchport'][arg] = kwargs[arg]
        switchports_req = self.new_create_request('switchports', data, fmt)
        if (kwargs.get('set_context') and 'tenant_id' in kwargs):
            # create a specific auth context for this request
            switchports_req.environ['neutron.context'] = context.Context(
                '', kwargs['tenant_id'])

        switchports_res = switchports_req.get_response(self.ext_api)
        return switchports_res

    def _make_switchports(self, fmt, switches, hardware_id, ports, names,
                          **kwargs):
        res = self._create_switchports(fmt, switches, hardware_id,
                                       ports, names, **kwargs)

        if res.status_int >= webob.exc.HTTPClientError.code:
            raise webob.exc.HTTPClientError(code=res.status_int)
        return self.deserialize(fmt, res)

    @contextlib.contextmanager
    def switch(self, id='switch1', host='switch1.net', do_delete=True,
               **kwargs):
        switch = self._make_switch(self.fmt, id, host, **kwargs)
        yield switch
        if do_delete:
            self._delete('switches', switch['switch']['id'])

    @contextlib.contextmanager
    def switchports(self, hardware_id='hardware1', switches=None,
                    ports=['eth1/1'], names=['eth0'], do_delete=True,
                    **kwargs):
        with optional_ctx(switches, self.switch) as switches:

            if isinstance(switches, dict):
                switches = [switches]

            switchports = self._make_switchports(
                self.fmt,
                [s['switch']['id'] for s in switches],
                hardware_id,
                ports,
                names, **kwargs)
            yield switchports
            if do_delete:
                self._delete('switchports', hardware_id)
