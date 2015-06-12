# Copyright 2014 OpenStack Foundation
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.
#

"""
Baremetal-neutron-extension

Revision ID: 3caaf9877f73
Revises: kilo
Create Date: 2014-09-11 13:23:27.828913

"""

# revision identifiers, used by Alembic.
revision = '3caaf9877f73'
down_revision = 'kilo'

from Crypto.Cipher import AES
from Crypto import Random

from alembic import op
import sqlalchemy as sa

import base64
from neutron_ironic_extension import config


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
            key = config.cfg.CONF.ironic.credential_secret
            value = aes_encrypt(key, value)
        return value

    def process_result_value(self, value, dialect):
        if value:
            key = config.cfg.CONF.ironic.credential_secret
            value = aes_decrypt(key, value)
        return value


def upgrade(active_plugins=None, options=None):
    op.create_table(
        'switches',
        sa.Column('id', sa.String(255), primary_key=True),
        sa.Column('description', sa.String(255)),
        sa.Column('host', sa.String(255)),
        sa.Column('username', sa.String(255), nullable=True),
        sa.Column('password', EncryptedValue(255), nullable=True),
        sa.Column('type', sa.String(255)))

    op.create_table(
        'switch_ports',
        sa.Column('id', sa.String(255), primary_key=True),
        sa.Column('switch_id', sa.String(255), sa.ForeignKey("switches.id"),
                  nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('port', sa.String(255), nullable=False),
        sa.Column('hardware_id', sa.String(255), nullable=True),
        sa.Column('mac_address', sa.String(255), nullable=True))

    op.create_table(
        'port_ext',
        sa.Column('port_id', sa.String(255), primary_key=True),
        sa.Column('commit', sa.Boolean, nullable=False),
        sa.Column('trunked', sa.Boolean, nullable=True),
        sa.Column('hardware_id', sa.String(255), nullable=True))

    op.create_table(
        'switch_port_bindings',
        sa.Column('port_id', sa.String(255), primary_key=True),
        sa.Column('network_id', sa.String(255), primary_key=True),
        sa.Column('switch_port_id', sa.String(255),
                  sa.ForeignKey("switch_ports.id"),
                  primary_key=True),
        sa.Column('state', sa.String(255), default=u"INACTIVE"))


def downgrade(active_plugins=None, options=None):
    op.drop_table('switch_port_bindings')
    op.drop_table('port_ext')
    op.drop_table('switch_ports')
    op.drop_table('switches')
