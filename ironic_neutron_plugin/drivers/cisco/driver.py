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

"""
Implements a Nexus-OS NETCONF over SSHv2 API Client.

This is lifted partially from the cisco ml2 mechanism.
"""
from neutron.openstack.common import importutils
from neutron.openstack.common import log as logging

from ironic_neutron_plugin.drivers.cisco import nexus_snippets as snipp
from ironic_neutron_plugin.drivers import base as base_driver
from ironic_neutron_plugin.db import db

LOG = logging.getLogger(__name__)

class CiscoException(Exception):
    pass

class CiscoDriver(base_driver.Driver):

    def __init__(self):
        self.ncclient = None

    def attach(self, vlanid, switch_port):
        self.enable_vlan_on_trunk_int(vlanid, switch_port)

    def detatch(self, vlanid, switch_port):
        self.disable_vlan_on_trunk_int(vlanid, switch_port)

    def _import_ncclient(self):
        """Import the NETCONF client (ncclient) module.

        The ncclient module is not installed as part of the normal Neutron
        distributions. It is imported dynamically in this module so that
        the import can be mocked, allowing unit testing without requiring
        the installation of ncclient.

        """
        return importutils.import_module('ncclient.manager')

    def _edit_config(self, switch_port, target='running', config=''):

        conn = self._connect(switch_port.switch)
        try:
            conn.edit_config(target, config=config)
        except Exception as e:
            raise CiscoException(e)

    def _connect(self, switch):
        if not self.ncclient:
            self.ncclient = self._import_ncclient()

        host = switch.ip
        port = 22  # TODO(morgabra) Add to switch model
        username = switch.username
        password = switch.password
        try:
            return self.ncclient.connect(host=host,
                                         port=port,
                                         username=username,
                                         password=password)
        except Exception as e:
            raise CiscoException(e)

    def create_xml_snippet(self, customized_config):
        conf_xml_snippet = snipp.EXEC_CONF_SNIPPET % (customized_config)
        return conf_xml_snippet

    def enable_vlan_on_trunk_int(self, vlanid, switch_port):
        """Enable a VLAN on a trunk interface."""

        if len(list(db.filter_portbindings(switch_port_id=switch_port.id))) == 1:
            snippet = snipp.CMD_INT_VLAN_SNIPPET
        else:
            snippet = snipp.CMD_INT_VLAN_ADD_SNIPPET

        snippet = snipp.CMD_INT_VLAN_ADD_SNIPPET
        confstr = snippet % (switch_port.port, vlanid)
        confstr = self.create_xml_snippet(confstr)
        LOG.debug("NexusDriver: %s", confstr)
        self._edit_config(switch_port, target='running', config=confstr)

    def disable_vlan_on_trunk_int(self, vlanid, switch_port):
        """Disable a VLAN on a trunk interface."""
        confstr = snipp.CMD_NO_VLAN_INT_SNIPPET % (switch_port.port, vlanid)
        confstr = self.create_xml_snippet(confstr)
        LOG.debug("NexusDriver: %s", confstr)
        self._edit_config(switch_port, target='running', config=confstr)
