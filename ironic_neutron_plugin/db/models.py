import sqlalchemy as sa
from sqlalchemy import orm as sa_orm

from neutron.db import model_base
from neutron.openstack.common import log as logging

LOG = logging.getLogger(__name__)

class IronicSwitchPort(model_base.BASEV2):
    """Maps a device to a physical switch port."""

    __tablename__ = "ironic_switch_ports"

    id = sa.Column(sa.Integer, primary_key=True, autoincrement=True)

    switch_id = sa.Column(sa.Integer, sa.ForeignKey('ironic_switches.id'))
    device_id = sa.Column(sa.String(255), index=True)  # ironic chassis id
    port = sa.Column(sa.String(255))  # switch port number: <1-n>

    def as_dict(self):
        return {
            'id': self.id,
            'switch_id': self.switch_id,
            'device_id': self.device_id,
            'port': self.port
        }

class IronicSwitchType(object):

    cisco = 'cisco'
    arista = 'arista'

    @classmethod
    def as_dict(cls):
        return {
            'cisco': cls.cisco,
            'arista': cls.arista
        }

class IronicSwitch(model_base.BASEV2):
    """A physical switch and admin credentials."""

    __tablename__ = "ironic_switches"

    id = sa.Column(sa.Integer, primary_key=True, autoincrement=True)

    ip = sa.Column(sa.String(255))
    username = sa.Column(sa.String(255))
    password = sa.Column(sa.String(255))

    # TODO(morgabra) validation
    type = sa.Column(sa.String(255))
    switch_ports = sa_orm.relationship('IronicSwitchPort', cascade='all,delete', backref='switch')

    def as_dict(self):
        return {
            'id': self.id,
            'ip': self.ip,
            'username': self.username,
            'password': '******',
            'type': self.type
        }

class IronicNetwork(model_base.BASEV2):
    """Keep track of vlans via 'provider' API extension"""

    __tablename__ = "ironic_networks"

    network_id = sa.Column(sa.String(255), primary_key=True)
    physical_network = sa.Column(sa.String(255))
    segmentation_id = sa.Column(sa.Integer)
    network_type = sa.Column(sa.String(255))

    def as_dict(self):
        return {
            "provider:physical_network": self.physical_network,
            "provider:segmentation_id": self.segmentation_id,
            "provider:network_type": self.network_type,

        }

class IronicPortBinding(model_base.BASEV2):
    """Keep track of active switch configurations.

    TODO(morgabra) This keeps switch config state in neutron. In general, if there is an entry here then
    the configuration is running on the switch. There are many problems with this plan.

    TODO(morgabra) Ideally we implement config validation and purge/sync utilities which should let us get
    away without keeping any state?"""

    __tablename__ = "ironic_port_bindings"

    # TODO(morgabra) This is confusing, port_id is a neutron port
    port_id = sa.Column(sa.String(255), primary_key=True)
    switch_port_id = sa.Column(sa.Integer, sa.ForeignKey('ironic_switch_ports.id'), primary_key=True)

    def as_dict(self):
        return {
            "port_id": self.port_id,
            "switch_port_id": self.switch_port_id
        }
