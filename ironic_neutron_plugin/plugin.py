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
from neutron.db import db_base_plugin_v2

from ironic_neutron_plugin.db import db
from ironic_neutron_plugin.drivers import manager
from ironic_neutron_plugin.extensions import switch

from neutron.common import exceptions as n_exc
from neutron.openstack.common import log as logging

import six

LOG = logging.getLogger(__name__)


class IronicPlugin(db_base_plugin_v2.NeutronDbPluginV2):

    __native_bulk_support = False
    __native_pagination_support = False
    __native_sorting_support = True

    supported_extension_aliases = ["provider", "switch"]

    def __init__(self):
        super(IronicPlugin, self).__init__()
        db_api.configure_db()

        self.driver_manager = manager.DriverManager()

        LOG.info("Ironic plugin initialized.")

    def _validate_network_extensions(self, network):

        physical_network = network["network"].get("provider:physical_network")
        if not isinstance(physical_network, six.string_types):
            raise n_exc.BadRequest(
                resource="network",
                msg="'provider:physical_network' is required")

        network_type = network["network"].get("provider:network_type")
        if not isinstance(network_type, six.string_types):
            raise n_exc.BadRequest(
                resource="network",
                msg="'provider:network_type' is required")

        segmentation_id = network["network"].get("provider:segmentation_id")
        if not isinstance(segmentation_id, six.integer_types):
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

        # Parse out and validate all the network extension data we
        # expect to see.
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
        # TODO(morgabra) What does this mean? Iterate over every switch
        # and remove the relevant vlan?
        res = super(IronicPlugin, self).delete_network(context, id)
        db.delete_network(id)
        return res

    def update_network(self, context, id, network):
        raise n_exc.BadRequest(
            resource="network",
            msg="update not supported")

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

    def _get_ironic_ports(self, port, ironic_network):
        """Fetch and validate relevant switchports for a given device_id
        suitable for attaching to the given ironic network.

        TODO(morgabra) This is horrible: it's a nice feature to be able to
        specify portmaps with the create_port() request but it conflicts with
        pre-setting the portmaps via the switch extension, resulting in 2 code
        paths for pretty much the same thing.
        """
        LOG.info(
            'Fetching portmaps for device %s' % (port["port"]["device_id"]))

        device_id = port["port"]["device_id"]

        # if trunked we will configure all ports, if access only the primary.
        if ironic_network.trunked:
            ironic_ports = list(db.filter_portmaps(
                device_id=device_id))
        else:
            ironic_ports = list(db.filter_portmaps(
                device_id=device_id, primary=True))

        if not ironic_ports:
            # create portmaps
            ironic_ports = self._create_ironic_ports(port, ironic_network)
        else:
            # if we are given portmaps in the request but some already exist
            # in the db, assert that they match
            portmaps = port["port"]["switch:portmaps"]
            for pm in portmaps:
                pm["device_id"] = device_id

            if portmaps:
                for p in ironic_ports:
                    p = p.as_dict()
                    p.pop('id')
                    if p not in portmaps:
                        portmap_ids = ','.join(
                            [pm.id for pm in ironic_ports])
                        msg = (
                            "Given portmap(s) do not match existing "
                            "portmap(s) with id(s): %s" % (portmap_ids)
                        )
                        raise n_exc.BadRequest(
                            resource="port",
                            msg=msg)

        return self._validate_ironic_ports(ironic_ports, port, ironic_network)

    def _create_ironic_ports(self, port, ironic_network):

        device_id = port["port"]["device_id"]
        LOG.info('Creating portmaps for device %s' % (device_id))

        portmaps = port["port"]["switch:portmaps"]

        # You may only have a maximum of 2 portmaps
        # TODO(morgabra) Limiting to 2 is probably not necessary
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

        # TODO(morgabra) - This is gross. We should probably move
        # the validation in the method to db.create_portmap() instead,
        # which would stop us from using a classmethod of another random
        # controller.
        new_portmaps = []
        for p in portmaps:
            p["device_id"] = device_id
            portmap = switch.PortMapController.create_portmap(p)
            new_portmaps.append(portmap)

        return new_portmaps

    def _validate_ironic_ports(self, ironic_ports, port, ironic_network):

        # Fetch all existing networks we are attached to.
        portbindings = list(db.filter_portbindings_by_switch_port_ids(
            [p.id for p in ironic_ports]))
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

        return ironic_ports

    def create_port(self, context, port):

        device_id = port["port"].get("device_id")
        if not device_id:
            raise n_exc.BadRequest(
                resource="port",
                msg="'device_id' is required")

        network_id = port["port"]["network_id"]
        ironic_network = db.get_network(network_id)

        if not ironic_network:
            msg = "No ironic network found for network %s" % (network_id)
            raise n_exc.BadRequest(
                resource="port",
                msg=msg)

        ironic_ports = self._get_ironic_ports(port, ironic_network)

        port = super(IronicPlugin, self).create_port(context, port)
        self._add_port_data(port, ironic_ports)

        self.driver_manager.attach(port, ironic_network, ironic_ports)
        return port

    def delete_port(self, context, id):
        port = self.get_port(context, id)
        ironic_ports = list(db.filter_portmaps(device_id=port['device_id']))

        ironic_network = db.get_network(port['network_id'])

        self.driver_manager.detach(port, ironic_network, ironic_ports)
        return super(IronicPlugin, self).delete_port(context, id)

    def update_port(self, context, id, port):
        raise n_exc.BadRequest(
            resource="port",
            msg="update not supported")

    def get_port(self, context, id, fields=None):
        port = super(IronicPlugin, self).get_port(context, id, fields)
        port = self._add_port_data(port)
        return port

    def get_ports(self, context, filters=None, fields=None,
                  sorts=None, limit=None, marker=None,
                  page_reverse=False):
        ports = super(IronicPlugin, self).get_ports(
            context, filters, fields, sorts, limit, marker, page_reverse)
        return [self._add_port_data(p) for p in ports]

    def _add_port_data(self, neutron_port, ironic_ports=None):
        """Update default port info with plugin-specific
        stuff (switch port mappings, etc).
        """
        if not ironic_ports:
            ironic_ports = db.filter_portmaps(
                device_id=neutron_port["device_id"])
        ironic_ports = [p.as_dict() for p in ironic_ports]
        neutron_port.update({"switch:portmaps": ironic_ports})
        return neutron_port
