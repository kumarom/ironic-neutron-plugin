# Copyright (c) 2014 OpenStack Foundation.
# (c) Copyright 2015 Hewlett-Packard Development Company, L.P.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from sqlalchemy import orm

from neutron.db import api as db_api
from neutron.openstack.common import log as logging

from baremetal_neutron_extension.db import models


LOG = logging.getLogger(__name__)


class IronicDBException(Exception):
    pass


def create_port_ext(port_id, commit, trunked, hardware_id, session=None):
    if not session:
        session = db_api.get_session()

    with session.begin(subtransactions=True):
        port = models.PortExt(
            port_id=port_id,
            commit=commit,
            trunked=trunked,
            hardware_id=hardware_id)
        session.add(port)
        session.flush()
        return port


def get_port_ext(port_id, session=None):
    if not session:
        session = db_api.get_session()

    with session.begin(subtransactions=True):
        try:
            return (session.query(models.PortExt).
                    get((port_id)))
        except orm.exc.NoResultFound:
            return None


def filter_port_ext(session=None, **kwargs):
    if not session:
        session = db_api.get_session()

    with session.begin(subtransactions=True):
        return (session.query(models.PortExt).
                filter_by(**kwargs))


def update_port_ext(port_id, commit=None, hardware_id=None,
                    trunked=None, session=None):
    if not session:
        session = db_api.get_session()

    updated = False

    with session.begin(subtransactions=True):
        port = (session.query(models.PortExt).
                get(port_id))

        if commit is not None:
            port.commit = commit
            updated = True

        if hardware_id is not None:
            port.hardware_id = hardware_id
            updated = True

        if trunked is not None:
            port.trunked = trunked
            updated = True

        if updated:
            session.add(port)
            session.flush()

        return port


def delete_port_ext(port_id, session=None):
    if not session:
        session = db_api.get_session()

    port = get_port_ext(port_id, session)

    if not port:
        return False  # TODO(morgabra) throw probably

    with session.begin(subtransactions=True):
        session.delete(port)
        session.flush()
        return True


def create_switchport_binding(port_id, network_id, switch_port_id,
                              state=None, session=None):
    if not session:
        session = db_api.get_session()

    with session.begin(subtransactions=True):
        portbinding = models.SwitchPortBinding(
            port_id=port_id,
            network_id=network_id,
            switch_port_id=switch_port_id,
            state=None)
        session.add(portbinding)
        session.flush()
        return portbinding


def get_all_switchport_bindings(session=None):
    if not session:
        session = db_api.get_session()

    with session.begin(subtransactions=True):
        return (session.query(models.SwitchPortBinding).all())


def get_switchport_binding(port_id, network_id, switch_port_id, session=None):
    if not session:
        session = db_api.get_session()

    with session.begin(subtransactions=True):
        try:
            return (session.query(models.SwitchPortBinding).
                    get((port_id, network_id, switch_port_id)))
        except orm.exc.NoResultFound:
            return None


def filter_switchport_bindings(session=None, **kwargs):
    if not session:
        session = db_api.get_session()

    with session.begin(subtransactions=True):
        return (session.query(models.SwitchPortBinding).
                filter_by(**kwargs))


def filter_switchport_bindings_by_switch_port_ids(ids, session=None):
    if not session:
        session = db_api.get_session()

    with session.begin(subtransactions=True):
        return (session.query(models.SwitchPortBinding).
                filter(models.SwitchPortBinding.switch_port_id.in_(ids)))


def update_switchport_binding_state(port_id, network_id, switch_port_id, state,
                                    session=None):
    if not session:
        session = db_api.get_session()

    with session.begin(subtransactions=True):
        portbinding = (session.query(models.SwitchPortBinding).
                       get((port_id, network_id, switch_port_id)))
        portbinding.state = state
        session.add(portbinding)
        session.flush()
        return portbinding


def delete_switchport_binding(port_id, network_id, switch_port_id,
                              session=None):
    if not session:
        session = db_api.get_session()

    portbinding = get_switchport_binding(
        port_id, network_id, switch_port_id, session=session)

    if not portbinding:
        return False  # TODO(morgabra) throw probably

    with session.begin(subtransactions=True):
        session.delete(portbinding)
        session.flush()
        return True


def create_switchports(switchports,
                       session=None):
    if not session:
        session = db_api.get_session()

    created_switchports = []
    with session.begin(subtransactions=True):
        for switchport in switchports:
            sp = models.SwitchPort(
                **switchport)
            session.add(sp)
            sp.switch  # aggresively load the switch model
            created_switchports.append(sp)
        session.flush()
        return created_switchports


def get_all_switchports(session=None):
    if not session:
        session = db_api.get_session()

    with session.begin(subtransactions=True):
        return (session.query(models.SwitchPort).
                options(orm.subqueryload(models.SwitchPort.switch)).all())


def get_switchports_by_ids(ids, session=None):
    if not ids:
        return []

    if not session:
        session = db_api.get_session()

    with session.begin(subtransactions=True):
        return (session.query(models.SwitchPort).
                options(orm.subqueryload(models.SwitchPort.switch)).
                filter(models.SwitchPort.id.in_(ids)))


def filter_switchports(session=None, **kwargs):
    if not session:
        session = db_api.get_session()

    with session.begin(subtransactions=True):
        return (session.query(models.SwitchPort).
                options(orm.subqueryload(models.SwitchPort.switch)).
                filter_by(**kwargs))


def delete_switchports(switchport_ids, session=None):

    if not session:
        session = db_api.get_session()

    if not switchport_ids:
        return False

    with session.begin(subtransactions=True):
        for switchport_id in switchport_ids:
            try:
                switchport = (session.query(models.SwitchPort).
                              get(switchport_id))
            except orm.exc.NoResultFound:
                switchport = None  # TODO(morgabra) this should throw.

            if switchport:
                session.delete(switchport)
        session.flush()
        return True


def compare_switchports(sp_models, sp_dicts, with_id=False, session=None):
    """Compare a hardware_ids switchports with a given list of dicts.

    TODO(morgbara) Can you overload __eq__ on an sqlalchemy model? I actually
    want functional equivalence, unrelated to the model ID.
    """

    if not session:
        session = db_api.get_session()

    if len(sp_models) != len(sp_dicts):
        return False

    sp_models = [m.as_dict() for m in sp_models]
    sp_dicts = [models.SwitchPort.make_dict(d) for d in sp_dicts]

    if not with_id:
        for m in sp_models:
            m.pop("id")
        for d in sp_dicts:
            d.pop("id")

    for d in sp_dicts:
        if d not in sp_models:
            return False

    return True


def create_switch(id, host, username, password, switch_type,
                  description=None, session=None):
    if not session:
        session = db_api.get_session()

    with session.begin(subtransactions=True):
        switch = models.Switch(
            id=id,
            host=host,
            username=username,
            password=password,
            type=switch_type,
            description=description)
        session.add(switch)
        return switch


def get_switch(switch_id, session=None):
    if not session:
        session = db_api.get_session()

    with session.begin(subtransactions=True):
        try:
            return (session.query(models.Switch).
                    get(switch_id))
        except orm.exc.NoResultFound:
            return None


def filter_switches(session=None, **kwargs):
    if not session:
        session = db_api.get_session()

    with session.begin(subtransactions=True):

        return (session.query(models.Switch).
                filter_by(**kwargs))


def get_all_switches(session=None):
    if not session:
        session = db_api.get_session()

    with session.begin(subtransactions=True):
        return (session.query(models.Switch).all())


def delete_switch(switch_id, session=None):
    if not session:
        session = db_api.get_session()

    switch = get_switch(switch_id, session=session)

    if not switch:
        return False  # TODO(morgabra) Throw probably

    with session.begin(subtransactions=True):
        session.delete(switch)
        session.flush()
        return True
