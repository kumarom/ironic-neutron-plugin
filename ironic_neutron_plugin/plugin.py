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

from neutron.api.v2 import attributes

from sqlalchemy.orm import exc as sa_exc
from neutron.common import exceptions as exc

from neutron.common import constants as const

from neutron.extensions import extra_dhcp_opt as edo_ext
from neutron.extensions import allowedaddresspairs as addr_pair
from neutron.plugins.ml2.common import exceptions as ml2_exc
from neutron.openstack.common import excutils

from neutron.db import models_v2

from neutron.plugins.ml2 import driver_context

from neutron.db import db_base_plugin_v2

from neutron.plugins.ml2 import plugin
from neutron.plugins.ml2 import driver_api as api

from ironic_neutron_plugin.db import db
from ironic_neutron_plugin.drivers import manager
from ironic_neutron_plugin.extensions import switch

from neutron.openstack.common import log as logging

from oslo.config import cfg

LOG = logging.getLogger(__name__)


ironic_opts = [
    cfg.BoolOpt("dry_run",
                default=False,
                help="Log only, but exersize the mechanism."),
    cfg.StrOpt("credential_secret",
               help=("Secret AES key for encrypting switch credentials "
                     " in the datastore."))
]

cfg.CONF.register_opts(ironic_opts, "ironic")


class IronicMl2Plugin(plugin.Ml2Plugin):
    """
    Base Ml2Plugin with added extensions:
        1) physical switch credential management/port mappings
        2) "commit" flag on the port object
        3) "trunked" flag on the port object

    A subclass would not be necessary if:
        1) You could load extensions from a mechanism/config file/something
        2) The mech_context contained the request body
           (for extension field processing)

    TODO(morgabra) Some of this stuff might make it upstream with some attention
    (physical portmaps?), but other stuff might be a harder sell. ("commit" flag)

    TODO(morgabra) Currently there's an additional driver abstraction layer
    for the mechanism, which should probably be split out in leu of different
    mechanisms that check switch:port["type"]?

    TODO(morgabra) It seems like we should use the portbinding extension
    in some capacity, I don't understand it.

    TODO(morgabra) Does "trunked" belong on the port or network?

    TODO(morgabra) "commit" is a strange feature, separating the neturon
    data model from the actual network configuration. This was a result
    of nova creating ports for the ironic virt driver before we were ready
    to realize that configuration on the switch. I'm not sure it's a great
    idea and maybe changing nova behavior would be better? (Pushing the port)
    """

    _supported_extension_aliases = (
        plugin.Ml2Plugin._supported_extension_aliases
        + ["switch", "commit", "trunked"]
    )

    db_base_plugin_v2.NeutronDbPluginV2.register_dict_extend_funcs(
        attributes.PORTS, ['_find_port_dict_extensions'])
    db_base_plugin_v2.NeutronDbPluginV2.register_dict_extend_funcs(
        attributes.PORT, ['_find_port_dict_extensions'])

    def _get_port_attr(self, port, key):
        if "port" not in port:
            port = {"port": port}

        val = port["port"].get(key)
        if val == attributes.ATTR_NOT_SPECIFIED:
            val = None
        return val

    def _find_port_dict_extensions(self, port_res, port_db,
                                   port_ext=None, switchports=None, session=None):
        """Looks up extension data and updates port_res."""
        if not port_ext:
            port_ext = db.get_port_ext(port_res["id"], session=session)
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

    def _update_port_ext(self, original_port, res_port, req_port, session=None):
        """Update db model keeping track of extension data."""

        commit = self._get_port_attr(req_port, "commit")
        trunked = self._get_port_attr(req_port, "trunked")
        hardware_id = self._get_port_attr(req_port, "switch:hardware_id")

        # we cannot allow the trunked flag to change for already committed ports.
        if trunked != None and (original_port["trunked"] != trunked):
            if original_port["commit"] and (commit != False):
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

        # We add hardware_id from the top-level object to each switchport, which
        # the portmap controller expects and allows us to use the same code.
        for sp in switchports:
            sp["hardware_id"] = hardware_id

        # TODO(morgabra) This is not all that intuitive and maybe wrong. Instead
        # of erroring if there are switchports already available for the hardware_id
        # and requiring a separate call to delete them, we can just update them
        # if they aren't in use (which update_portmaps() does for us.)
        switchports = switch.SwitchPortController.update_switchports(
            switchports, session=session)
        return [sp.as_dict() for sp in switchports]

    def _validate_port_can_commit(self, res_port, req_port, session=None):
        """
        Poorly named function that determines if a port can actually be configured
        given the state of the system. (ex. do not allow a non-trunked port to be
        committed to a running trunked config.)
        """
        switchport_ids = [p["id"] for p in res_port["switch:ports"]]

        if not switchport_ids:
            msg = ("Cannot attach, no switchports found")
            raise exc.InvalidInput(error_message=msg)

        bound_port_ids = []
        if switchport_ids:
            # Fetch all existing networks we are attached to.
            portbindings = list(db.filter_switchport_bindings_by_switch_port_ids(
                switchport_ids))
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
            port_ext = db.get_port_ext(bound_port_id)
            if not port_ext.trunked:
                msg = ("Already attached via non-trunked "
                       "port %s" % (bound_port_id))
                raise exc.InvalidInput(error_message=msg)

    def _delete_port_ext(self, port_id):
        db.delete_port_ext(port_id)

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

            # Process extension data
            port_ext = self._create_port_ext(result, port, session=session)
            switchports = self._update_switchports(result, port, session=session)
            self._find_port_dict_extensions(result, None,
                port_ext=port_ext, switchports=switchports)
            # Validate we can actually configure this port
            if result["commit"]:
                do_commit = True
                self._validate_port_can_commit(
                    result, None, session=session)

            self._process_port_create_security_group(context, result, sgids)
            network = self.get_network(context, result['network_id'])
            mech_context = driver_context.PortContext(self, context, result,
                                                      network)
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
                LOG.error(_("mechanism_manager.create_port_postcommit "
                            "failed, deleting port '%s'"), result['id'])
                self.delete_port(context, result['id'])
        self.notify_security_groups_member_updated(context, result)
        return result

    def update_port(self, context, id, port):
        do_commit = False

        attrs = port['port']
        need_port_update_notify = False

        session = context.session
        changed_fixed_ips = 'fixed_ips' in port['port']
        with session.begin(subtransactions=True):
            try:
                port_db = (session.query(models_v2.Port).
                           enable_eagerloads(False).
                           filter_by(id=id).with_lockmode('update').one())
            except sa_exc.NoResultFound:
                raise exc.PortNotFound(port_id=id)

            # Process extension data
            original_port = self._make_port_dict(port_db)
            self._find_port_dict_extensions(
                original_port, None, session=session)

            updated_port = super(plugin.Ml2Plugin, self).update_port(context, id,
                                                              port)

            # Process extension data
            port_ext = self._update_port_ext(original_port, updated_port, port, session=session)
            switchports = self._update_switchports(updated_port, port, session=session)
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
            elif changed_fixed_ips:
                self._check_fixed_ips_and_address_pairs_no_overlap(
                    context, updated_port)
            need_port_update_notify |= self.update_security_group_on_port(
                context, id, port, original_port, updated_port)
            network = self.get_network(context, original_port['network_id'])
            need_port_update_notify |= self._update_extra_dhcp_opts_on_port(
                context, id, port, updated_port)
            mech_context = driver_context.PortContext(
                self, context, updated_port, network,
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

        return updated_port

    def delete_port(self, context, id, l3_port_check=True):
        super(IronicMl2Plugin, self).delete_port(
            context, id, l3_port_check=True)
        self._delete_port_ext(id)


    def get_ports(self, context, filters=None, fields=None,
                  sorts=None, limit=None, marker=None,
                  page_reverse=False):

        # We want to allow filtering by the hardware_id extension field.
        if 'switch:hardware_id' in filters and filters['switch:hardware_id']:
            ports = db.filter_port_ext(hardware_id=filters['switch:hardware_id'])
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
        self.driver_manager = manager.DriverManager()
        LOG.info("IronicMechanismDriver initialized.")

    def create_network_postcommit(self, context):
        # TODO(morgabra) Actually provision vlan
        pass

    def create_port_postcommit(self, context):
        network = context.network.current
        current = context.current

        LOG.info("create_port_postcommit() commit=True for port %s, attaching" % current["id"])
        self.driver_manager.attach(current, network)


    def update_port_postcommit(self, context):
        """
        TODO(morgabra) Failures here do *not* reset the database state :(
        TODO(morgabra) Rethink this - it's a bummer that this single function
        is responsible for figuring out if it should commit or uncommit a config
        """
        network = context.network.current
        original = context.original
        current = context.current

        if original["commit"] and not current["commit"]:
            LOG.info("update_port_postcommit() commit=True -> commit=False for port %s, detaching" % current["id"])
            self.driver_manager.detach(current, network)
        else:
            LOG.info("update_port_postcommit() commit=False -> commit=True for port %s, attaching" % current["id"])
            self.driver_manager.attach(current, network)

    def delete_port_postcommit(self, context):
        network = context.network.current
        current = context.current

        if not current["switch:ports"]:
            msg = "cannot update port, no switchports found"
            raise exc.InvalidInput(error_message=msg)

        LOG.info("delete_port_postcommit() for port %s, dettaching" % current["id"])
        self.driver_manager.detach(current, network)

    def bind_port(self, context):
        pass
