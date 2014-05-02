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

from Crypto.Cipher import AES
from Crypto import Random

from ironic_neutron_plugin import config

from neutron.db import model_base
from neutron.db import models_v2
from neutron.openstack.common import log as logging

import sqlalchemy as sa
from sqlalchemy import orm as sa_orm

import base64

LOG = logging.getLogger(__name__)


def aes_encrypt(key, msg):
    iv = Random.new().read(AES.block_size)
    cipher = AES.new(key, AES.MODE_CFB, iv)
    ciphertext = iv + cipher.encrypt(msg)
    return base64.b64encode(ciphertext)


def aes_decrypt(key, msg):
    msg = base64.b64decode(msg)
    iv = msg[:AES.block_size]
    cipher = AES.new(key, AES.MODE_CFB, iv)
    msg = cipher.decrypt(msg[AES.block_size:])
    return msg


class EncryptedValue(sa.TypeDecorator):
    impl = sa.String

    def process_bind_param(self, value, dialect):
        if value:
            key = config.get_ironic_config().credential_secret
            value = aes_encrypt(key, value)
        return value

    def process_result_value(self, value, dialect):
        if value:
            key = config.get_ironic_config().credential_secret
            value = aes_decrypt(key, value)
        return value


class IronicSwitchPort(model_base.BASEV2, models_v2.HasId):
    """Maps a device to a physical switch port."""

    __tablename__ = "ironic_switch_ports"
    
    switch_id = sa.Column(sa.String(255),
                          sa.ForeignKey("ironic_switches.id"),
                          nullable=False)
    port = sa.Column(sa.String(255), nullable=False)
    hardware_id = sa.Column(sa.String(255), index=True, nullable=False)
    primary = sa.Column(sa.Boolean, nullable=False)

    # LLDP fields
    system_name = sa.Column(sa.String(255), nullable=True)
    port_id = sa.Column(sa.String(255), nullable=True)
    port_description = sa.Column(sa.String(255), nullable=True)
    chassis_id = sa.Column(sa.String(255), nullable=True)
    
    # Extra
    mac_address = sa.Column(sa.String(255), nullable=True)


    def as_dict(self):
        return {
            u"id": self.id,
            u"switch_id": self.switch_id,
            u"port": self.port,

            u"system_name": self.system_name,
            u"port_id": self.port_id,
            u"chassis_id": self.chassis_id,
            u"port_description": self.port_description,
            u"mac_address": self.mac_address,

            u"hardware_id": self.hardware_id,
            u"primary": self.primary
        }


class IronicSwitchType(object):

    cisco = u"cisco"
    arista = u"arista"
    dummy = u"dummy"

    @classmethod
    def as_dict(cls):
        return {
            u"cisco": cls.cisco,
            u"arista": cls.arista,
            u"dummy": cls.dummy
        }


class IronicSwitch(model_base.BASEV2):
    """A physical switch and admin credentials.

    TODO(morgabra) We probably want to assign an id to a switch, maybe
    whatever LLDP returns?
    """

    __tablename__ = "ironic_switches"

    id = sa.Column(sa.String(255), primary_key=True)
    ip = sa.Column(sa.String(255))
    username = sa.Column(sa.String(255), nullable=True)
    password = sa.Column(EncryptedValue(255), nullable=True)

    # TODO(morgabra) validation
    type = sa.Column(sa.String(255))
    switch_ports = sa_orm.relationship(
        IronicSwitchPort, lazy="joined", cascade="delete", backref="switch")

    def as_dict(self):
        return {
            u"id": self.id,
            u"ip": self.ip,
            u"username": self.username,
            u"password": "*****",
            u"type": self.type
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
            u"provider:physical_network": self.physical_network,
            u"provider:segmentation_id": self.segmentation_id,
            u"provider:network_type": self.network_type,
            u"switch:trunked": self.trunked
        }

class IronicPort(model_base.BASEV2):
    """Keep track of extra information about neutron ports."""

    __tablename__ = "ironic_port"

    port_id = sa.Column(sa.String(255), primary_key=True)
    commit = sa.Column(sa.Boolean)
    hardware_id = sa.Column(sa.String(255), nullable=True) 

    def as_dict(self):
        return {
            u"port_id": self.port_id,
            u"switch:commit": self.commit,
            u"switch:hardware_id": self.hardware_id
        }  


class IronicPortBindingState(object):
    """PortBinding states:

    CREATED: Configuration is not active on the switch
             but we want it to be
    ACTIVE: Configuration is running on the switch
    DELETED: Configuration is running on the switch
             but we want it removed
    """
    CREATED = u'CREATED'
    ACTIVE = u'ACTIVE'
    DELETED = u'DELETED'


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
        sa.String(36),
        sa.ForeignKey("ironic_switch_ports.id"),
        primary_key=True)
    state = sa.Column(sa.String(255),
                      default=IronicPortBindingState.CREATED)

    def as_dict(self):
        return {
            u"port_id": self.port_id,
            u"network_id": self.network_id,
            u"switch_port_id": self.switch_port_id,
            u"state": self.state
        }
