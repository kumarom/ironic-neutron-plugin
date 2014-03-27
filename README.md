ironic-neutron-plugin
=====================

This is a (likely) extremely misguided attempt at a proof of concept neutron plugin that is suitable
for managing an ironic deployment.

This driver currently only handles configuring the ToR(s) to allow a device on a few pre-defined VLANs.

This requires a few neutron api extensions:
1. switch/credential management
2. a mapping of device_id to physical switch(es)/port(s).

This is very much not usable long-term, as it's probably a bad idea and/or we'll have to integrate this
into a real plugin.

Notes/Open Questions
====================
1. An ml2 driver seems like it exposes enough functionality for us if we are only playing with ToRs. The major issue is there doesn't seem to be a clean way to hook into loading custom extensions, but this might be a bad idea anyway to maintain a portmap in neutron.
2. A lot of the implementation details for configuring cisco stuff was copied from the neutron repo. As far as I can tell there doesn't exist sufficient abstraction to support the create_port() behavior we want but still use the existing vendor mechanism drivers. (At least not without a lot of hacking) I'm not sure what the long-term solution should be, but for now we'll likely have to implement yet another driver abstraction layer for the hardware we need to support.

Development
===========

Get Neutron
-----------
1. ```git clone git@github.com:openstack/neutron.git```

Get Dependencies
----------------
0. ```pip install virtualenv```
1. ```virtualenv devenv```
2. ```. devenv/bin/activate```
3. ```pip install -r requirements.txt```
4. ```pip install mysql-python```

Make a Start Script
-------------------
```
import sys

from neutron.server import main

if __name__ == "__main__":
    sys.exit(main())
```

Edit neutron.conf
-----------------
0. A suitable template is located @ ironic-neutron-plugin/etc/neutron/neutron.conf
1. ```state_path``` - writable temp dir
2. ```api_extensions_path``` - absolute path to ironic-neutron-pluin/extensions
3. ```[database]``` - writeable mysql db - sqlite:// probably works?
4. ```core_plugin``` - *IMPORTANT* this must be on your pythonpath, so neutron can find our plugin

Run Neutron Server
------------------
```python /path/to/start_script.py --config-file /path/to/neutron.conf --config-dir /path/to/neutron.git/etc```


Deployment
==========
1. Install neutron however you might do that in a production setting
2. Make ironic-neutron-plugin available on your pythonpath
3. Edit neutron.conf/core_plugin (see 'Development')

API
===

*NOTE* If you happen to have authentication enabled, you need to get a token from keystone and include it in the 'X-Auth-Token' header. You can then omit tenant_id when creating objects.

Concepts
--------

By default neutron 'port' objects are actually logical ports that a host agent (openvswitch, etc) on a physical host realizes for it's virtual guests.

The core feature of this plugin is that a neutron 'port' now directly correlates to granting a physical host access to a particular network segment. (Currently, this just adds some allowed vlans to ports on ToR(s))

To facilitate this, we had to add some extra objects: Switches and PortMaps.

Switch (Extenstion Object)
--------------------------

Represents a single physical switch, including management credentials. Has a relationship with 'PortMap', which maps an abstract 'device_id' to a port on the switch.

#### Create
```curl -XPOST localhost:9696/v2.0/switches -H 'Content-Type: application/json' -d '{"switch": {"ip": "10.127.75.135", "username": "user", "password": "pass", "type": "cisco"}}'```

```curl -XPOST localhost:9696/v2.0/switches -H 'Content-Type: application/json' -d '{"switch": {"ip": "10.127.75.136", "username": "user", "password": "pass", "type": "cisco"}}'```

#### Read
```curl localhost:9696/v2.0/switches```

```curl localhost:9696/v2.0/switches/<switch_id>```

#### Update (Not Implemented)
```curl -XPOST localhost:9696/v2.0/switches -H 'Content-Type: application/json' -d '{"switch": {"password": "new_password"}}'```

#### Delete (Not Implemented)
```curl -XDELETE localhost:9696/v2.0/switches/<switch_id>```

PortMap (Extension Object)
--------------------------

Represents a mapping of abstract 'device_id' to a physical switch port.

#### Create
```curl -XPOST localhost:9696/v2.0/portmaps -H 'Content-Type: application/json' -d '{"portmap": {"switch_id": "<switch_id>", "device_id": "device", "port": "1/40", "mac_address": "aa:aa:aa:aa:aa:aa"}}'```

#### Read
```curl localhost:9696/v2.0/portmaps```

```curl localhost:9696/v2.0/portmaps/<portmap_id>```

```curl localhost:9696/v2.0/portmaps?device_id=<device_id>```

#### Update

#### Delete
```curl -XDELETE localhost:9696/v2.0/portmaps/<portmap_id>```

Network (Neutron Object)
------------------------

Default neutron network object, we additionally make use of the provider network extension.

#### Create
```curl -XPOST localhost:9696/v2.0/networks -H 'Content-Type: application/json' -d '{"network": {"name": "PUBLIC-Cust", "provider:physical_network": "PUBLIC-Cust", "provider:network_type": "vlan", "provider:segmentation_id": 301, "tenant_id": "mytenant"}}'```

#### Read
```curl localhost:9696/v2.0/networks```

#### Update

#### Delete

Subnet (Neutron Object)
-----------------------

Default neutron subnet object.

#### Create
```curl -XPOST localhost:9696/v2.0/subnets -H 'Content-Type: application/json' -d '{"subnet": {"network_id": "<network_id>", "ip_version": 4, "cidr": "10.127.104.0/25", "tenant_id": "mytenant"}}'```

### Read
```curl localhost:9696/v2.0/subnets```

#### Update

#### Delete

Port (Neutron Object)
---------------------

Default neutron port object. We require mac_address and device_id be set so we can find which switchports to configure via the PortMap object. Switchport information is returned in the default response.

#### Create

```curl -XPOST localhost:9696/v2.0/ports -H 'Content-Type: application/json' -d '{"port": {"network_id": "<network_id>", "tenant_id": "mytenant", "device_id": "<device_id>"}}'```

#### Read

```curl localhost:9696/v2.0/ports```
```curl localhost:9696/v2.0/ports?device_id=<device_id>```

#### Update

#### Delete

NX-OS Crash Course
------------------
show running interface ethernet 1/40
show running interface port-channel 40
show ip dhcp snooping binding

Config
------

"""
Config Templates:
Notes:
TOR1 and TOR2 are A and B side switches.
VPC port-channel is a multi-chassis etherchannel spanning across 2 switches to one host by the switches utilizing the same bundle-ID.

<pub_ip> - Public IP address
<pub_mask> - Pulic Subnet Mask
<pub_mac> - Public Bond MAC interface

<snet_ip> - ServiceNet IP address
<snet_mask> - ServiceNet Subnet Mask
<snet_mac> - ServicNet Bond MAC Address

<pub_vlan> - Public VLAN Number
<snet_vlan> - Servicenet VLAN number
<prov_vlan> - Provisioning VLAN number

<svr_int1>  - First Server Interface
<svr_int2>  - Second Server Interface

<sw_int> - Switch Interface (doubles as port-channel/VPC identifiers)


----------------------------------------------------------

Production - Trunk allowing <pub_vlan>/<snet_vlan> on LACP VPC port-channel.

TOR1/TOR2:

interface port-channel<sw_int>
  description CUST<y>-host
  switchport mode trunk
  switchport trunk allowed vlan <pub_vlan>,<snet_vlan>
  spanning-tree port type edge trunk
  vpc <sw_int>
  no shutdown

interface Ethernet1/<sw_int>
  description CUST<Y>-host
  switchport mode trunk
  switchport trunk allowed vlan <pub_vlan>,<snet_vlan>
  spanning-tree port type edge trunk
  channel-group <sw_int> mode active
  no shutdown


----------------------------------------------------------

Pre/Post Prod - Access port <prov_vlan> on TOR1 only. TOR2 interface shutdown.

TOR1:
 interface Ethernet1/<sw_int>
 description CUST<Y>-host
 switchport mode access
 switchport access vlan <prov_vlan>
 spannning-tree port type edge
 no shutdown

TOR2:
 interface Ethernet1/<sw_int>
 shutdown

----------------------------------------------------------

IP Binding Config(global configuration):

ip source binding <pub_ip> <pub_mac> vlan <pub_vlan> interface port-channel<sw_int>
ip source binding <snet_ip> <snet_mac> vlan <snet_vlan> interface port-channel<sw_int>


----------------------------------------------------------
Host Configuration:

auto <svr_int1>
iface <svr_int1> inet manual
bond-master bond0

auto <svr_int2>
iface <svr_int2> inet manual
bond-master bond0

auto bond0
iface bond0 inet manual
bond-mode 4
bond-miimon 100
bond-lacp-rate 1
bond-slaves <svr_int1> <svr_int2>

auto bond0.<pub_vlan>
iface bond0.<pub_vlan> inet static
vlan_raw_device bond0
address <pub_ip>
netmask <pub_mask>
hwaddress ether <pub_mac>

auto bond0.<snet_vlan>
iface bond0.<snet_vlan> inet static
vlan_raw_device bond0
address <snet_ip>
netmask <snet_mask>
hwaddress ether <snet_mac>

----------------------------------------------------------
----------------------------------------------------------

Example Configuration:
In this configuration the host is on port ethernet1/5 of the TORs.

<pub_ip> - 192.168.1.1
<pub_mask> - 255.255.255.0
<pub_mac> - 90:e2:ba:56:64:54

<snet_ip> - 10.127.1.1
<snet_mask> - 255.255.255.0
<snet_mac> - 90:e2:ba:56:64:55

<pub_vlan> - 201
<snet_vlan> - 301

<svr_int1>  - eth0
<svr_int2>  - eth1

<sw_int> - 5

----------------------------------------------------------
Switch:
ip source binding 192.168.1.1 90:e2:ba:56:64:54 vlan 201 interface port-channel5
ip source binding 10.127.1.1 90:e2:ba:56:64:55 vlan 301 interface port-channel5

TOR1/TOR2:

interface port-channel5
  description CUST-host
  switchport mode trunk
  switchport trunk allowed vlan 201,301
  spanning-tree port type edge trunk
  vpc 5
  no shutdown

interface Ethernet1/5
  description CUST<Y>-host
  switchport mode trunk
  switchport trunk allowed vlan 201,301
  spanning-tree port type edge trunk
  channel-group 5 mode active
  no shutdown



----------------------------------------------------------
Host:

auto eth0
iface eth0 inet manual
bond-master bond0

auto eth1
iface eth1 inet manual
bond-master bond0

auto bond0
iface bond0 inet manual
bond-mode 4
bond-miimon 100
bond-lacp-rate 1
bond-slaves eth0 eth1

auto bond0.201
iface bond0.201 inet static
vlan_raw_device bond0
address 192.168.1.1
netmask 255.255.255.0
hwaddress ether 90:e2:ba:56:64:54

auto bond0.301
iface bond0.301 inet static
vlan_raw_device bond0
address 10.127.1.1
netmask 255.255.255.0
hwaddress ether 90:e2:ba:56:64:55

----------------------------------------------------------
"""




