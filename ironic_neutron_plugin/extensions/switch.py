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

from neutron.api import extensions
from neutron import wsgi

from ironic_neutron_plugin.db import db
from ironic_neutron_plugin import exceptions as exc

from simplejson import scanner as json_scanner

from neutron.api.v2 import attributes as attr
from neutron.db import api as db_api
from neutron.openstack.common import log as logging

LOG = logging.getLogger(__name__)

EXTRA_ATTRIBUTES = {
    "ports": {
        "switch:ports": {"allow_post": True, "allow_put": True,
                         "default": attr.ATTR_NOT_SPECIFIED,
                         "is_visible": True},
        "switch:hardware_id": {"allow_post": True, "allow_put": True,
                               "default": attr.ATTR_NOT_SPECIFIED,
                               "validate": {"type:string": None},
                               "is_visible": True}
    }
}


class SwitchController(wsgi.Controller):

    def index(self, request):
        switches = db.get_all_switches()
        return dict(switches=[s.as_dict() for s in switches])

    def show(self, request, id):
        switch = db.get_switch(id)
        if not switch:
            raise exc.NotFound(
                resource="switch %s" % (id))
        return dict(switch=switch.as_dict())

    def delete(self, request, id):
        db.delete_switch(id)

    def create(self, request):
        try:
            body = request.json_body
        except json_scanner.JSONDecodeError:
            raise exc.BadRequest(
                resource="switch",
                reason="invalid JSON body")

        try:
            body = body.pop("switch")
        except KeyError:
            raise exc.BadRequest(
                resource="swtich",
                reason="'switch' not found in request body")

        try:
            id = body.pop('id')

            host = body.pop('host')
            username = body.pop('username')
            password = body.pop('password')

            switch_type = body.pop('type')
        except KeyError as e:
            raise exc.BadRequest(
                resource="switch",
                reason="missing required key: %s" % (e.message))

        # optional
        description = body.get('description')

        switch = db.create_switch(
            id, host, username, password, switch_type, description=description)

        return dict(switch=switch.as_dict())


class SwitchPortController(wsgi.Controller):

    def index(self, request):
        filters = {}
        if request.GET.get("hardware_id"):
            filters["hardware_id"] = request.GET.get("hardware_id")

        if request.GET.get("switch_id"):
            filters["switch_id"] = request.GET.get("switch_id")

        if filters:
            switchports = db.filter_switchports(**filters)
        else:
            switchports = db.get_all_switchports()
        return dict(switchports=[p.as_dict() for p in switchports])

    def show(self, request, hardware_id):
        switchports = db.filter_switchports(hardware_id=hardware_id)
        if not switchports:
            raise exc.NotFound(
                resource="switchports %s" % (hardware_id))
        return dict(switchports=[s.as_dict() for s in switchports])

    def delete(self, request, hardware_id):
        return self.delete_switchports(hardware_id)

    def create(self, request):
        try:
            body = request.json_body
        except json_scanner.JSONDecodeError:
            raise exc.BadRequest(
                resource="switchports",
                reason="invalid JSON body")

        try:
            body = body.pop("switchports")
        except KeyError:
            raise exc.BadRequest(
                resource="switchports",
                reason="'switchports' not found in request body")

        switchports = self.create_switchports(body)
        return dict(switchports=[s.as_dict() for s in switchports])

    @classmethod
    def _validate_hardware_id(cls, switchports):
        # Ensure all given hardware_ids are !None
        hardware_ids = set([s.get("hardware_id") for s in switchports])
        if None in hardware_ids:
             raise exc.BadRequest(
                resource="switchports",
                reason="hardware_id cannot be empty")

        # Ensure all given hardware_ids match
        if (len(hardware_ids) != 1):
             raise exc.BadRequest(
                resource="switchports",
                reason="all switchport hardware_ids must match")

        return list(hardware_ids)[0]

    @classmethod
    def validate_switchports(cls, switchports, session=None):
        """
        TODO(morgabra) Split this up, think about it more. It's
        inefficient and large.
        """
        if not session:
            session = db_api.get_session()

        if not switchports:
            raise exc.BadRequest(
                resource="switchports",
                reason="must specify at least 1 switchport")

        hardware_id = cls._validate_hardware_id(switchports)

        # Ensure no switchports exist for the given hardware_id
        existing = list(db.filter_switchports(hardware_id=hardware_id, session=session))
        if existing:
             raise exc.BadRequest(
                resource="switchports",
                reason="switchports already exist for hardware_id='%s'" % hardware_id)

        # Ensure all given names are !None
        names = set([s.get("name") for s in switchports])
        if None in names:
             raise exc.BadRequest(
                resource="switchports",
                reason="name cannot be empty")

        # Ensure all given names are unique
        if (len(names) != len(switchports)):
             raise exc.BadRequest(
                resource="switchports",
                reason="all switchport names must be unique")

        # Ensure all given switch_id/port maps are unique
        ports = set([(s.get("switch_id"), s.get("port")) for s in switchports])
        if (len(ports) != len(switchports)):
             raise exc.BadRequest(
                resource="switchports",
                reason="cannot add switchport with identical switch_id/port values")

        for switch_id, port in ports:

            # Ensure switch_id is !None
            if not switch_id:
             raise exc.BadRequest(
                resource="switchports",
                reason="switch_id cannot be empty")

            # Ensure switch_id is !None
            if not port:
             raise exc.BadRequest(
                resource="switchports",
                reason="port cannot be empty")

            # Ensure referenced switch actually exists
            switch = db.get_switch(switch_id, session=session)
            if not switch:
                raise exc.NotFound(
                    resource="switch %s" % (switch_id))

            # Ensure switchport not taken by another hardware_id
            existing = list(db.filter_switchports(
                switch_id=switch_id, port=port, session=session))
            if len(existing) >= 1:
                raise exc.BadRequest(
                    resource="switchport",
                    reason=("port already mapped to hardware_id "
                            "'%s'" % (existing[0].hardware_id)))

        return switchports

    @classmethod
    def create_switchports(cls, switchports, session=None):
        if not session:
            session = db_api.get_session()

        with session.begin(subtransactions=True):
            switchports = cls.validate_switchports(switchports, session=session)
            return db.create_switchports(switchports, session=session)

    @classmethod
    def delete_switchports(cls, hardware_id, switchports=None, session=None):
        if not session:
            session = db_api.get_session()

        # find pre-existing portmaps and check if they are in-use before deleting.
        with session.begin(subtransactions=True):

            if not switchports:
                switchports = list(db.filter_switchports(hardware_id=hardware_id, session=session))

            switchport_ids = [sp.id for sp in switchports]
            if switchport_ids:
                bindings = list(db.filter_switchport_bindings_by_switch_port_ids(switchport_ids, session=session))
                if bindings:
                    raise exc.BadRequest(
                        resource="switchport",
                        reason=("Cannot delete, switchport(s) '%s' in use" % (','.join(switchport_ids)))
                    )
            return db.delete_switchports(switchport_ids, session=session)

    @classmethod
    def update_switchports(cls, switchports, session=None):
        if not session:
            session = db_api.get_session()

        with session.begin(subtransactions=True):

            hardware_id = cls._validate_hardware_id(switchports)
            originals = list(db.filter_switchports(hardware_id=hardware_id, session=session))

            # If the given switchports match what exists in the db, we don't have to do anything.
            equal = db.compare_switchports(originals, switchports, session=session)

            if equal:
                LOG.info("No switchports update required for hardware_id %s" % (hardware_id))
                return originals
            else:
                LOG.info("Updating switchports for hardware_id %s" % (hardware_id))
                # TODO(morgbara) this is a little ham-fisted, but it's *super* complicated to allow
                # updating a switchport from underneath a running config.
                cls.delete_switchports(hardware_id, session=session)
                return cls.create_switchports(switchports, session=session)



class Switch(extensions.ExtensionDescriptor):

    @classmethod
    def get_name(cls):
        return "Switch"

    @classmethod
    def get_alias(cls):
        return "switch"

    @classmethod
    def get_description(cls):
        return ("Physical switch with access credentials "
                "and hardware_id <-> switch port mapping")

    @classmethod
    def get_namespace(cls):
        return "http://github.com/rackerlabs/ironic-neutron-plugin"

    @classmethod
    def get_updated(cls):
        return "2014-03-11T00:00:00-00:00"

    def get_resources(self):
        resources = []
        sresource = extensions.ResourceExtension("switches",
                                                 SwitchController())
        resources.append(sresource)

        presource = extensions.ResourceExtension("switchports",
                                                 SwitchPortController())
        resources.append(presource)
        return resources

    def get_extended_resources(self, version):
        if version == "2.0":
            return EXTRA_ATTRIBUTES
        else:
            return {}
