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

DRIVER_MAP = {
    models.IronicSwitchType.cisco: cisco_driver.CiscoDriver
}


class DriverManager(object):

    def __init__(self):
        """Instantiate each available driver."""
        self._drivers = {}
        for switch_type, driver_class in DRIVER_MAP.items():
            self._drivers[switch_type] = driver_class()

    def attach(self, neutron_port, switch_ports, trunked):
        """Realize a neutron port configuration on given physical ports."""
        try:
            for switch_port in switch_ports:
                driver = self._drivers[switch_port.switch.type]
                driver.attach(neutron_port, switch_port, trunked)
                # TODO(morgabra) Handle configuration failure, could
                # potentially end up half-configured on the switch.
                db.create_portbinding(
                    port_id=neutron_port['id'],
                    network_id=neutron_port['network_id'],
                    switch_port_id=switch_port['id'])
        except base_driver.DriverException as e:
            LOG.error('Failed configuring port', switch_port.as_dict())
            raise e

    def detach(self, neutron_port, switch_ports, trunked):
        """Realize a neutron port configuration on given physical ports."""
        try:
            for switch_port in switch_ports:
                driver = self._drivers[switch_port.switch.type]
                driver.detach(neutron_port, switch_port, trunked)
                db.delete_portbinding(
                    port_id=neutron_port['id'],
                    network_id=neutron_port['network_id'],
                    switch_port_id=switch_port['id'])
        except base_driver.DriverException as e:
            LOG.error('Failed configuring port', switch_port.as_dict())
            raise e
