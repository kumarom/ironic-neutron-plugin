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

from ironic_neutron_plugin.db import db
from ironic_neutron_plugin.db import models

from ironic_neutron_plugin.drivers import base as base_driver
from ironic_neutron_plugin.drivers.cisco import driver as cisco_driver

from neutron.openstack.common import log as logging

LOG = logging.getLogger(__name__)

# TODO(morgabra) proper driver loading mechanism
DRIVER_MAP = {
    models.IronicSwitchType.cisco: cisco_driver.CiscoDriver,
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
        if len(ips) != 1:
            raise base_driver.DriverException(
                ('More than 1 IP assigned to port %s'
                 % (neutron_port['id'])))
        return ips[0]['ip_address']

    def _get_portbindings(self, ironic_switch_port):
        return list(db.filter_portbindings(
            switch_port_id=ironic_switch_port['id']))

    def _get_portbinding(self, neutron_port, ironic_switch_port):
        return db.get_portbinding(
            port_id=neutron_port['id'],
            network_id=neutron_port['network_id'],
            switch_port_id=ironic_switch_port['id'])

    def _create_portbinding(self, neutron_port, ironic_switch_port):
        return db.create_portbinding(
            port_id=neutron_port['id'],
            network_id=neutron_port['network_id'],
            switch_port_id=ironic_switch_port['id'])

    def _delete_portbinding(self, neutron_port, ironic_switch_port):
        return db.delete_portbinding(
            port_id=neutron_port['id'],
            network_id=neutron_port['network_id'],
            switch_port_id=ironic_switch_port['id'])

    def _set_portbinding_active(self, ironic_portbinding):
        db.update_portbinding_state(
            port_id=ironic_portbinding.port_id,
            network_id=ironic_portbinding.network_id,
            switch_port_id=ironic_portbinding.switch_port_id,
            state=models.IronicPortBindingState.ACTIVE)

    def _set_portbinding_deleting(self, ironic_portbinding):
        db.update_portbinding_state(
            port_id=ironic_portbinding.port_id,
            network_id=ironic_portbinding.network_id,
            switch_port_id=ironic_portbinding.switch_port_id,
            state=models.IronicPortBindingState.DELETED)

    def _make_port_info(self, neutron_port,
                        ironic_network, ironic_switch_port):
        return base_driver.PortInfo(
            switch_ip=ironic_switch_port.switch.ip,
            switch_username=ironic_switch_port.switch.username,
            switch_password=ironic_switch_port.switch.password,
            device_id=neutron_port["device_id"],
            interface=ironic_switch_port["port"],
            vlan_id=ironic_network.segmentation_id,
            ip=self._get_ip(neutron_port),
            mac_address=neutron_port["mac_address"],
            trunked=ironic_network.trunked
        )

    def attach(self, neutron_port, ironic_network, ironic_switch_ports):
        """Realize a neutron port configuration on given physical ports."""

        try:
            for ironic_switch_port in ironic_switch_ports:

                portbindings = self._get_portbindings(ironic_switch_port)
                new_portbinding = self._create_portbinding(
                    neutron_port, ironic_switch_port)

                driver = self._get_driver(ironic_switch_port)
                port_info = self._make_port_info(
                    neutron_port, ironic_network, ironic_switch_port)

                if portbindings:
                    driver.attach(port_info)
                else:
                    driver.create(port_info)

                self._set_portbinding_active(new_portbinding)
            return True
        except base_driver.DriverException as e:
            LOG.error('Failed configuring port: %s', e)
            return False

    def detach(self, neutron_port, ironic_network, ironic_switch_ports):
        """Realize a neutron port configuration on given physical ports."""
        try:
            for ironic_switch_port in ironic_switch_ports:

                portbindings = self._get_portbindings(ironic_switch_port)

                # find relevant portbinding and set state to deleting
                active_portbinding = self._get_portbinding(
                    neutron_port, ironic_switch_port)

                if not active_portbinding:
                    msg = ("No relevant portbinding found for port %s, "
                           "skipping detach()" % (neutron_port['id']))
                    LOG.error(msg)
                    raise base_driver.DriverException(msg)

                self._set_portbinding_deleting(active_portbinding)

                driver = self._get_driver(ironic_switch_port)
                port_info = self._make_port_info(
                    neutron_port, ironic_network, ironic_switch_port)

                if len(portbindings) == 1:
                    driver.delete(port_info)
                else:
                    driver.detach(port_info)

                self._delete_portbinding(neutron_port, ironic_switch_port)

            return True
        except base_driver.DriverException as e:
            LOG.error('Failed configuring port: %s', e)
            return False
