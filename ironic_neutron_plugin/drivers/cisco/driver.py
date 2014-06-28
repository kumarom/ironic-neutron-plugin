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

import re
import time

LOG = logging.getLogger(__name__)

# TODO(morgabra) rethink this, at the very least make this a config
# option. We could probably change it to a global ignore list?
IGNORE_CLEAR = [
    re.compile("no no snmp trap link-status"),
    re.compile("no no lldp transmit"),
    re.compile("no spanning-tree bpduguard enable"),
    re.compile("no channel-group \d+ mode active")
]


class CiscoException(base_driver.DriverException):
    pass


class CiscoDriver(base_driver.Driver):

    def __init__(self, dry_run=None):
        self.dry_run = dry_run
        if dry_run is None:
            self.dry_run = config.cfg.CONF.ironic.dry_run
        self.ncclient = None
        self.connections = {}

    def _filter_interface_conf(self, c):
        """Determine if an interface configuration string is relevant."""
        if c.startswith("!"):
            return False

        if c.startswith("version "):
            return False

        if c.startswith("interface"):
            return False

        if not c:
            return False

        return True

    def _negate_conf(self, c):
        """Negate a line of configuration."""
        return "no %s" % c

    def _get_result(self, res):
        """Get text reponse from an ncclient command.

        Example XML from ncclient:

        <?xml version="1.0" encoding="ISO-8859-1"?>
        <rpc-reply xmlns="urn:ietf:params:xml:ns:netconf:base:1.0"
                   xmlns:if="http://www.cisco.com/nxos:1.0:if_manager"
                   xmlns:nxos="http://www.cisco.com/nxos:1.0"
                   message-id="urn:uuid:4a9be8b4-df85-11e3-ab20-becafe000bed">
          <data>
            !Command: show running-config interface Ethernet1/20
            !Time: Mon May 19 18:40:08 2014

            version 6.0(2)U2(4)

            interface Ethernet1/20
              shutdown
              spanning-tree port type edge
              spanning-tree bpduguard enable

          </data>
        </rpc-reply>

        Example return value:
        ['shutdown',
         'spanning-tree port type edge',
         'spanning-tree bpduguard enable']
        """
        if not res:
            return []

        # get the first child from the xml response
        res = res._root.getchildren()
        if len(res) != 1:
            raise Exception("cannot parse command response")

        # split the raw text by newline
        text = res[0].text
        if not text:
            return []

        res = text.split("\n")

        # filter comments and other unrelated data
        return [c.strip() for c in res if self._filter_interface_conf(c)]

    def show(self, port, type="ethernet"):
        LOG.debug("Fetching interface %s" % (port.interface))

        eth_int = commands._make_ethernet_interface(port.interface)
        cmds = commands.show_interface_configuration(type, eth_int)

        result = self._run_commands(port, cmds)
        return self._get_result(result)

    def show_dhcp_snooping_configuration(self, port):
        LOG.debug("Fetching dhcp snooping entries for int %s" % port.interface)

        po_int = commands._make_portchannel_interface(port.interface)
        cmds = commands.show_dhcp_snooping_configuration(po_int)

        result = self._run_commands(port, cmds)
        return self._get_result(result)

    def clear(self, port):
        """Remove all configuration for a given interface, which includes
        the ethernet interface, related port-channel, and any dhcp snooping
        bindings or other port security features.

        For some reason, you can't run 'no interface eth x/x' on
        the 3172. So we have to read the config for the interface first
        and manually negate each option.

        'no interface port-channel' works as expected.

        You must remove entries from the dhcp snooping table before removing
        the underlying port-channel otherwise it won't work.
        """
        LOG.debug("clearing interface %s" % (port.interface))

        interface = port.interface
        po_int = commands._make_portchannel_interface(interface)
        eth_int = commands._make_ethernet_interface(interface)

        eth_conf = self.show(port, type='ethernet')
        eth_conf = [self._negate_conf(c) for c in eth_conf]

        dhcp_conf = self.show_dhcp_snooping_configuration(port)
        dhcp_conf = [self._negate_conf(c) for c in dhcp_conf]

        cmds = commands._configure_interface('port-channel', po_int)
        cmds = cmds + dhcp_conf
        cmds = cmds + commands._delete_port_channel_interface(po_int)
        cmds = cmds + commands._configure_interface('ethernet', eth_int)
        cmds = cmds + eth_conf + ['shutdown']

        def _filter_clear_commands(c):
            for r in IGNORE_CLEAR:
                if r.match(c):
                    return False
            return True

        cmds = [c for c in cmds if _filter_clear_commands(c)]

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
                try:
                    c.close_session()
                except Exception as e:
                    LOG.debug("Failed closing session: %s" % c.session_id)
                self.connections[port.switch_host] = None

            raise CiscoException(e)

    def _run_commands(self, port, commands):
        num_tries = 0
        max_tries = 1 + config.cfg.CONF.ironic.auth_failure_retries
        sleep_time = config.cfg.CONF.ironic.auth_failure_retry_interval
        while True:
            num_tries += 1
            try:
                return self._run_commands_inner(port, commands)
            except CiscoException as err:
                if ('authorization failed' not in str(err) or
                        num_tries == max_tries):
                    raise
                LOG.warning("Received authorization failure, will retry: "
                            "%s" % err)
            time.sleep(sleep_time)
