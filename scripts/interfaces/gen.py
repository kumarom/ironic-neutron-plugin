from jinja2 import Template
import os

"""

"""

def _make_net_info(if_num, address, netmask, gateway):

    net_info = {'if_num': if_num,
                'address': address,
                'netmask': netmask,
                'gateway': gateway,
                'dns': "8.8.8.8 8.8.4.4"
               }
    return net_info


networks = [
    _make_net_info(if_num="0", address='50.57.63.10', netmask='255.255.255.128', gateway='50.57.63.1'),
    _make_net_info(if_num="1", address='10.184.255.138', netmask='255.255.255.128', gateway='10.184.255.129')
]


curr_dir = os.path.dirname(os.path.realpath(__file__))
f = open(os.path.join(curr_dir, "interfaces.template"))
t = f.read()
f.close()

template = Template(t)
print template.render(interfaces=networks)