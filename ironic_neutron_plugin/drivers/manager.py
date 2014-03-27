from neutron.openstack.common import log as logging

from ironic_neutron_plugin.db import models

from ironic_neutron_plugin.drivers import base as base_driver
from ironic_neutron_plugin.drivers.cisco import driver as cisco_driver
from ironic_neutron_plugin.db import db

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

    def attach(self, neutron_port, switch_ports):
        """Realize a neutron port configuration on given physical ports."""
        try:
            for switch_port in switch_ports:
                self._drivers[switch_port.switch.type].attach(neutron_port, switch_port)
                #TODO(morgabra) Create the portbinding first, but maybe in a disable/unconfigured state, and update the flag post config.
                #               We need to do that because there are some config options that can't be cleared without relevant information
                db.create_portbinding(
                    port_id=neutron_port['id'],
                    switch_port_id=switch_port['id'])
        except base_driver.DriverException as e:
            LOG.error('Failed configuring port', switch_port.as_dict())
            raise e

    def detach(self, neutron_port, switch_ports):
        """Realize a neutron port configuration on given physical ports."""
        try:
            for switch_port in switch_ports:
                self._drivers[switch_port.switch.type].detach(neutron_port, switch_port)
                db.delete_portbinding(
                    port_id=neutron_port['id'],
                    switch_port_id=switch_port['id'])
        except base_driver.DriverException as e:
            LOG.error('Failed configuring port', switch_port.as_dict())
            raise e