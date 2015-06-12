import argparse
import json
import requests


class FixtureException(Exception):
    pass

DECOM_NET = {
    "name": "DECOM",
    "provider:physical_network": "decom",
    "provider:network_type": "vlan",
    "provider:segmentation_id": 50,
    "tenant_id": "mytenant"
}
DECOM_SUBNET = {
    "network_id": None,
    "ip_version": 4,
    "cidr": "10.129.0.0/25",
    "tenant_id": "mytenant"
}

PUB_NET = {
    "name": "PUBLIC-Cust",
    "provider:physical_network": "pubnet",
    "provider:network_type": "vlan",
    "provider:segmentation_id": 301,
    "tenant_id": "mytenant"
}
PUB_SUBNET = {
    "network_id": None,
    "ip_version": 4,
    "cidr": "10.127.104.0/25",
    "tenant_id": "mytenant"
}

SNET_NET = {
    "name": "SNET-Cust",
    "provider:physical_network": "svcnet",
    "provider:network_type": "vlan",
    "provider:segmentation_id": 201,
    "tenant_id": "mytenant"
}
SNET_SUBNET = {
    "network_id": None,
    "ip_version": 4,
    "cidr": "10.128.0.0/25",
    "tenant_id": "mytenant"
}

SWITCH_1 = {
    "id": "switch1",
    "host": "10.127.75.135",
    "username": "admin",
    "password": "admin",
    "type": "cisco"
}
SWITCH_2 = {
    "id": "switch2",
    "host": "10.127.75.136",
    "username": "admin",
    "password": "admin",
    "type": "cisco"
}


def create_network(url, network):
    r = requests.post('%s/v2.0/networks' % url,
                      headers={'Content-Type': 'application/json'},
                      data=json.dumps({'network': network}))

    if r.status_code != 201:
        raise FixtureException('create_network failed: %s' % r.text)

    r = r.json()
    return r['network']['id']


def create_subnet(url, network_id, subnet):
    subnet['network_id'] = network_id
    r = requests.post('%s/v2.0/subnets' % url,
                      headers={'Content-Type': 'application/json'},
                      data=json.dumps({'subnet': subnet}))

    if r.status_code != 201:
        raise FixtureException('create_subnet failed: %s' % r.text)

    r = r.json()
    return r['subnet']['id']


def create_switch(url, switch):
    r = requests.post('%s/v2.0/switches' % url,
                      headers={'Content-Type': 'application/json'},
                      data=json.dumps({'switch': switch}))

    if r.status_code != 200:
        raise FixtureException('create_switch failed: %s' % r.text)

    r = r.json()
    return r['switch']['id']


def create_switchports(url, number, switch_ids):

    def _make_switchport(id, port_no, switch_id):
        return {
            "switch_id": switch_id,
            "hardware_id": "device%s" % (id),
            "name": "eth%s" % str(port_no),
            "port": "Eth1/%s" % str(id),
        }

    switchports = [_make_switchport(number, i, s)
                   for (i, s) in enumerate(switch_ids)]

    r = requests.post('%s/v2.0/switchports' % url,
                      headers={'Content-Type': 'application/json'},
                      data=json.dumps({'switchports': switchports}))

    if r.status_code != 200:
        raise FixtureException('create_switchport failed: %s' % r.text)

    r = r.json()
    return r['switchports']


def main():
    parser = argparse.ArgumentParser(
        description='Add some development fixtures.')
    parser.add_argument('--url', default='http://localhost:9696',
                        help='Neutron URL')

    url = parser.parse_args().url

    for network, subnet in [(DECOM_NET, DECOM_SUBNET),
                            (PUB_NET, PUB_SUBNET),
                            (SNET_NET, SNET_SUBNET)]:

        net_id = create_network(url, network)
        print 'created network %s' % net_id
        subnet_id = create_subnet(url, net_id, subnet)
        print 'created subnet %s' % subnet_id

    switch1_id = create_switch(url, SWITCH_1)
    print 'created switch %s' % switch1_id
    switch2_id = create_switch(url, SWITCH_2)
    print 'created switch %s' % switch2_id

    for i in xrange(5):
        create_switchports(url, i, [switch1_id, switch2_id])
        print 'created switchports for device%s' % i

if __name__ == "__main__":
    main()
