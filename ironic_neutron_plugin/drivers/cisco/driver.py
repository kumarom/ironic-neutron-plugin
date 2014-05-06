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

from ironic_neutron_plugin import config
from ironic_neutron_plugin.drivers import base as base_driver
from ironic_neutron_plugin.drivers.cisco import commands

LOG = logging.getLogger(__name__)


class CiscoException(base_driver.DriverException):
    pass


class CiscoDriver(base_driver.Driver):

    def __init__(self):
        self.dry_run = config.get_ironic_config().dry_run
        self.ncclient = None

    def create(self, port):

        LOG.debug("Creating port %s for hardware_id %s"
                  % (port.interface, port.hardware_id))
        LOG.debug("Attaching vlan %s to interface %s"
                  % (port.vlan_id, port.interface))

        cmds = commands.create_port(
            hardware_id=port.hardware_id,
            interface=port.interface,
            vlan_id=port.vlan_id,
            ip=port.ip,
            mac_address=port.mac_address,
            trunked=port.trunked)

        self._run_commands(
            port.switch_ip,
            port.switch_username,
            port.switch_password,
            cmds)

    def delete(self, port):

        LOG.debug("Deleting port %s for hardware_id %s"
                  % (port.interface, port.hardware_id))

        cmds = commands.delete_port(
            interface=port.interface,
            vlan_id=port.vlan_id,
            trunked=port.trunked)

        self.detach(port)
        self._run_commands(
            port.switch_ip,
            port.switch_username,
            port.switch_password,
            cmds)

    def attach(self, port):

        LOG.debug("Attaching vlan %s to interface %s"
                  % (port.vlan_id, port.interface))

        cmds = commands.add_vlan(
            interface=port.interface,
            vlan_id=port.vlan_id,
            ip=port.ip,
            mac_address=port.mac_address,
            trunked=port.trunked)

        self._run_commands(
            port.switch_ip,
            port.switch_username,
            port.switch_password,
            cmds)

    def detach(self, port):

        LOG.debug("Detaching vlan %s from interface %s"
                  % (port.vlan_id, port.interface))

        cmds = commands.remove_vlan(
            interface=port.interface,
            vlan_id=port.vlan_id,
            ip=port.ip,
            mac_address=port.mac_address,
            trunked=port.trunked)

        self._run_commands(
            port.switch_ip,
            port.switch_username,
            port.switch_password,
            cmds)

    def _import_ncclient(self):
        """Import the NETCONF client (ncclient) module.

        The ncclient module is not installed as part of the normal Neutron
        distributions. It is imported dynamically in this module so that
        the import can be mocked, allowing unit testing without requiring
        the installation of ncclient.

        """
        return importutils.import_module('ncclient.manager')

    def _run_commands(self, ip, username, password, commands):

        if self.dry_run:
            LOG.debug("Dry run is enabled, would have "
                      "executed commands: %s" % (commands))
            return

        if not commands:
            LOG.debug("No commands to run")
            return

        conn = self._connect(ip, username, password)
        try:
            LOG.debug("Executing commands: %s" % (commands))

            conn.command(commands)
        except Exception as e:
            raise CiscoException(e)

    def _connect(self, ip, username, password, port=22):
        if not self.ncclient:
            self.ncclient = self._import_ncclient()

        try:
            return self.ncclient.connect(host=ip,
                                         port=port,
                                         username=username,
                                         password=password)
        except Exception as e:
            raise CiscoException(e)
