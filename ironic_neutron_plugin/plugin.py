from oslo.config import cfg

from neutron.db import db_base_plugin_v2
from neutron.db import api as db_api

from ironic_neutron_plugin.db import models
from ironic_neutron_plugin.db import db
from ironic_neutron_plugin.common import faults

from neutron.openstack.common import log as logging

LOG = logging.getLogger(__name__)


class IronicPlugin(db_base_plugin_v2.NeutronDbPluginV2):

    __native_bulk_support = False

    supported_extension_aliases = ["provider", "switch"]

    def __init__(self):
        super(IronicPlugin, self).__init__()
        db_api.configure_db()
        LOG.info('Ironic plugin initialized.')


    def create_network(self, context, network):
        #TODO(morgabra) Validation
        #TODO(morgabra) Actually provision vlan or whatever
        #TODO(morgabra) This should probably be a single transaction if doable?
        neutron_network = super(IronicPlugin, self).create_network(context, network)

        ironic_network = db.create_network(
            neutron_network['id'],
            physical_network=network['network']['provider:physical_network'],
            network_type=network['network']['provider:network_type'],
            segmentation_id=network['network']['provider:segmentation_id']
        )
        ironic_network = ironic_network.as_dict()
        neutron_network.update(ironic_network)

        return neutron_network

    def delete_network(self, context, id):
        #TODO(morgabra) Delete ironic network also
        return super(IronicPlugin, self).delete_network(context, id)

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

    def _add_network_data(self, neutron_network):
        """Update default network response with provider network info (segmentation_id, etc)"""
        ironic_network = db.get_network(neutron_network['id'])
        neutron_network.update(ironic_network.as_dict())
        return neutron_network

    def create_subnet(self, context, subnet):
        return super(IronicPlugin, self).create_subnet(context, subnet)

    def delete_subnet(self, context, id):
        return super(IronicPlugin, self).delete_subnet(context, id)

    def update_subnet(self, context, id, subnet):
        return super(IronicPlugin, self).update_subnet(context, id, subnet)

    def create_port(self, context, port):

        device_id = port['port'].get('device_id')
        if not device_id:
            raise faults.BadRequest(explanation='"device_id" is required')

        mac_address = port['port'].get('mac_address')
        if not isinstance(mac_address, basestring):
            raise faults.BadRequest(explanation='"mac_address" is required')

        ironic_ports = [p.as_dict() for p in db.filter_portmaps(device_id=device_id)]

        # TODO(morgabra) enforce number of switchports?
        if len(ironic_ports) < 1:
            raise faults.BadRequest(explanation='No portmaps for device "%s" found' % (device_id))

        port = super(IronicPlugin, self).create_port(context, port)
        self._add_port_data(port, ironic_ports)

        # TODO(morgabra) realize port configuration
        return port

    def delete_port(self, context, id):
        return super(IronicPlugin, self).delete_port(context, id)

    def update_port(self, context, id, port):
        return super(IronicPlugin, self).update_port(context, id, port)

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
        """Update default port info with plugin-specific stuff (switch port mappings, etc)"""
        if not ironic_ports:
            ironic_ports = [p.as_dict() for p in db.filter_portmaps(device_id=neutron_port['device_id'])]
        neutron_port.update({'switch:portmaps': ironic_ports})
        return neutron_port


