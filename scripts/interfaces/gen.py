from jinja2 import Template
import os

"""

"""

def _make_net_info(name, address, netmask, gateway):

    net_info = {'name': name,
                'address': address,
                'netmask': netmask,
                'gateway': gateway,
               }
    return net_info


networks = [
    _make_net_info(name='p9p1', address='50.57.63.10', netmask='255.255.255.128', gateway='50.57.63.1'),
    _make_net_info(name='p9p2', address='10.184.255.138', netmask='255.255.255.128', gateway='10.184.255.129')
]


curr_dir = os.path.dirname(os.path.realpath(__file__))
f = open(os.path.join(curr_dir, "interfaces.template"))
t = f.read()
f.close()

template = Template(t)
print template.render(interfaces=networks)

# Used servers
curl -XPOST localhost:9696/v2.0/ports -H 'Content-Type: application/json' -d '{"port": {"switch:commit": true, "network_id": "11111111-1111-1111-1111-111111111111", "tenant_id": "mytenant", "switch:hardware_id": "e2637cdd-2208-4c37-96ce-246ef7fd3cdb", "switch:portmaps": [{"system_name": "c9-23-1", "port": "Eth1/13", "primary": true}, {"switch_id": "c9-23-2", "port": "Eth1/13", "primary": false}]}}'




curl -XPOST localhost:9696/v2.0/ports -H 'Content-Type: application/json' -d '{"port": {"switch:commit": true, "network_id": "11111111-1111-1111-1111-111111111111", "tenant_id": "mytenant", "switch:hardware_id": "80c94189-1b70-42b7-b827-0c76ad5b6239", "switch:portmaps": [{"system_name": "c9-24-1", "port": "Eth1/14", "primary": true}, {"switch_id": "c9-24-2", "port": "Eth1/14", "primary": false}]}}'

curl -XPOST localhost:9696/v2.0/ports -H 'Content-Type: application/json' -d '{"port": {"switch:commit": true, "network_id": "00000000-0000-0000-0000-000000000000", "tenant_id": "mytenant", "switch:hardware_id": "80c94189-1b70-42b7-b827-0c76ad5b6239", "switch:portmaps": [{"system_name": "c9-24-1", "port": "Eth1/14", "primary": true}, {"switch_id": "c9-24-2", "port": "Eth1/14", "primary": false}]}}'


