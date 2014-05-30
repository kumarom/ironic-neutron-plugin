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

import mock

import os

from neutron import context
from neutron.openstack.common import log as logging
from neutron.plugins.common import constants as p_const
from neutron.plugins.ml2 import config as ml2_config
from neutron.plugins.ml2 import driver_api as api
from neutron.plugins.ml2 import driver_context
from neutron.plugins.ml2.drivers import type_vlan as vlan_config
from neutron.tests.unit import test_db_plugin

from ironic_neutron_plugin import config as ironic_config
from ironic_neutron_plugin.extensions import switch as switch_extension


LOG = logging.getLogger(__name__)
ML2_PLUGIN = 'ironic_neutron_plugin.plugin.IronicMl2Plugin'
PHYS_NET = 'physnet1'
COMP_HOST_NAME = 'testhost'
COMP_HOST_NAME_2 = 'testhost_2'
VLAN_START = 1000
VLAN_END = 1100
NEXUS_IP_ADDR = '1.1.1.1'
NETWORK_NAME = 'test_network'
NETWORK_NAME_2 = 'test_network_2'
NEXUS_INTERFACE = '1/1'
NEXUS_INTERFACE_2 = '1/2'
CIDR_1 = '10.0.0.0/24'
CIDR_2 = '10.0.1.0/24'
DEVICE_ID_1 = '11111111-1111-1111-1111-111111111111'
DEVICE_ID_2 = '22222222-2222-2222-2222-222222222222'
DEVICE_OWNER = 'compute:None'
BOUND_SEGMENT1 = {api.NETWORK_TYPE: p_const.TYPE_VLAN,
                  api.PHYSICAL_NETWORK: PHYS_NET,
                  api.SEGMENTATION_ID: VLAN_START}
BOUND_SEGMENT2 = {api.NETWORK_TYPE: p_const.TYPE_VLAN,
                  api.PHYSICAL_NETWORK: PHYS_NET,
                  api.SEGMENTATION_ID: VLAN_START + 1}


class IronicMl2MechanismTestCase(test_db_plugin.NeutronDbPluginV2TestCase):

    def setUp(self):

        self.fmt = 'json'

        extensions_path = os.path.dirname(os.path.realpath(__file__))
        ironic_config.cfg.CONF.set_override(
            'api_extensions_path',
            os.path.join(extensions_path, '../extensions')
        )

        ironic_config.cfg.CONF.set_override(
            'credential_secret',
            'sixteen byte key',
            group='ironic'
        )

        ml2_opts = {
            'mechanism_drivers': ['ironic'],
            'tenant_network_types': ['vlan'],
            'type_drivers': ['vlan']
        }
        for opt, val in ml2_opts.items():
                ml2_config.cfg.CONF.set_override(opt, val, 'ml2')

        # Configure the ML2 VLAN parameters
        phys_vrange = ':'.join([PHYS_NET, str(VLAN_START), str(VLAN_END)])
        vlan_config.cfg.CONF.set_override('network_vlan_ranges',
                                          [phys_vrange],
                                          'ml2_type_vlan')

        # Mock port context values for bound_segments and 'status'.
        self.mock_bound_segment = mock.patch.object(
            driver_context.PortContext,
            'bound_segment',
            new_callable=mock.PropertyMock).start()
        self.mock_bound_segment.return_value = BOUND_SEGMENT1

        self.mock_original_bound_segment = mock.patch.object(
            driver_context.PortContext,
            'original_bound_segment',
            new_callable=mock.PropertyMock).start()
        self.mock_original_bound_segment.return_value = None

        ext_mgr = switch_extension.Switch()
        super(IronicMl2MechanismTestCase, self).setUp(
            'ironic_neutron_plugin.plugin.IronicMl2Plugin',
            ext_mgr=ext_mgr)

        self.port_create_status = 'DOWN'

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

    def _create_switchport(self, fmt, switch_id, hardware_id, port, name,
                           arg_list=None, **kwargs):

        data = {'switchport': {'switch_id': switch_id,
                               'hardware_id': hardware_id,
                               'port': port,
                               'name': name}}

        for arg in (arg_list or ()):
            # Arg must be present
            if arg in kwargs:
                data['switchport'][arg] = kwargs[arg]
        switchport_req = self.new_create_request('switchports', data, fmt)
        if (kwargs.get('set_context') and 'tenant_id' in kwargs):
            # create a specific auth context for this request
            switchport_req.environ['neutron.context'] = context.Context(
                '', kwargs['tenant_id'])

        switchport_res = switchport_req.get_response(self.ext_api)
        return switchport_res
