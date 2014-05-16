+--------------------------------------+-------------+------------------------------------------------------+
| id                                   | name        | subnets                                              |
+--------------------------------------+-------------+------------------------------------------------------+
| 81ad7985-36f5-4e3d-bae5-0dbc88bcbc13 | DECOM       | dd3d3c31-0b6b-4daa-9e85-d979f809acf0 10.129.0.0/25   |
| a42e1191-908d-470c-9260-dbbe18003e50 | SNET-Cust   | 95034068-3aa6-40c3-9f0d-7e9b3defa6ec 10.128.0.0/25   |
| 6c829253-fd84-4f76-b4f0-1778d5d29411 | PUBLIC-Cust | 094485c0-7b94-4ec5-9438-2c772ea4a62e 10.127.104.0/25 |
+--------------------------------------+-------------+------------------------------------------------------+


curl -XPOST localhost:9696/v2.0/ports -H 'Content-Type: application/json' -d '{"port": {"commit": true, "trunked": true, "network_id": "6c829253-fd84-4f76-b4f0-1778d5d29411", "tenant_id": "mytenant"]}}'

curl -XPUT localhost:9696/v2.0/ports/5da0bf72-53c9-43d7-b3b7-0e12bad4ae17 -H 'Content-Type: application/json' -d '{"port": {"commit": false}}'

curl -XPOST localhost:9696/v2.0/ports -H 'Content-Type: application/json' -d '{"port": {"commit": true, "trunked": true, "network_id": "6c829253-fd84-4f76-b4f0-1778d5d29411", "tenant_id": "mytenant", "switch:hardware_id": "device21", "switch:ports": [{"switch_id": "switch1", "name": "eth0", "port": "Eth1/21"}, {"switch_id": "switch2", "name": "eth1", "port": "Eth1/21"}]}}'

curl -XPOST localhost:9696/v2.0/ports -H 'Content-Type: application/json' -d '{"port": {"commit": true, "trunked": false, "network_id": "6c829253-fd84-4f76-b4f0-1778d5d29411", "tenant_id": "mytenant", "switch:hardware_id": "device21", "switch:ports": [{"switch_id": "switch1", "name": "eth0", "port": "Eth1/21"}, {"switch_id": "switch2", "name": "eth1", "port": "Eth1/21"}]}}'

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
2. It's a bummer to have to implement yet another driver abstraction layer to actually talk to the hardware. You might be able to pick some parts out of other plugins that are relevant?

Development
===========

Create a Virtualenv
-------------------

0. ```tox -e devenv```
1. ```. devenv/bin/activate```

*NOTE* This can take a while - lots of dependencies.

Create neutron.conf
-----------------

0. ```cp ./etc/neutron.conf.dist ./etc/neutron.conf```
1. ```state_path``` - writable temp dir
2. ```api_extensions_path``` - absolute path to ironic-neutron-pluin/extensions
3. ```[database]``` - writeable mysql db - sqlite:// probably works?
4. ```core_plugin``` - plugin module

Change Switch Credendial Encryption Key
---------------------------------------

Switch credentials are stored encrypted with AES in the datastore.

You must generate your own secret key before using this plugin.

```
python ./scripts/crypto/crypto.py gen_key

Generated AES Key:
5422035f085eae3129cd32955d6e92d7
```

place the output in neutron.conf

```
[ironic]
credential_key = 5422035f085eae3129cd32955d6e92d7
```

Run Neutron Server
------------------
```
# see scripts/neutron-server.sh for an example
neutron-server --config-file /path/to/plugin/etc/neutron.conf
```

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

#### Delete (Not Implemented)
```curl -XDELETE localhost:9696/v2.0/switches/<switch_id>```

PortMap (Extension Object)
--------------------------

Represents a mapping of abstract 'device_id' to a physical switch port.

#### Create
```curl -XPOST localhost:9696/v2.0/portmaps -H 'Content-Type: application/json' -d '{"portmap": {"switch_id": "<switch_id>", "hardware_id": "device", "port": "40", "primary": true}}'```

```curl -XPOST localhost:9696/v2.0/portmaps -H 'Content-Type: application/json' -d '{"portmap": {"system_name": "<switch_id>", "hardware_id": "device", "port_id": "40", "chassis_id": "chassis", "port_description": "port description", "primary": false}}'```

#### Read
```curl localhost:9696/v2.0/portmaps```

```curl localhost:9696/v2.0/portmaps/<portmap_id>```

```curl localhost:9696/v2.0/portmaps?device_id=<device_id>```

#### Delete
```curl -XDELETE localhost:9696/v2.0/portmaps/<portmap_id>```

Network (Neutron Object)
------------------------

Default neutron network object, we additionally make use of the provider network extension.

#### Create
```curl -XPOST localhost:9696/v2.0/networks -H 'Content-Type: application/json' -d '{"network": {"name": "PUBLIC-Cust", "provider:physical_network": "PUBLIC-Cust", "provider:network_type": "vlan", "provider:segmentation_id": 301, "tenant_id": "mytenant", "switch:trunked": true}}'```

```curl -XPOST localhost:9696/v2.0/networks -H 'Content-Type: application/json' -d '{"network": {"name": "SNET-Cust", "provider:physical_network": "SNET-Cust", "provider:network_type": "vlan", "provider:segmentation_id": 201, "tenant_id": "mytenant", "switch:trunked": true}}'```

```curl -XPOST localhost:9696/v2.0/networks -H 'Content-Type: application/json' -d '{"network": {"name": "DECOM", "provider:physical_network": "DECOM", "provider:network_type": "vlan", "provider:segmentation_id": 50, "tenant_id": "mytenant", "switch:trunked": false}}'```

#### Read
```curl localhost:9696/v2.0/networks```

Subnet (Neutron Object)
-----------------------

Default neutron subnet object.

#### Create
```curl -XPOST localhost:9696/v2.0/subnets -H 'Content-Type: application/json' -d '{"subnet": {"network_id": "<PUBLIC_network_id>", "ip_version": 4, "cidr": "10.127.104.0/25", "tenant_id": "mytenant"}}'```

```curl -XPOST localhost:9696/v2.0/subnets -H 'Content-Type: application/json' -d '{"subnet": {"network_id": "<SNET_network_id>", "ip_version": 4, "cidr": "10.128.0.0/25", "tenant_id": "mytenant"}}'```

```curl -XPOST localhost:9696/v2.0/subnets -H 'Content-Type: application/json' -d '{"subnet": {"network_id": "<DECOM_network_id>", "ip_version": 4, "cidr": "10.129.0.0/25", "tenant_id": "mytenant"}}'```

### Read
```curl localhost:9696/v2.0/subnets```

Port (Neutron Object)
---------------------

Default neutron port object. We require device_id be set so we can find which switchports to configure via the PortMap object. Switchport information is returned in the default response.

You can specify portmaps directly in the create request, or ahead of time via the portmap extension, or with an update request as long as the port admin_state_up == False.

'admin_state_up' == True will validate portmaps and push the switch configuration immediately. You can specify False to *not* configure the switch and do it later with an update.

#### Create

```curl -XPOST localhost:9696/v2.0/ports -H 'Content-Type: application/json' -d '{"port": {"commit": true, "trunked": true, "network_id": "<network_id>", "tenant_id": "mytenant", "switch:hardware_id": "device", "switch:portmaps": [{"switch_id": "<switch_id>", "port": 40, "primary": True}, {"switch_id": "<switch_id", "port": 40, "primary": False}]}}'```

```curl -XPOST localhost:9696/v2.0/ports -H 'Content-Type: application/json' -d '{"port": {"switch:commit": false, "network_id": "147907dd-3a6b-40d9-87d8-6a79e9541c98", "tenant_id": "mytenant", "switch:hardware_id": "device0"}}'```

```
curl -XPOST localhost:9696/v2.0/ports -H 'Content-Type: application/json' -d '{"port": {"commit": tb220432fad", "tenant_id": "mytenant", "switch:hardware_id": "device0", "switch:ports": [{"switch_id": "switch1", "port": 40}, {"switch_id": "switch2", "port": 40}]}}'
```

#### Read

```curl localhost:9696/v2.0/ports```

```curl localhost:9696/v2.0/ports?device_id=<device_id>```

#### Update

```curl -XPUT localhost:9696/v2.0/ports/<port_id> -H 'Content-Type: application/json' -d '{"port": {"name": "myport", "admin_state_up": true}}'```

```curl -XPUT localhost:9696/v2.0/ports/<port_id> -H 'Content-Type: application/json' -d '{"port": {"switch:portmaps": [{"system_name": "switch1", "port_id": "Eth1/40", "primary": True}, {"system_name": "switch2", "port_id": "Eth1/40", "primary": False}]}}'```

#### Delete

```curl -XDELETE localhost:9696/v2.0/ports/<port_id>```

NX-OS Crash Course
==================

show running interface ethernet 1/40

show running interface port-channel 40

show ip dhcp snooping binding

Config Reference
================

```
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
```




