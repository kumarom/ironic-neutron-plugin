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

from ironic_neutron_plugin.common import faults
from ironic_neutron_plugin.db import db

from ironic_neutron_plugin.drivers import manager as driver_manager

from neutron.openstack.common import log as logging

LOG = logging.getLogger(__name__)


class IronicPlugin(db_base_plugin_v2.NeutronDbPluginV2):

    __native_bulk_support = False

    supported_extension_aliases = ["provider", "switch"]

    def __init__(self):
        super(IronicPlugin, self).__init__()
        db_api.configure_db()

        self.driver_manager = driver_manager.DriverManager()

        LOG.info('Ironic plugin initialized.')

    def create_network(self, context, network):
        #TODO(morgabra) Actually provision vlan or whatever

        physical_network = network['network'].get('provider:physical_network')
        if not physical_network:
            raise faults.BadRequest(
                explanation='"provider:physical_network" is required')

        network_type = network['network'].get('provider:network_type')
        if not network_type:
            raise faults.BadRequest(
                explanation='"provider:network_type" is required')

        segmentation_id = network['network'].get('provider:segmentation_id')
        if not segmentation_id:
            raise faults.BadRequest(
                explanation='"provider:segmentation_id" is required')

        trunked = network['network'].get('switch:trunked')

        neutron_network = super(IronicPlugin, self).create_network(
            context, network)

        ironic_network = db.create_network(
            neutron_network['id'],
            physical_network=physical_network,
            network_type=network_type,
            segmentation_id=segmentation_id,
            trunked=bool(trunked)
        )
        return self._add_network_data(neutron_network, ironic_network)

    def delete_network(self, context, id):
        # TODO(morgabra) What does this mean? Iterate over every switch
        # and remove the relevant vlan?
        db.delete_network(id)
        return super(IronicPlugin, self).delete_network(context, id)

    def update_network(self, context, id, network):
        # TODO(morgabra) We could probably support metadata updating, but it's
        # really complicated to update a network from under a running config
        raise faults.BadRequest(explanation='Unsupported Operation')

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
            ironic_network = db.get_network(neutron_network['id'])
        if ironic_network:
            neutron_network.update(ironic_network.as_dict())
        return neutron_network

    def create_subnet(self, context, subnet):
        return super(IronicPlugin, self).create_subnet(context, subnet)

    def delete_subnet(self, context, id):
        return super(IronicPlugin, self).delete_subnet(context, id)

    def update_subnet(self, context, id, subnet):
        # TODO(morgabra) We could probably support metadata updating, but it's
        # really complicated to update a subnet from under a running config
        raise faults.BadRequest(explanation='Unsupported Operation')

    def create_port(self, context, port):

        network_id = port['port']['network_id']

        device_id = port['port'].get('device_id')
        if not device_id:
            raise faults.BadRequest(
                explanation='"device_id" is required')

        mac_address = port['port'].get('mac_address')
        if isinstance(mac_address, basestring):
            raise faults.BadRequest(
                explanation='"mac_address" is not allowed')

        ironic_network = db.get_network(network_id)

        if not ironic_network:
            msg = "No ironic network found for network %s" % (network_id)
            raise faults.BadRequest(explanation=msg)

        if ironic_network.trunked:
            ironic_ports = list(db.filter_portmaps(device_id=device_id))
        else:
            ironic_ports = list(db.filter_portmaps(
                device_id=device_id, primary=True))

        if len(ironic_ports) < 1:
            msg = 'No suitable portmap(s) for device "%s" found' % (device_id)
            raise faults.BadRequest(explanation=msg)

        # fetch all existing active networks on this port
        portbindings = list(db.filter_portbindings_by_switch_port_ids(
            [p.id for p in ironic_ports]))
        bound_network_ids = [pb.network_id for pb in portbindings]

        if bound_network_ids and (ironic_network.trunked is False):
            msg = ('Cannot attach non-trunked network, port '
                   'already bound to network(s) %s' % (bound_network_ids))
            raise faults.BadRequest(explanation=msg)

        for bound_network_id in bound_network_ids:

            # Validate we aren't already attached to this network
            if network_id == bound_network_id:
                msg = 'Already attached to network %s' % (network_id)
                raise faults.BadRequest(explanation=msg)

            # Validate this port has only other trunked networks attached
            bound_network = db.get_network(bound_network_id)
            if not bound_network.trunked:
                raise faults.BadRequest(
                    explanation=('Already attached to non-trunked '
                                 'network %s' % (bound_network_id)))

        port = super(IronicPlugin, self).create_port(context, port)
        self._add_port_data(port, ironic_ports)

        self.driver_manager.attach(port, ironic_ports, ironic_network.trunked)
        return port

    def delete_port(self, context, id):
        port = self.get_port(context, id)
        ironic_ports = list(db.filter_portmaps(device_id=port['device_id']))

        ironic_network = db.get_network(port['network_id'])
        trunked = ironic_network.trunked

        self.driver_manager.detach(port, ironic_ports, trunked)
        return super(IronicPlugin, self).delete_port(context, id)

    def update_port(self, context, id, port):
        raise faults.BadRequest(explanation='Unsupported Operation')

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
                device_id=neutron_port['device_id'])
        ironic_ports = [p.as_dict() for p in ironic_ports]
        neutron_port.update({'switch:portmaps': ironic_ports})
        return neutron_port
