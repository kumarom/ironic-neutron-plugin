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

from ironic_neutron_plugin.config import cfg

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
            key = cfg.CONF.ironic.credential_secret
            value = aes_encrypt(key, value)
        return value

    def process_result_value(self, value, dialect):
        if value:
            key = cfg.CONF.ironic.credential_secret
            value = aes_decrypt(key, value)
        return value


class SwitchPort(model_base.BASEV2, models_v2.HasId):
    """Maps a device to a physical switch port."""

    __tablename__ = "switch_ports"

    switch_id = sa.Column(sa.String(255),
                          sa.ForeignKey("switches.id"),
                          nullable=False)

    # Interface name (eth0, some other meaningful identifier)
    name = sa.Column(sa.String(255), nullable=False)
    # Switchport identifier (Ethernet1/1, something your mech understands)
    port = sa.Column(sa.String(255), nullable=False)
    # Some kind of externally-identifiable id suitable for mapping multiple
    # ports to a single entity (ironic node_id)
    hardware_id = sa.Column(sa.String(255), nullable=True)

    # Extra
    mac_address = sa.Column(sa.String(255), nullable=True)


    def as_dict(self):
        return {
            u"id": self.id,
            u"switch_id": self.switch_id,
            u"name": self.name,
            u"port": self.port,
            u"hardware_id": self.hardware_id,

            # extra
            u"mac_address": self.mac_address
        }

    @classmethod
    def make_dict(cls, d):
        return {
            u"id": d.get("id"),
            u"switch_id": d.get("switch_id"),
            u"name": d.get("name"),
            u"port": d.get("port"),
            u"hardware_id": d.get("hardware_id"),
            u"mac_address": d.get("mac_address")
        }



class Switch(model_base.BASEV2):
    """An external attachment point"""

    __tablename__ = "switches"

    id = sa.Column(sa.String(255), primary_key=True)
    description = sa.Column(sa.String(255))
    type = sa.Column(sa.String(255))

    # TODO(morgabra) move this out into a separate model
    host = sa.Column(sa.String(255))
    username = sa.Column(sa.String(255), nullable=True)
    password = sa.Column(EncryptedValue(255), nullable=True)

    ports = sa_orm.relationship(
        SwitchPort, lazy="joined", cascade="delete", backref="switch")

    def as_dict(self):
        return {
            u"id": self.id,
            u"description": self.description,
            u"host": self.host,
            u"username": self.username,
            u"password": "*****",
            u"type": self.type
        }


class PortExt(model_base.BASEV2):
    """Keep track of extra information about neutron ports.

    TODO(morgabra) This is not correct, but we need to stick
    this data somewhere.
    """

    __tablename__ = "port_ext"

    # TODO(morgabra) FK to the actual model and cascade
    port_id = sa.Column(sa.String(255), primary_key=True)
    hardware_id = sa.Column(sa.String(255), nullable=True)

    commit = sa.Column(sa.Boolean, nullable=False)
    trunked = sa.Column(sa.Boolean, nullable=True)


    def as_dict(self):
        return {
            u"port_id": self.port_id,
            u"commit": self.commit,
            u"trunked": self.trunked,
            u"hardware_id": self.hardware_id
        }


class SwitchPortBindingState(object):

    INACTIVE = u"INACTIVE"
    WANT_ACTIVE = u"WANT_ACTIVE"
    ACTIVE = u"ACTIVE"
    WANT_INACTIVE = u"WANT_INACTIVE"
    ERROR = u"ERROR"

    @classmethod
    def as_dict(cls):
        return {
            u"INACTIVE": cls.INACTIVE,
            u"WANT_ACTIVE": cls.WANT_ACTIVE,
            u"ACTIVE": cls.ACTIVE,
            u"WANT_INACTIVE": cls.WANT_INACTIVE,
            u"ERROR": cls.ERROR
        }


class SwitchPortBinding(model_base.BASEV2):
    """Keep track of which neutron ports are bound to which
    physical switchports.
    """

    __tablename__ = "switch_port_bindings"

    # TODO(morgabra) FK to the actual model and cascade
    port_id = sa.Column(sa.String(255), primary_key=True)
    network_id = sa.Column(sa.String(255), primary_key=True)
    switch_port_id = sa.Column(
        sa.String(36),
        sa.ForeignKey("switch_ports.id"),
        primary_key=True)
    state = sa.Column(sa.String(255),
                      default=SwitchPortBindingState.INACTIVE)

    def as_dict(self):
        return {
            u"port_id": self.port_id,
            u"network_id": self.network_id,
            u"switch_port_id": self.switch_port_id,
            u"state": self.state
        }
