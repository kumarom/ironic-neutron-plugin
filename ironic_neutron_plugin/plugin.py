# Copyright (c) 2014 OpenStack Foundation.
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

import contextlib

from ironic_neutron_plugin.db import db
from ironic_neutron_plugin.drivers import manager
from ironic_neutron_plugin import extensions
from ironic_neutron_plugin.extensions import switch

from neutron.api import extensions as neutron_extensions
from neutron.api.v2 import attributes
from neutron.common import constants as const
from neutron.common import exceptions as exc
from neutron.db import db_base_plugin_v2
from neutron.extensions import allowedaddresspairs as addr_pair
from neutron.extensions import extra_dhcp_opt as edo_ext
from neutron.openstack.common import excutils
from neutron.openstack.common import lockutils
from neutron.openstack.common import log as logging
from neutron.plugins.ml2.common import exceptions as ml2_exc
from neutron.plugins.ml2 import db as ml2_db
from neutron.plugins.ml2 import driver_api as api
from neutron.plugins.ml2 import driver_context
from neutron.plugins.ml2 import plugin

LOG = logging.getLogger(__name__)


class IronicMl2Plugin(plugin.Ml2Plugin):
    """Base Ml2Plugin with added extensions:
        1) physical switch credential management/port mappings
        2) "commit" flag on the port object
        3) "trunked" flag on the port object
    """

    _supported_extension_aliases = (
        plugin.Ml2Plugin._supported_extension_aliases
        + ["switch", "commit", "trunked"]
    )

    db_base_plugin_v2.NeutronDbPluginV2.register_dict_extend_funcs(
        attributes.PORTS, ['_find_port_dict_extensions'])
    db_base_plugin_v2.NeutronDbPluginV2.register_dict_extend_funcs(
        attributes.PORT, ['_find_port_dict_extensions'])

    def __init__(self, *args, **kwargs):
        super(IronicMl2Plugin, self).__init__(*args, **kwargs)
        neutron_extensions.append_api_extensions_path(extensions.__path__)

    def _get_port_attr(self, port, key):
        val = port["port"].get(key)
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

    def _create_port_ext(self, res_port, req_port, session=None):
        """Create db model to keep track of extension data."""
        commit = self._get_port_attr(req_port, "commit")
        trunked = self._get_port_attr(req_port, "trunked")
        hardware_id = self._get_port_attr(req_port, "switch:hardware_id")
        port_ext = db.create_port_ext(
            port_id=res_port["id"],
            commit=commit,
            trunked=trunked,
            hardware_id=hardware_id,
            session=session)
        return port_ext.as_dict()

    def _update_port_ext(self, original_port, res_port, req_port,
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
            port_id=res_port["id"],
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

    def _delete_port_ext(self, port_id, session=None):
        db.delete_port_ext(port_id, session)

    def create_port(self, context, port):
        do_commit = False

        attrs = port['port']
        attrs['status'] = const.PORT_STATUS_DOWN

        session = context.session
        with session.begin(subtransactions=True):
            self._ensure_default_security_group_on_port(context, port)
            sgids = self._get_security_groups_on_port(context, port)
            dhcp_opts = port['port'].get(edo_ext.EXTRADHCPOPTS, [])
            result = super(plugin.Ml2Plugin, self).create_port(context, port)
            self._process_port_create_security_group(context, result, sgids)
            network = self.get_network(context, result['network_id'])
            binding = ml2_db.add_port_binding(session, result['id'])

            # Process extension data
            port_ext = self._create_port_ext(
                result, port, session=session)
            switchports = self._update_switchports(
                result, port, session=session)
            self._find_port_dict_extensions(
                result, None, port_ext=port_ext,
                switchports=switchports, session=session)

            # Validate we can actually configure this port
            if result["commit"]:
                do_commit = True
                self._validate_port_can_commit(
                    result, None, session=session)

            mech_context = driver_context.PortContext(self, context, result,
                                                      network, binding)
            self._process_port_binding(mech_context, attrs)
            result[addr_pair.ADDRESS_PAIRS] = (
                self._process_create_allowed_address_pairs(
                    context, result,
                    attrs.get(addr_pair.ADDRESS_PAIRS)))
            self._process_port_create_extra_dhcp_opts(context, result,
                                                      dhcp_opts)
            self.mechanism_manager.create_port_precommit(mech_context)

        try:
            if do_commit:
                self.mechanism_manager.create_port_postcommit(mech_context)
        except ml2_exc.MechanismDriverError:
            with excutils.save_and_reraise_exception():
                LOG.error(("mechanism_manager.create_port_postcommit "
                           "failed, deleting port '%s'"), result['id'])
                self.delete_port(context, result['id'])

        # REVISIT(rkukura): Is there any point in calling this before
        # a binding has been succesfully established?
        self.notify_security_groups_member_updated(context, result)

        try:
            bound_context = self._bind_port_if_needed(mech_context)
        except ml2_exc.MechanismDriverError:
            with excutils.save_and_reraise_exception():
                LOG.error(("_bind_port_if_needed "
                           "failed, deleting port '%s'"), result['id'])
                self.delete_port(context, result['id'])
        return bound_context._port

    def update_port(self, context, id, port):
        do_commit = False

        attrs = port['port']
        need_port_update_notify = False

        LOG.info('Attempting port update %s: %s' % (id, port))

        session = context.session

        # REVISIT: Serialize this operation with a semaphore to
        # prevent deadlock waiting to acquire a DB lock held by
        # another thread in the same process, leading to 'lock wait
        # timeout' errors.
        with contextlib.nested(lockutils.lock('db-access'),
                               session.begin(subtransactions=True)):
            port_db, binding = ml2_db.get_locked_port_and_binding(session, id)
            if not port_db:
                raise exc.PortNotFound(port_id=id)

            original_port = self._make_port_dict(port_db)
            # Process extension data
            self._find_port_dict_extensions(
                original_port, None, session=session)

            updated_port = super(plugin.Ml2Plugin, self).update_port(
                context, id, port)

            # Process extension data
            port_ext = self._update_port_ext(
                original_port, updated_port, port, session=session)
            switchports = self._update_switchports(
                updated_port, port, session=session)
            self._find_port_dict_extensions(
                updated_port, None, port_ext=port_ext,
                switchports=switchports, session=session)

            # We only want to commit on a state change
            if original_port["commit"] != updated_port["commit"]:
                do_commit = True
                # If we are transitioning to active, validate
                if not original_port["commit"] and updated_port["commit"]:
                    self._validate_port_can_commit(
                        updated_port, None, session=session)

            if addr_pair.ADDRESS_PAIRS in port['port']:
                need_port_update_notify |= (
                    self.update_address_pairs_on_port(context, id, port,
                                                      original_port,
                                                      updated_port))
            need_port_update_notify |= self.update_security_group_on_port(
                context, id, port, original_port, updated_port)
            network = self.get_network(context, original_port['network_id'])
            need_port_update_notify |= self._update_extra_dhcp_opts_on_port(
                context, id, port, updated_port)
            mech_context = driver_context.PortContext(
                self, context, updated_port, network, binding,
                original_port=original_port)
            need_port_update_notify |= self._process_port_binding(
                mech_context, attrs)
            self.mechanism_manager.update_port_precommit(mech_context)

        # TODO(apech) - handle errors raised by update_port, potentially
        # by re-calling update_port with the previous attributes. For
        # now the error is propogated to the caller, which is expected to
        # either undo/retry the operation or delete the resource.
        if do_commit:
            self.mechanism_manager.update_port_postcommit(mech_context)

        need_port_update_notify |= self.is_security_group_member_updated(
            context, original_port, updated_port)

        if original_port['admin_state_up'] != updated_port['admin_state_up']:
            need_port_update_notify = True

        if need_port_update_notify:
            self._notify_port_updated(mech_context)

        bound_port = self._bind_port_if_needed(
            mech_context,
            allow_notify=True,
            need_notify=need_port_update_notify)
        return bound_port._port

    def delete_port(self, context, id, l3_port_check=True):
        super(IronicMl2Plugin, self).delete_port(
            context, id, l3_port_check=l3_port_check)
        self._delete_port_ext(id, session=context.session)

    def get_ports(self, context, filters=None, fields=None,
                  sorts=None, limit=None, marker=None,
                  page_reverse=False):

        # We want to allow filtering by the hardware_id extension field.
        if 'switch:hardware_id' in filters and filters['switch:hardware_id']:
            ports = db.filter_port_ext(
                hardware_id=filters['switch:hardware_id'],
                session=context.session)
            port_ids = [p.port_id for p in ports]

            # no ports match that hardware_id, so we can bail early
            if not port_ids:
                return []
            else:
                ids = filters.get("id", [])
                filters["id"] = ids + port_ids

        return super(IronicMl2Plugin, self).get_ports(
            context, filters, fields, sorts, limit, marker, page_reverse)


class IronicMechanismDriver(api.MechanismDriver):

    def initialize(self):
        self._driver_manager = manager.DriverManager()
        LOG.info("IronicMechanismDriver initialized.")

    def get_driver_manager(self):
        return self._driver_manager

    def create_port_postcommit(self, context):
        network = context.network.current
        current = context.current

        LOG.info(("create_port_postcommit() commit=True "
                  "for port %s, attaching" % current["id"]))
        self.get_driver_manager().attach(current, network)

    def update_port_postcommit(self, context):
        """TODO(morgabra) Failures here do *not* reset the database state :(
        TODO(morgabra) Rethink this - maybe the base plugin should call
        a different function for commit/uncommit?
        """
        network = context.network.current
        original = context.original
        current = context.current

        if original["commit"] and not current["commit"]:
            LOG.info(("update_port_postcommit() commit=True -> commit=False "
                      "for port %s, detaching" % current["id"]))
            self.get_driver_manager().detach(current, network)
        else:
            LOG.info(("update_port_postcommit() commit=False -> commit=True "
                      "for port %s, attaching" % current["id"]))
            self.get_driver_manager().attach(current, network)

    def delete_port_postcommit(self, context):
        network = context.network.current
        current = context.current

        if current["switch:ports"]:
            LOG.info(("delete_port_postcommit() for port "
                      "%s, dettaching" % current["id"]))
            self.get_driver_manager().detach(current, network)
        else:
            LOG.info(("delete_port_postcommit() for port %s, no switchports "
                      "found - skipping detach" % current["id"]))
