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

import copy

from baremetal_neutron_extension.db import db
from baremetal_neutron_extension.drivers import manager
from baremetal_neutron_extension import extensions
from baremetal_neutron_extension.extensions import switch

from neutron.api import extensions as neutron_extensions
from neutron.api.v2 import attributes
from neutron.common import exceptions as exc
from neutron.db import db_base_plugin_v2
from neutron.openstack.common import log as logging
from neutron.plugins.ml2 import driver_api as api

LOG = logging.getLogger(__name__)


class IronicExtensionDriver(api.ExtensionDriver):

    _supported_extension_aliases = ["switch", "commit", "trunked"]

    db_base_plugin_v2.NeutronDbPluginV2.register_dict_extend_funcs(
        attributes.PORTS, ['_find_port_dict_extensions'])
    db_base_plugin_v2.NeutronDbPluginV2.register_dict_extend_funcs(
        attributes.PORT, ['_find_port_dict_extensions'])

    def initialize(self):
        neutron_extensions.append_api_extensions_path(extensions.__path__)
        LOG.info("IronicExtensionDriver initialization complete")

    @property
    def extension_alias(self):
        """
        Supported extension alias.

        :returns: alias identifying the core API extension supported
                  by this driver
        """
        if not hasattr(self, '_aliases'):
            aliases = self._supported_extension_aliases[:]
            self._aliases = aliases
        return self._aliases

    def extend_port_dict(self, session, model, result):
        """Add extended attributes to port dictionary.

        :param session: database session
        :param result: port dictionary to extend

        Called inside transaction context on session to add any
        extended attributes defined by this driver to a port
        dictionary to be used for mechanism driver calls and/or
        returned as the result of a port operation.
        """

        commit = self._get_port_attr(model, "commit")
        trunked = self._get_port_attr(model, "trunked")
        hardware_id = self._get_port_attr(model, "switch:hardware_id")
        switchports = self._get_port_attr(model, "switch:ports")
        if switchports is None:
            switchports = []
        if commit is None:
            commit = False

        port_ext = db.get_port_ext(result["id"], session=session)
        if port_ext:
            LOG.info("Port %s does not have extension data"
                     % model["id"])
            port_ext = port_ext.as_dict()
            result["commit"] = port_ext["commit"]
            result["trunked"] = port_ext["trunked"]
            if port_ext["hardware_id"]:
                switchports = db.filter_switchports(
                    hardware_id=port_ext["hardware_id"],
                    session=session)
                switchports = [sp.as_dict() for sp in switchports]
            result["switch:hardware_id"] = port_ext["hardware_id"]
            result["switch:ports"] = switchports
        else:
            result["switch:hardware_id"] = hardware_id
            result["commit"] = commit
            result["trunked"] = trunked
            result["switch:ports"] = switchports

    def _get_port_attr(self, port, key):
        val = port.get(key)
        if val == attributes.ATTR_NOT_SPECIFIED:
            val = None
        return val

    def _find_port_dict_extensions(self, port_res, port_db, port_ext=None,
                                   switchports=None, session=None):
        """Looks up extension data and updates port_res."""
        if not port_ext:
            port_ext = db.get_port_ext(port_res["id"], session=session)
            if not port_ext:
                LOG.error("Port %s does not have extension data"
                          % port_db["id"])
                return
            port_ext = port_ext.as_dict()

        if not switchports:
            switchports = []
            if port_ext["hardware_id"]:
                switchports = db.filter_switchports(
                    hardware_id=port_ext["hardware_id"], session=session)
            switchports = [sp.as_dict() for sp in switchports]

        port_res["switch:ports"] = switchports
        port_res["switch:hardware_id"] = port_ext["hardware_id"]
        port_res["commit"] = port_ext["commit"]
        port_res["trunked"] = port_ext["trunked"]

    def _create_port_ext(self, res_port, req_port, context):
        """Create db model to keep track of extension data."""
        commit = self._get_port_attr(req_port, "commit")
        trunked = self._get_port_attr(req_port, "trunked")
        hardware_id = self._get_port_attr(req_port, "switch:hardware_id")
        if commit is None:
            commit = False
        port_ext = db.create_port_ext(
            port_id=res_port["id"],
            commit=commit,
            trunked=trunked,
            hardware_id=hardware_id,
            session=context.session)
        return port_ext.as_dict()

    def _update_port_ext(self, original_port, req_port,
                         session=None):
        """Update db model keeping track of extension data."""

        commit = self._get_port_attr(req_port, "commit")
        trunked = self._get_port_attr(req_port, "trunked")
        hardware_id = self._get_port_attr(req_port, "switch:hardware_id")

        # we cannot allow the trunked flag to change if committed.
        if trunked is not None and (original_port["trunked"] != trunked):
            if original_port["commit"] and (commit is not False):
                msg = "cannot update trunked flag when commit=true"
                raise exc.InvalidInput(error_message=msg)

        port_ext = db.update_port_ext(
            port_id=original_port["id"],
            trunked=trunked,
            commit=commit,
            hardware_id=hardware_id,
            session=session)
        return port_ext.as_dict()

    def _update_switchports(self, res_port, req_port, session=None):
        hardware_id = self._get_port_attr(req_port, "switch:hardware_id")
        switchports = self._get_port_attr(req_port, "switch:ports")

        if not switchports:
            return []

        if switchports and not hardware_id:
            msg = "switch:ports requires switch:hardware_id"
            raise exc.InvalidInput(error_message=msg)

        for sp in switchports:
            sp["hardware_id"] = hardware_id

        switchports = switch.SwitchPortController.update_switchports(
            switchports, session=session)
        return [sp.as_dict() for sp in switchports]

    def _validate_port_can_commit(self, res_port, req_port,
                                  session=None):
        """Poorly named function that determines if a port can actually
        be configured given the state of the system. (ex. do not allow a
        non-trunked port to be committed to a running trunked config.)
        """
        switchport_ids = [p["id"] for p in res_port["switch:ports"]]

        if not switchport_ids:
            msg = ("Cannot attach, no switchports found")
            raise exc.InvalidInput(error_message=msg)

        bound_port_ids = []
        if switchport_ids:
            # Fetch all existing networks we are attached to.
            portbindings = db.filter_switchport_bindings_by_switch_port_ids(
                switchport_ids, session=session)
            portbindings = list(portbindings)
            bound_port_ids = set([pb.port_id for pb in portbindings])

        # We can't attach to a non-trunked network if the port is already
        # attached to another network.
        if bound_port_ids and (res_port["trunked"] is False):
            msg = ("Cannot attach non-trunked network, port "
                   "already bound to network(s) %s" % (bound_port_ids))
            raise exc.InvalidInput(error_message=msg)

        for bound_port_id in bound_port_ids:
            # We can't attach a trunked network if we are already attached
            # to a non-trunked network.
            port_ext = db.get_port_ext(bound_port_id, session=session)
            if not port_ext.trunked:
                msg = ("Already attached via non-trunked "
                       "port %s" % (bound_port_id))
                raise exc.InvalidInput(error_message=msg)

    def process_create_port(self, context, port, result):
        """Process extended attributes for create network.
        :param context: database session
        :param port: dictionary of incoming network data
        :param result: network dictionary to extend

        Called inside transaction context on session to validate and
        persist any extended network attributes defined by this
        driver. Extended attribute values must also be added to
        result.
        """

        # Process extension data
        port_ext = self._create_port_ext(result, port, context=context)
        switchports = self._update_switchports(result, port,
                                               session=context.session)
        self._find_port_dict_extensions(result, None, port_ext=port_ext,
                                        switchports=switchports,
                                        session=context.session)

        # Validate we can actually configure this port
        if result["commit"]:
            self._validate_port_can_commit(result, None,
                                           session=context.session)

    def process_update_port(self, context, data, result):
        """Process extended attributes for update port.

        :param context: database session
        :param data: dictionary of incoming port data
        :param result: port dictionary to extend

        Called inside transaction context on session to validate and
        update any extended port attributes defined by this
        driver. Extended attribute values, whether updated or not,
        must also be added to result.
        """

        orginal_exten = copy.deepcopy(result)
        # Process extension data
        self._find_port_dict_extensions(
            result, None, session=context.session)

        port_ext = self._update_port_ext(
            result, data, session=context.session)
        switchports = self._update_switchports(
            result, data, session=context.session)
        self._find_port_dict_extensions(
            result, None, port_ext=port_ext,
            switchports=switchports, session=context.session)

        # We only want to commit on a state change
        if orginal_exten.get("commit") != result["commit"]:
            # If we are transitioning to active, validate
            if not orginal_exten.get("commit") and result["commit"]:
                self._validate_port_can_commit(
                    result, None, session=context.session)


class IronicMechanismDriver(api.MechanismDriver):

    def initialize(self):
        self._driver_manager = manager.DriverManager()
        LOG.info("IronicMechanismDriver initialized.")

    def get_driver_manager(self):
        return self._driver_manager

    def create_port_postcommit(self, context):
        network = context.network.current
        current = context.current

        if current["commit"] is True:
            LOG.info("create_port_postcommit() commit=True "
                     "for port %s, attaching" % current["id"])
            self.get_driver_manager().attach(current, network)

    def update_port_postcommit(self, context):
        """TODO(morgabra) Failures here do *not* reset the database state :(
        TODO(morgabra) Rethink this - maybe the base plugin should call
        a different function for commit/uncommit?
        """
        network = context.network.current
        original = context.original
        current = context.current

        if original.get("commit") is True and current["commit"] is False:
            LOG.info("update_port_postcommit() commit=True -> commit=False "
                     "for port %s, detaching" % current["id"])
            self.get_driver_manager().detach(current, network)
        elif original.get("commit") is False and current["commit"] is True:
            LOG.info("update_port_postcommit() commit=False -> commit=True "
                     "for port %s, attaching" % current["id"])
            self.get_driver_manager().attach(current, network)
        else:
            LOG.info("update_port_postcommit() commit unchanged"
                     " - skipping.")

    def delete_port_postcommit(self, context):
        network = context.network.current
        current = context.current

        if current["switch:ports"]:
            LOG.info("delete_port_postcommit() for port "
                     "%s, dettaching" % current["id"])
            self.get_driver_manager().detach(current, network)
        else:
            LOG.info("delete_port_postcommit() for port %s, no switchports "
                     "found - skipping detach" % current["id"])
