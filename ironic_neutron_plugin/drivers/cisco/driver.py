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

"""
Implements a Nexus-OS NETCONF over SSHv2 API Client.

This is lifted partially from the cisco ml2 mechanism.
"""
from ironic_neutron_plugin import config

from neutron.common import utils
from neutron.openstack.common import importutils
from neutron.openstack.common import log as logging

from ironic_neutron_plugin.drivers import base as base_driver
from ironic_neutron_plugin.drivers.cisco import commands
from ironic_neutron_plugin.drivers.cisco import utils as cisco_utils

import time

LOG = logging.getLogger(__name__)


class CiscoException(base_driver.DriverException):
    pass


class CiscoDriver(base_driver.Driver):

    def __init__(self, dry_run=None):
        self.dry_run = dry_run
        if dry_run is None:
            self.dry_run = config.cfg.CONF.ironic.dry_run
        self.ncclient = None
        self.connections = {}

    def show_interface(self, port, type="ethernet"):
        LOG.debug("Fetching interface %s %s" % (type, port.interface))

        cmds = commands.show_interface(type, port.interface)

        result = self._run_commands(port, cmds)
        return cisco_utils.parse_interface_status(result)

    def show_interface_configuration(self, port, type="ethernet"):
        LOG.debug("Fetching interface %s %s" % (type, port.interface))

        cmds = commands.show_interface_configuration(type, port.interface)

        result = self._run_commands(port, cmds)
        return cisco_utils.parse_command_result(result)

    def show_dhcp_snooping_configuration(self, port):
        LOG.debug("Fetching dhcp snooping entries for int %s" % port.interface)

        po_int = commands._make_portchannel_interface(port.interface)
        cmds = commands.show_dhcp_snooping_configuration(po_int)

        result = self._run_commands(port, cmds)
        return cisco_utils.parse_command_result(result)

    def clear(self, port):
        """Remove all configuration for a given interface, which includes
        the ethernet interface, related port-channel, and any dhcp snooping
        bindings or other port security features.
        """
        LOG.debug("clearing interface %s" % (port.interface))

        interface = port.interface
        po_int = commands._make_portchannel_interface(interface)
        eth_int = commands._make_ethernet_interface(interface)

        # get and filter relevant dhcp snooping bindings
        dhcp_conf = self.show_dhcp_snooping_configuration(port)
        dhcp_conf = [cisco_utils.negate_conf(c) for c in dhcp_conf]

        # we need to configure the portchannel because there is no
        # guarantee that it exists, and you cannot remove snooping
        # bindings without the actual interface existing.
        cmds = []
        if dhcp_conf:
            cmds = cmds + commands._configure_interface('port-channel', po_int)
            cmds = cmds + dhcp_conf

        # delete the portchannel and default the eth interface
        cmds = cmds + commands._delete_port_channel_interface(po_int)
        cmds = cmds + commands._delete_ethernet_interface(eth_int)

        return self._run_commands(port, cmds)

    def create(self, port):
        self.clear(port)

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

        return self._run_commands(port, cmds)

    def delete(self, port):
        LOG.debug("Deleting port %s for hardware_id %s"
                  % (port.interface, port.hardware_id))
        return self.clear(port)

    def attach(self, port):
        LOG.debug("Attaching vlan %s to interface %s"
                  % (port.vlan_id, port.interface))

        cmds = commands.add_vlan(
            interface=port.interface,
            vlan_id=port.vlan_id,
            ip=port.ip,
            mac_address=port.mac_address,
            trunked=port.trunked)

        return self._run_commands(port, cmds)

    def detach(self, port):
        LOG.debug("Detaching vlan %s from interface %s"
                  % (port.vlan_id, port.interface))

        cmds = commands.remove_vlan(
            interface=port.interface,
            vlan_id=port.vlan_id,
            ip=port.ip,
            mac_address=port.mac_address,
            trunked=port.trunked)

        self._run_commands(port, cmds)

        # TODO(morgbara) this is not ideal, but we don't want
        # to fail an vlan removal if the ip binding doesn't exist,
        # and there really isn't a way to do this safely without
        # checking for it (which takes time). This will be a little
        # better when we differenciate between types of failures when
        # talking to a switch better.
        cmds = commands.unbind_ip(
            interface=port.interface,
            vlan_id=port.vlan_id,
            ip=port.ip,
            mac_address=port.mac_address,
            trunked=port.trunked
        )

        try:
            return self._run_commands(port, cmds)
        except CiscoException as e:
            LOG.info("Failed to remove ip binding: %s" % str(e))
            return None

    def running_config(self, port):
        LOG.debug("Fetching running-config %s" % (port.interface))

        switch = {
            "interface": port.interface,
            "hostname": port.switch_host
        }

        running_config = {}

        running_config['dhcp'] = self.show_dhcp_snooping_configuration(port)

        running_config['ethernet'] = self.show_interface_configuration(
            port, type="ethernet")

        # a port-channel might not be defined
        try:
            running_config['port-channel'] = self.show_interface_configuration(
                port, type="port-channel")
        except CiscoException as e:
            if ('syntax error' in str(e).lower()):
                running_config['port-channel'] = ['no port-channel']
            else:
                raise e

        return {
            "switch": switch,
            "running-config": running_config
        }

    def interface_status(self, port):
        LOG.debug("Fetching interface status %s" % (port.interface))

        switch = {
            "interface": port.interface,
            "hostname": port.switch_host
        }

        status = {}
        status['ethernet'] = self.show_interface(
            port, type="ethernet")

        # a port-channel might not be defined
        try:
            status['port-channel'] = self.show_interface(
                port, type="port-channel")
        except CiscoException as e:
            if ('syntax error' in str(e).lower()):
                status['port-channel'] = ['no port-channel']
            else:
                raise e

        return {
            "switch": switch,
            "interface-status": status
        }

    def _import_ncclient(self):
        """Import the NETCONF client (ncclient) module.

        The ncclient module is not installed as part of the normal Neutron
        distributions. It is imported dynamically in this module so that
        the import can be mocked, allowing unit testing without requiring
        the installation of ncclient.
        """
        return importutils.import_module('ncclient.manager')

    @utils.synchronized('ironic-cisco-driver')
    def _connect(self, port):
        c = self.connections.get(port.switch_host)

        # TODO(morgabra) connected is updated from a thread, so obviously
        # there are some issues with checking this here.
        if not c or not c.connected:
            LOG.debug("starting session: %s" % (port.switch_host))
            connect_args = {
                "host": port.switch_host,
                "port": 22,  # TODO(morgabra) configurable
                "username": port.switch_username,
                "password": port.switch_password,
                "timeout": 10  # TOOD(morgabra) configurable
            }
            c = self.ncclient.connect(**connect_args)
            self.connections[port.switch_host] = c

        LOG.debug("got session: %s" % (c.session_id))

        return c

    def _run_commands_inner(self, port, commands):

        if not commands:
            LOG.debug("No commands to run")
            return

        LOG.debug("executing commands: %s" % (commands))

        if self.dry_run:
            LOG.debug("Dry run is enabled, skipping")
            return None

        if not self.ncclient:
            self.ncclient = self._import_ncclient()

        c = None
        try:
            c = self._connect(port)
            return c.command(commands)
        except Exception as e:
            # TODO(morgabra) Tell the difference between a connection error and
            # and a config error. We don't need to clear the current connection
            # for latter.
            LOG.debug("Failed running commands: %s" % e)
            if c:
                self.connections[port.switch_host] = None
                try:
                    c.close_session()
                except Exception as err:
                    LOG.debug("Failed closing session %(sess)s: %(e)s",
                              {'sess': c.session_id, 'e': err})

            raise CiscoException(e)

    def _run_commands(self, port, commands):
        num_tries = 0
        max_tries = 1 + config.cfg.CONF.ironic.auth_failure_retries
        sleep_time = config.cfg.CONF.ironic.auth_failure_retry_interval

        retryable_errors = ['authorization failed',
                            'Permission denied',
                            'Not connected to NETCONF server']

        def retryable_error(err):
            for retry_err in retryable_errors:
                if retry_err in err:
                    return True
            return False

        while True:
            num_tries += 1
            try:
                return self._run_commands_inner(port, commands)
            except CiscoException as err:
                if (num_tries == max_tries or not retryable_error(str(err))):
                    raise
                LOG.warning("Received retryable failure: %s" % err)
            time.sleep(sleep_time)
