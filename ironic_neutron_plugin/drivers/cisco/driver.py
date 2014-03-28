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

from ironic_neutron_plugin.drivers.cisco import commands
from ironic_neutron_plugin.drivers import base as base_driver
from ironic_neutron_plugin.db import db

LOG = logging.getLogger(__name__)

class CiscoException(base_driver.DriverException):
    pass

class CiscoDriver(base_driver.Driver):

    def __init__(self):
        self.ncclient = None

    def _get_vlan_id(self, neutron_port):
        network_id = neutron_port['network_id']
        network = db.get_network(network_id)
        return network.segmentation_id

    def _get_ip(self, neutron_port):
        ips = neutron_port['fixed_ips']
        if len(ips) != 1:
            raise CiscoException('More than 1 IP assigned to port %s, bailing out.' % (neutron_port['id']))
        return ips[0]['ip_address']

    def _get_port_bindings(self, switch_port):
        # get existing port bindings
        return list(db.filter_portbindings(switch_port_id=switch_port['id']))

    def attach(self, neutron_port, switch_port, trunked):

        vlan_id = self._get_vlan_id(neutron_port)
        ip = self._get_ip(neutron_port)

        # TODO(morgabra) We should move this logic out to the manager probably, and
        #                have drivers implement create() and attach()/detach() separately.
        port_bindings = self._get_port_bindings(switch_port)

        if not len(port_bindings):
            LOG.debug('No existing bindings, creating new configuration')
            self._run_commands(switch_port, commands.create_port(
                device_id=switch_port['device_id'],
                interface=switch_port['port'],
                vlan_id=vlan_id,
                ip=ip,
                mac_address=neutron_port['mac_address'],
                trunked=trunked))
        else:
            LOG.debug('Existing bindings, adding vlan')
            self._run_commands(switch_port, commands.add_vlan(
                interface=switch_port['port'],
                vlan_id=vlan_id,
                ip=ip,
                mac_address=neutron_port['mac_address'],
                trunked=trunked))

    def detach(self, neutron_port, switch_port, trunked):
        vlan_id = self._get_vlan_id(neutron_port)
        ip = self._get_ip(neutron_port)

        port_bindings = self._get_port_bindings(switch_port)

        try:
            if not len(port_bindings):
                msg = 'No portbindings found for given port, doing nothing...'
                LOG.error(msg)
                return

            self._run_commands(switch_port, commands.remove_vlan(
                interface=switch_port['port'],
                vlan_id=vlan_id,
                ip=ip,
                mac_address=neutron_port['mac_address'],
                trunked=trunked))

            if len(port_bindings) == 1:
                LOG.debug('Last binding for port, shutting down ports...')
                self._run_commands(switch_port, commands.delete_port(
                    interface=switch_port['port'],
                    vlan_id=vlan_id,
                    trunked=trunked))

        except CiscoException as e:
            #TODO(morgabra) We can ignore some classes of errors, but not all
            LOG.error("Failed detatch!")
            LOG.error(e)

    def _import_ncclient(self):
        """Import the NETCONF client (ncclient) module.

        The ncclient module is not installed as part of the normal Neutron
        distributions. It is imported dynamically in this module so that
        the import can be mocked, allowing unit testing without requiring
        the installation of ncclient.

        """
        return importutils.import_module('ncclient.manager')

    def _run_commands(self, switch_port, commands):

        #conn = self._connect(switch_port.switch)
        try:
            LOG.debug("Executing commands: %s" % (commands))

            #conn.command(commands)
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
