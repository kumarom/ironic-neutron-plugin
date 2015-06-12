import logging as py_logging
from neutron.openstack.common import log as logging
logging.setup("swtich")

# TODO(morgbara) figure out how to use a config file for this
LOG = logging.getLogger('baremetal_neutron_extension.drivers.cisco.driver')
LOG.logger.setLevel(py_logging.DEBUG)

from baremetal_neutron_extension.drivers import base
from baremetal_neutron_extension.drivers.cisco import driver as cisco_driver


def create_port(port, driver):
    driver.create(port)


def delete_port(port, driver):
    driver.delete(port)


def add_vlan(port, driver):
    driver.attach(port)


def remove_vlan(port, driver):
    driver.detach(port)


def show(port, driver):
    driver.show(port)


def clear(port, driver):
    driver.clear(port)

d = cisco_driver.CiscoDriver(dry_run=True)
p = base.PortInfo(
    switch_host='host',
    switch_username='user',
    switch_password='pass',
    hardware_id='hardware_id',
    interface='Eth1/20',
    vlan_id='101',
    ip='10.0.0.1',
    mac_address='aa:bb:cc:dd:ee',
    trunked=True)

clear(p, d)
