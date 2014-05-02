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

from neutron.db import api as db_api

from neutron.db import agentschedulers_db
from neutron.db import allowedaddresspairs_db as addr_pair_db
from neutron.db import db_base_plugin_v2
from neutron.db import external_net_db
from neutron.db import extradhcpopt_db
from neutron.db import securitygroups_rpc_base as sg_db_rpc
from neutron.db import quota_db  # noqa


from ironic_neutron_plugin.db import db
from ironic_neutron_plugin.drivers import manager
from ironic_neutron_plugin.extensions import switch

from neutron.api.v2 import attributes as attr
from neutron.common import exceptions as n_exc
from neutron.openstack.common import log as logging

LOG = logging.getLogger(__name__)


class IronicPlugin(db_base_plugin_v2.NeutronDbPluginV2,
                   external_net_db.External_net_db_mixin,
                   sg_db_rpc.SecurityGroupServerRpcMixin,
                   agentschedulers_db.DhcpAgentSchedulerDbMixin,
                   addr_pair_db.AllowedAddressPairsMixin,
                   extradhcpopt_db.ExtraDhcpOptMixin):

    __native_bulk_support = False
    __native_pagination_support = False
    __native_sorting_support = True

    supported_extension_aliases = ["switch", "external-net", "binding",
                                   "quotas", "security-group", "agent",
                                   "dhcp_agent_scheduler",
                                   "multi-provider", "allowed-address-pairs",
                                   "extra_dhcp_opt", "provider"]

    def __init__(self):
        super(IronicPlugin, self).__init__()
        db_api.configure_db()

        self.driver_manager = manager.DriverManager()

        LOG.info("Ironic plugin initialized.")

    def _validate_network_extensions(self, network):

        physical_network = network["network"].get("provider:physical_network")
        if physical_network == attr.ATTR_NOT_SPECIFIED:
            raise n_exc.BadRequest(
                resource="network",
                msg="'provider:physical_network' is required")

        network_type = network["network"].get("provider:network_type")
        if network_type == attr.ATTR_NOT_SPECIFIED:
            raise n_exc.BadRequest(
                resource="network",
                msg="'provider:network_type' is required")

        segmentation_id = network["network"].get("provider:segmentation_id")
        if segmentation_id == attr.ATTR_NOT_SPECIFIED:
            raise n_exc.BadRequest(
                resource="network",
                msg="'provider:segmentation_id' is required")

        trunked = bool(network["network"].get("switch:trunked"))

        return {
            "physical_network": physical_network,
            "network_type": network_type,
            "segmentation_id": segmentation_id,
            "trunked": trunked
        }

    def create_network(self, context, network):
        #TODO(morgabra) Actually provision vlan or whatever
        network_extension_data = self._validate_network_extensions(
            network)

        neutron_network = super(IronicPlugin, self).create_network(
            context, network)

        ironic_network = db.create_network(
            neutron_network['id'],
            **network_extension_data
        )
        return self._add_network_data(neutron_network, ironic_network)

    def delete_network(self, context, id):
        # TODO(morgabra) This needs implemented
        res = super(IronicPlugin, self).delete_network(context, id)
        db.delete_network(id)
        return res

    def update_network(self, context, id, network):
        return super(IronicPlugin, self).update_network(context, id, network)

    def get_network(self, context, id, fields=None):
        network = super(IronicPlugin, self).get_network(context, id, fields)
        return self._add_network_data(network)

    def get_networks(self, context, filters=None, fields=None,
                     sorts=None, limit=None, marker=None,
                     page_reverse=False):
        networks = super(IronicPlugin, self).get_networks(
            context, filters, fields, sorts, limit, marker, page_reverse)
        return [self._add_network_data(n) for n in networks]

    def _add_network_data(self, neutron_network, ironic_network=None):
        """Update default network response with provider network
        info (segmentation_id, etc).
        """
        if not ironic_network:
            ironic_network = db.get_network(neutron_network["id"])
        if ironic_network:
            neutron_network.update(ironic_network.as_dict())
        return neutron_network

    def create_subnet(self, context, subnet):
        return super(IronicPlugin, self).create_subnet(context, subnet)

    def delete_subnet(self, context, id):
        return super(IronicPlugin, self).delete_subnet(context, id)

    def update_subnet(self, context, id, subnet):
        return super(IronicPlugin, self).update_subnet(context, id, subnet)

    def _get_hardware_id_from_port(self, port):
        if "port" not in port:
            port = {"port": port}

        hardware_id = port["port"].get("switch:hardware_id")
        if hardware_id == attr.ATTR_NOT_SPECIFIED:
            hardware_id = None
        return hardware_id   

    def _get_portmaps_from_port(self, port):
        if "port" not in port:
            port = {"port": port}

        portmaps = port["port"].get("switch:portmaps")
        if portmaps == attr.ATTR_NOT_SPECIFIED:
            portmaps = []
        return portmaps

    def _get_commit_from_port(self, port):
        if "port" not in port:
            port = {"port": port}

        commit = port["port"].get("switch:commit")
        if commit == attr.ATTR_NOT_SPECIFIED:
            commit = False
        return commit    

    def _get_ironic_portmaps(self, port, ironic_network):
        """Fetch and validate relevant switchports for a given device_id
        suitable for attaching to the given ironic network.
        """
        hardware_id = self._get_hardware_id_from_port(port)
        LOG.info(
            'Fetching portmaps for hardware_id %s' % (hardware_id))

        if hardware_id:
            # if trunked we will configure all ports, if access only the primary.
            if ironic_network.trunked:
                ironic_portmaps = list(db.filter_portmaps(
                    hardware_id=hardware_id))
            else:
                ironic_portmaps = list(db.filter_portmaps(
                    hardware_id=hardware_id, primary=True))
            return ironic_portmaps
        return []

    def _create_ironic_portmaps(self, port, ironic_network):
        hardware_id = self._get_hardware_id_from_port(port)
        LOG.info('Creating portmaps for hardware_id %s' % (hardware_id))

        portmaps = self._get_portmaps_from_port(port)
        new_portmaps = []

        if portmaps and not hardware_id:
            msg = "Must set switch:hardware_id with switch:portmaps"
            raise n_exc.BadRequest(
                resource="port",
                msg=msg)

        if portmaps:
            # You may only have a maximum of 2 portmaps
            if len(portmaps) > 2:
                msg = ("A maximum of 2 portmaps are allowed, "
                       "%s given" % (len(portmaps)))
                raise n_exc.BadRequest(
                    resource="port",
                    msg=msg)

            # You may only have 1 primary portmap
            is_primary = set([pm["primary"] for pm in portmaps])
            if (len(is_primary) != len(portmaps)) or (True not in is_primary):
                msg = ("Exactly 1 portmap must be primary")
                raise n_exc.BadRequest(
                    resource="port",
                    msg=msg)

            for p in portmaps:
                p["hardware_id"] = hardware_id
                portmap = switch.PortMapController.create_portmap(p)
                new_portmaps.append(portmap)

        return new_portmaps

    def _validate_port(self, ironic_portmaps, port, ironic_network):
        
        switchport_ids = [p.id for p in ironic_portmaps]
        bound_network_ids = []
        if switchport_ids:
            # Fetch all existing networks we are attached to.
            portbindings = list(db.filter_portbindings_by_switch_port_ids(
                [p.id for p in ironic_portmaps]))
            bound_network_ids = [pb.network_id for pb in portbindings]

        # We can't attach to a non-trunked network if the port is already
        # attached to another network.
        if bound_network_ids and (ironic_network.trunked is False):
            msg = ("Cannot attach non-trunked network, port "
                   "already bound to network(s) %s" % (bound_network_ids))
            raise n_exc.BadRequest(
                resource="port",
                msg=msg)

        for bound_network_id in bound_network_ids:

            # We can't attach to the same network again.
            if ironic_network.network_id == bound_network_id:
                msg = ("Already attached to "
                       "network %s" % (ironic_network.network_id))
                raise n_exc.BadRequest(
                    resource="port",
                    msg=msg)

            # We can't attach a trunked network if we are already attached
            # to a non-trunked network.
            bound_network = db.get_network(bound_network_id)
            if not bound_network.trunked:
                msg = ("Already attached to non-trunked "
                       "network %s" % (bound_network_id))
                raise n_exc.BadRequest(
                    resource="port",
                    msg=msg)

    def _get_ironic_network(self, network_id):
        ironic_network = db.get_network(network_id)
        if not ironic_network:
            msg = "No ironic network found for network %s" % (network_id)
            raise n_exc.BadRequest(
                resource="port",
                msg=msg)
        return ironic_network

    def create_port(self, context, port):

        network_id = port["port"]["network_id"]
        ironic_network = self._get_ironic_network(network_id)

        commit = self._get_commit_from_port(port)
        hardware_id = self._get_hardware_id_from_port(port)
        portmaps = self._get_portmaps_from_port(port)

        ironic_portmaps = self._get_ironic_portmaps(port, ironic_network)

        # TODO(morgabra) This obviously won't do anything if there already exist portmaps
        # in the databse for a particular hardware_id.
        if not ironic_portmaps:
            ironic_portmaps = self._create_ironic_portmaps(port, ironic_network)
        
        # throws
        self._validate_port(ironic_portmaps, port, ironic_network)

        port = super(IronicPlugin, self).create_port(context, port)
        ironic_port = db.create_port(port["id"], commit, hardware_id)

        self._add_port_data(port, ironic_port=ironic_port, ironic_portmaps=ironic_portmaps)

        if commit:
            success = self.driver_manager.attach(
                port, ironic_network, ironic_portmaps)

            if not success:
                port_id = port["id"]
                self.delete_port(context, port_id)
                msg = "Failed configuring port: %s" % port_id
                raise n_exc.BadRequest(
                    resource="port",
                    msg=msg)

        return port

    def delete_port(self, context, id):
        port = self.get_port(context, id)
        ironic_network = db.get_network(port['network_id'])

        ironic_portmaps = self._get_ironic_portmaps(port, ironic_network)

        self.driver_manager.detach(port, ironic_network, ironic_portmaps)
        db.delete_port(id)
        return super(IronicPlugin, self).delete_port(context, id)

    def update_port(self, context, id, port):

        port = port.get("port", {})
        old_port = self.get_port(context, id)

        # Don't allow updating hardware_id for a port
        old_hw_id = self._get_hardware_id_from_port(old_port)
        new_hw_id = self._get_hardware_id_from_port(port)
        if new_hw_id:
            if (old_hw_id is not None) and (new_hw_id != old_hw_id): 
                msg = ("Updating switch:hardware_id not supported")
                raise n_exc.BadRequest(
                    resource="port",
                    msg=msg)
            else:
                db.update_port_hardware_id(id, new_hw_id)

        # Don't allow commit True -> False
        # Handle changing admin states
        old_state = self._get_commit_from_port(old_port)
        new_state = self._get_commit_from_port(port)

        if old_state and (new_state is False):
            msg = ("switch:commit True -> False not supported")
            raise n_exc.BadRequest(
                resource="port",
                msg=msg)

        # we want to make sure we add/validate any portmaps that happen
        # to get sent with the update
        old_port.update(port)
        new_port = old_port

        network_id = new_port["network_id"]
        ironic_network = self._get_ironic_network(network_id)
        ironic_portmaps = self._get_ironic_portmaps(new_port, ironic_network)

        if not ironic_portmaps:
            ironic_portmaps = self._create_ironic_portmaps(new_port, ironic_network)
        
        # throws
        self._validate_port(ironic_portmaps, new_port, ironic_network)

        # if we are moving from commit == False -> True,
        # we need to actually push the config to the switch(es)
        if (old_state is False) and (new_state is True):

            LOG.info("Port %s setting commit=True" % id)

            success = self.driver_manager.attach(
                new_port, ironic_network, ironic_portmaps)
            if success:
                db.update_port_commit(new_port["id"], True)
            else:
                port_id = new_port["id"]
                msg = "Failed configuring port: %s" % port_id
                raise n_exc.BadRequest(
                    resource="port",
                    msg=msg)

        updated_port = super(IronicPlugin, self).update_port(context, id, {"port": port})
        self._add_port_data(updated_port, ironic_portmaps=ironic_portmaps)
        return updated_port

    def get_port(self, context, id, fields=None):
        port = super(IronicPlugin, self).get_port(context, id, fields)
        port = self._add_port_data(port)
        return port

    def get_ports(self, context, filters=None, fields=None,
                  sorts=None, limit=None, marker=None,
                  page_reverse=False):
        if 'switch:hardware_id' in filters and filters['switch:hardware_id']:
            ports = db.filter_ports(hardware_id=filters['switch:hardware_id'])
            ports = [self.get_port(context, p.port_id, fields) for p in ports]
        else:
            ports = super(IronicPlugin, self).get_ports(
                context, filters, fields, sorts, limit, marker, page_reverse)
        return [self._add_port_data(p) for p in ports]

    def _add_port_data(self, neutron_port, ironic_port=None, ironic_portmaps=None):
        """Update default port info with plugin-specific
        stuff (switch port mappings, etc).
        """

        if not ironic_port:
            ironic_port = db.get_port(neutron_port["id"])
        
        hardware_id = ironic_port.hardware_id

        if not ironic_portmaps:
            ironic_portmaps = db.filter_portmaps(
                hardware_id=hardware_id)

        ironic_portmaps = [p.as_dict() for p in ironic_portmaps]
        neutron_port.update({"switch:portmaps": ironic_portmaps})
        ironic_port_dict = ironic_port.as_dict()
        ironic_port_dict.pop('port_id')
        neutron_port.update(ironic_port_dict)
        return neutron_port
