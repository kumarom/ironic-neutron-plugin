from neutron.openstack.common import log as logging

from ironic_neutron_plugin.db import models
from ironic_neutron_plugin.db import db

from ironic_neutron_plugin.drivers.cisco import driver as cisco_driver

LOG = logging.getLogger(__name__)

DRIVER_MAP = {
    models.IronicSwitchType.cisco: cisco_driver.CiscoDriver
}

class DriverException(Exception):
    pass

class DriverManager(object):

    def __init__(self):
        """Instantiate each available driver."""

        self._drivers = {}
        for switch_type, driver_class in DRIVER_MAP.items():
            self._drivers[switch_type] = driver_class()

    def attach(self, network_id, ironic_ports):
        """Realize a neutron port configuration on given physical ports."""

        import pdb; pdb.set_trace()

        network = db.get_network(network_id)
        vlanid = network.segmentation_id

        try:
            for ironic_port in ironic_ports:
                self._drivers[ironic_port.switch.type].attach(vlanid, ironic_port)
        except DriverException as e:
            LOG.error('Failed configuring port', ironic_port.as_dict())
            raise e

    def detach(self, network_id, ironic_ports):
        """Realize a neutron port configuration on given physical ports."""

        network = db.get_network(network_id)
        vlanid = network.segmentation_id

        try:
            for ironic_port in ironic_ports:
                self._drivers[ironic_port.switch.type].detatch(vlanid, ironic_port)
        except DriverException as e:
            LOG.error('Failed configuring port', ironic_port.as_dict())
            raise e