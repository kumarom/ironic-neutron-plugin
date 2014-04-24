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

from ironic_neutron_plugin.extensions import switch as switch_extension

from neutron import context
from neutron.tests.unit import test_db_plugin

import os
from oslo.config import cfg


PLUGIN_NAME = "ironic_neutron_plugin.plugin.IronicPlugin"

ROOT_DIR = os.path.dirname(os.path.dirname(__file__))
CONFIG_FILE = os.path.join(ROOT_DIR, '../etc/neutron.conf')


class IronicPluginTestCase(test_db_plugin.NeutronDbPluginV2TestCase):

    fmt = 'json'

    def setUp(self):

        extensions_path = os.path.dirname(os.path.realpath(__file__))
        cfg.CONF.set_override(
            "api_extensions_path",
            os.path.join(extensions_path, "../extensions")
        )

        cfg.CONF.set_override(
            "credential_secret", "sixteen byte key", group="ironic"
        )

        ext_mgr = switch_extension.Switch()
        super(IronicPluginTestCase, self).setUp(PLUGIN_NAME,
                                                ext_mgr=ext_mgr)

        self.context = context.get_admin_context()

    def tearDown(self):
        super(IronicPluginTestCase, self).tearDown()

    def _create_default_network(self, name, trunked=True):
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
            "switch:trunked": trunked,
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
