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

import sqlalchemy as sa
from sqlalchemy import orm as sa_orm

from neutron.db import model_base
from neutron.openstack.common import log as logging

LOG = logging.getLogger(__name__)


class IronicSwitchPort(model_base.BASEV2):
    """Maps a device to a physical switch port."""

    __tablename__ = "ironic_switch_ports"

    id = sa.Column(sa.Integer, primary_key=True, autoincrement=True)

    switch_id = sa.Column(sa.Integer, sa.ForeignKey("ironic_switches.id"))
    # ironic chassis id
    device_id = sa.Column(sa.String(255), index=True)
    # switch port number: <1-n>
    port = sa.Column(sa.String(255))
    # for non-trunked networks, only this port will be configured
    primary = sa.Column(sa.Boolean)

    def as_dict(self):
        return {
            "id": self.id,
            "switch_id": self.switch_id,
            "device_id": self.device_id,
            "port": self.port,
            "primary": self.primary
        }


class IronicSwitchType(object):

    cisco = "cisco"
    arista = "arista"

    @classmethod
    def as_dict(cls):
        return {
            "cisco": cls.cisco,
            "arista": cls.arista
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
    switch_ports = sa_orm.relationship(
        "IronicSwitchPort", cascade="all,delete", backref="switch")

    def as_dict(self):
        return {
            "id": self.id,
            "ip": self.ip,
            "username": self.username,
            "password": '******',
            "type": self.type
        }


class IronicNetwork(model_base.BASEV2):
    """Keep track of vlans via 'provider' API extension."""

    __tablename__ = "ironic_networks"

    network_id = sa.Column(sa.String(255), primary_key=True)
    physical_network = sa.Column(sa.String(255))
    segmentation_id = sa.Column(sa.Integer)
    network_type = sa.Column(sa.String(255))
    # TODO(morgbara) is this the best place to store this information?
    trunked = sa.Column(sa.Boolean)

    def as_dict(self):
        return {
            "provider:physical_network": self.physical_network,
            "provider:segmentation_id": self.segmentation_id,
            "provider:network_type": self.network_type,
            "switch:trunked": self.trunked
        }


class IronicPortBindingState(object):
    """PortBinding states:

    CREATED: Configuration is not active on the switch
             but we want it to be
    ACTIVE: Configuration is running on the switch
    DELETED: Configuration is running on the switch
             but we want it removed
    """
    CREATED = 'CREATED'
    ACTIVE = 'ACTIVE'
    DELETED = 'DELETED'


class IronicPortBinding(model_base.BASEV2):
    """Keep track of active switch configurations.

    TODO(morgabra) We should be able to figure out how to
    recover a failed binding based on the portbinding state.
    We still need to write that recovery code/scripts.
    """

    __tablename__ = "ironic_port_bindings"

    # TODO(morgabra) This is confusing, port_id is a neutron port
    port_id = sa.Column(sa.String(255), primary_key=True)
    network_id = sa.Column(sa.String(255), primary_key=True)
    switch_port_id = sa.Column(
        sa.Integer, sa.ForeignKey("ironic_switch_ports.id"), primary_key=True)
    state = sa.Column(sa.String(255), default=IronicPortBindingState.CREATED)

    def as_dict(self):
        return {
            "port_id": self.port_id,
            "network_id": self.network_id,
            "switch_port_id": self.switch_port_id,
            "state": self.state
        }
