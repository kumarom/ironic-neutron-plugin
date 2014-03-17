from sqlalchemy.orm import exc

from neutron.db import api as db_api
from neutron.openstack.common import log as logging

from ironic_neutron_plugin.db import models

LOG = logging.getLogger(__name__)


def create_portmap(switch_id, device_id, port):
    session = db_api.get_session()

    with session.begin(subtransactions=True):
        portmap = models.IronicSwitchPort(
                    switch_id=switch_id,
                    device_id=device_id,
                    port=port)
        session.add(portmap)
        return portmap


def get_all_portmaps():
    session = db_api.get_session()
    return (session.query(models.IronicSwitchPort).all())


def get_portmap(portmap_id):
    session = db_api.get_session()

    try:
        return (session.query(models.IronicSwitchPort).
                get(portmap_id))
    except exc.NoResultFound:
        return None


def filter_portmaps(**kwargs):

    session = db_api.get_session()
    return (session.query(models.IronicSwitchPort).
            filter_by(**kwargs))


def delete_portmap(portmap_id):
    session = db_api.get_session()
    portmap = session.query(models.IronicSwitchPort).get(portmap_id)
    session.delete(portmap)
    session.flush()
    return True


def create_switch(switch_ip, username, password, switch_type):
    session = db_api.get_session()

    with session.begin(subtransactions=True):
        switch = models.IronicSwitch(
                    ip=switch_ip,
                    username=username,
                    password=password,
                    type=switch_type)
        session.add(switch)
        return switch


def get_switch(switch_id):
    session = db_api.get_session()

    try:
        return (session.query(models.IronicSwitch).
                get(switch_id))
    except exc.NoResultFound:
        return None


def filter_switches(**kwargs):

    session = db_api.get_session()
    return (session.query(models.IronicSwitch).
            filter_by(**kwargs))


def get_all_switches():
    session = db_api.get_session()
    return (session.query(models.IronicSwitch).all())


def delete_switch(switch_id):
    session = db_api.get_session()
    switch = session.query(models.IronicSwitch).get(switch_id)
    session.delete(switch)
    session.flush()
    return True


def get_network(network_id):
    session = db_api.get_session()
    try:
        return (session.query(models.IronicNetwork).
                get(network_id))
    except exc.NoResultFound:
        return None


def create_network(network_id, physical_network=None,
                   segmentation_id=None, network_type=None):
    session = db_api.get_session()

    with session.begin(subtransactions=True):
        network = models.IronicNetwork(
                    network_id=network_id,
                    physical_network=physical_network,
                    segmentation_id=segmentation_id,
                    network_type=network_type)
        session.add(network)
        return network
