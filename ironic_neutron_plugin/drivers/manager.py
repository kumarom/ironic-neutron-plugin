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

from ironic_neutron_plugin.db import db
from ironic_neutron_plugin.db import models

from ironic_neutron_plugin.drivers import base as base_driver
from ironic_neutron_plugin.drivers.cisco import driver as cisco_driver

from neutron.openstack.common import log as logging

LOG = logging.getLogger(__name__)

# TODO(morgabra) proper driver loading mechanism
DRIVER_MAP = {
    'cisco': cisco_driver.CiscoDriver,
    'dummy': base_driver.DummyDriver
}


class DriverManager(object):

    def __init__(self):
        """Instantiate each available driver."""
        self._drivers = {}
        for switch_type, driver_class in DRIVER_MAP.items():
            self._drivers[switch_type] = driver_class()

    def _get_driver(self, ironic_switch_port):
        return self._drivers[ironic_switch_port.switch.type]

    def _get_vlan_id(self, ironic_network):
        return ironic_network.segmentation_id

    def _get_ip(self, neutron_port):
        ips = neutron_port['fixed_ips']
        if len(ips) == 0:
            return None
        elif len(ips) > 1:
            raise base_driver.DriverException(
                ('More than 1 fixed_ip assigned to port %s'
                 % (neutron_port['id'])))
        else:
            return ips[0]['ip_address']

    def _get_switchports(self, neutron_port):
        switchports = neutron_port.get("switch:ports", [])
        switchport_ids = [sp["id"] for sp in switchports]

        return list(db.get_switchports_by_ids(switchport_ids))

    def _get_switchports_by_ids(self, ids):
        return list(db.get_switchports_by_ids(ids))

    def _get_portbindings(self, switch_port):
        return list(db.filter_switchport_bindings(
            switch_port_id=switch_port['id']))

    def _get_portbinding(self, neutron_port, switch_port):
        return db.get_switchport_binding(
            port_id=neutron_port['id'],
            network_id=neutron_port['network_id'],
            switch_port_id=switch_port['id'])

    def _create_portbinding(self, neutron_port, switch_port):
        return db.create_switchport_binding(
            port_id=neutron_port['id'],
            network_id=neutron_port['network_id'],
            switch_port_id=switch_port['id'])

    def _delete_portbinding(self, neutron_port, switch_port):
        return db.delete_switchport_binding(
            port_id=neutron_port['id'],
            network_id=neutron_port['network_id'],
            switch_port_id=switch_port['id'])

    def _set_portbinding_state(self, ironic_portbinding, state):
        db.update_switchport_binding_state(
            port_id=ironic_portbinding.port_id,
            network_id=ironic_portbinding.network_id,
            switch_port_id=ironic_portbinding.switch_port_id,
            state=state)

    def _make_port_info(self, switch_port, neutron_port=None,
                        neutron_network=None):
        info = base_driver.PortInfo(
            switch_host=switch_port.switch.host,
            switch_username=switch_port.switch.username,
            switch_password=switch_port.switch.password,
            interface=switch_port["port"]
        )

        if neutron_port:
            info.hardware_id = neutron_port["switch:hardware_id"]
            info.ip = self._get_ip(neutron_port)
            info.mac_address = neutron_port["mac_address"]
            info.trunked = neutron_port["trunked"]

        if neutron_network:
            info.vlan_id = neutron_network["provider:segmentation_id"]

        return info

    def running_config(self, switch_port_id):
        """Given a switch_port_id, look up and return relevant
        configuration info from the underlying device.
        """
        # TODO(morgabra) db.get_switchport_by_id()
        switch_ports = self._get_switchports_by_ids([switch_port_id])
        if not switch_ports:
            return {}
        switch_port = switch_ports[0]

        # get and return response from driver
        # TODO(morgabra) standardize response?
        port_info = self._make_port_info(switch_port)
        driver = self._get_driver(switch_port)
        return driver.running_config(port_info)

    def interface_status(self, switch_port_id):
        """Given a switch_port_id, look up and return relevant
        status info from the underlying interface.
        """
        # TODO(morgabra) db.get_switchport_by_id()
        switch_ports = self._get_switchports_by_ids([switch_port_id])
        if not switch_ports:
            return {}
        switch_port = switch_ports[0]

        # get and return response from driver
        # TODO(morgabra) standardize response?
        port_info = self._make_port_info(switch_port)
        driver = self._get_driver(switch_port)
        return driver.interface_status(port_info)

    def attach(self, neutron_port, neutron_network):
        """Realize a neutron port configuration on given physical ports.

        We can't just wrap this in a database transaction because we'll have
        to manually recover the switch configurations if we fail.
        """
        switchports = self._get_switchports(neutron_port)

        try:
            if not switchports:
                msg = ('Cannot attach, no given switchports '
                       'for port %s' % neutron_port["id"])
                LOG.error(msg)
                raise base_driver.DriverException(msg)

            if not neutron_port["trunked"]:
                # TODO(morgabra) There should be a mechanism for picking
                # which switchport to configure - maybe by name?
                pass

            for switchport in switchports:

                portbindings = self._get_portbindings(switchport)
                new_portbinding = self._create_portbinding(
                    neutron_port, switchport)
                self._set_portbinding_state(
                    new_portbinding, models.SwitchPortBindingState.WANT_ACTIVE)

                driver = self._get_driver(switchport)
                port_info = self._make_port_info(
                    switch_port=switchport,
                    neutron_port=neutron_port,
                    neutron_network=neutron_network
                )

                if portbindings:
                    driver.attach(port_info)
                else:
                    driver.create(port_info)

                self._set_portbinding_state(
                    new_portbinding, models.SwitchPortBindingState.ACTIVE)

        except Exception as e:
            for switchport in switchports:
                self._delete_portbinding(neutron_port, switchport)
            LOG.error('Failed configuring port: %s', e)
            raise e

    def detach(self, neutron_port, neutron_network):
        """Realize a neutron port configuration on given physical ports."""
        switchports = self._get_switchports(neutron_port)

        try:
            if not switchports:
                msg = ('Cannot detach, no given switchports '
                       'for port %s' % neutron_port["id"])
                LOG.error(msg)
                raise base_driver.DriverException(msg)

            for switchport in switchports:

                portbindings = self._get_portbindings(switchport)

                # find relevant portbinding and set state to deleting
                active_portbinding = self._get_portbinding(
                    neutron_port, switchport)

                if not active_portbinding:
                    msg = ("No relevant portbinding found for port %s, "
                           "skipping detach()" % (neutron_port['id']))
                    LOG.error(msg)
                    continue

                self._set_portbinding_state(
                    active_portbinding,
                    models.SwitchPortBindingState.WANT_INACTIVE)

                driver = self._get_driver(switchport)
                port_info = self._make_port_info(
                    switch_port=switchport,
                    neutron_port=neutron_port,
                    neutron_network=neutron_network
                )

                if len(portbindings) == 1:
                    driver.delete(port_info)
                else:
                    driver.detach(port_info)

                self._delete_portbinding(neutron_port, switchport)

        except Exception as e:
            for switchport in switchports:
                self._delete_portbinding(neutron_port, switchport)
            LOG.error('Failed configuring port: %s', e)
            raise e
