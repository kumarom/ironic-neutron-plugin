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

This is a (likely) extremely misguided attempt at a proof of concept neutron plugin that works with ironic
(or really any bare-metal environment).

Added features/extensions:

1. physical switch/credential management
2. a mapping of a new attribute "hardware_id" to physical switch(es)/port(s)
4. "trunked" flag on port objects, which is passed through to the mechanism to determine how to configure the ToR
3. "commit" flag on port objects - allowing you to push/remove ToR configurations separately from the neutron port object

In short, instead of agents plugging virtual ports, we keep a map of physical switchports to an abstract "hardware_id" and call a second driver layer that configures the switchport and adds/removes relevant vlans.


Notes/Open Questions/TODO
=========================

1. We have to subclass the Ml2 plugin because there is no way to load extensions. (Even if there was, the request body isn't passed to the mechanism and the returned objects do not include extension fields.)
2. If the above were fixed, we could push the switchport mapping and other extension logic into the mechanism, which would make this much easier to maintain.
3. Alternatively, the features we need could be merged upstream in some capacity.

Development
===========

Create a Virtualenv
-------------------

0. ```tox -e devenv```
1. ```. devenv/bin/activate```

Create neutron.conf
-------------------

0. ```cp ./etc/neutron.conf.dist ./etc/neutron.conf```

Edit neutron.conf
-----------------

At a minium, you'll need to change the following:

```
[DEFAULT]
api_extensions_path = <absolute path to the extensions dir - ex: /path/to/ironic-neutron-plugin/ironic_neutron_plugin/extensions>
log_dir = <absolute path to your log directory - ex: /path/to/ironic-neutron-plugin/logs>

[database]
connection = <mysql connection - ex: mysql://neutron_user:password@127.0.0.1:3306/neutron>

[ml2_type_vlan]
network_vlan_ranges = <comma-separated provider-network names (ex: net1,net2)>
```

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
export PYTHONPATH=$PYTHONPATH:/path/to/ironic-neutron-plugin
neutron-server --config-file /path/to/ironic-neutron-plugin/etc/neutron.conf
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

Represents a single physical switch, including management credentials. Has a relationship with 'SwitchPort', which maps an abstract 'hardware_id' to a port on the switch.

'type' will determine which driver is used to configure the switch, currently only 'cisco' is implemented (and only halfway tested with a 3172)

#### Create
```curl -XPOST localhost:9696/v2.0/switches -H 'Content-Type: application/json' -d '{"switch": {"id": "<some_unique_id>", "host": "10.0.0.1", "username": "user", "password": "pass", "type": "cisco"}}'```

```curl -XPOST localhost:9696/v2.0/switches -H 'Content-Type: application/json' -d '{"switch": {"id": "<some_unique_id>", "host": "10.0.0.2", "username": "user", "password": "pass", "type": "cisco"}}'```

#### Read
```curl localhost:9696/v2.0/switches```

```curl localhost:9696/v2.0/switches/<switch_id>```

#### Delete (Not Implemented)
```curl -XDELETE localhost:9696/v2.0/switches/<switch_id>```

SwitchPorts (Extension Object)
--------------------------

Represents a mapping of abstract 'hardware_id' to a physical switch port.

'hardware_id' is anything that uniquely itentifies a set of physical network interfaces. Note that the *instance* id is used in the device_id field by nova, which doesn't help us when we want to maintain a persistent mapping of devices.

#### Create
```curl -XPOST localhost:9696/v2.0/portmaps -H 'Content-Type: application/json' -d '{"switchports": [{"switch_id": "<switch_id>", "hardware_id": "device", "port": "Eth1/1", "name": eth0}, {"switch_id": "<switch_id>", "hardware_id": "device", "port": "Eth1/1", "name": eth1}}'```

#### Read
```curl localhost:9696/v2.0/switchports```

```curl localhost:9696/v2.0/switchports/<hardware_id>```

```curl localhost:9696/v2.0/switchports?hardware_id=<hardware_id>```

#### Delete
```curl -XDELETE localhost:9696/v2.0/switchports/<hardware_id>```

Network (Neutron Object)
------------------------

Default neutron network object.

The value of 'provider:physical_network' must be listed in the 'network_vlan_ranges' option in the config file.
If you are trying tenant networks, make sure you set vlan ranges in the 'network_vlan_ranges' option in the config file.

#### Create
```curl -XPOST localhost:9696/v2.0/networks -H 'Content-Type: application/json' -d '{"network": {"name": "PUBLIC-Cust", "provider:physical_network": "public", "provider:network_type": "vlan", "provider:segmentation_id": 301, "tenant_id": "mytenant"}}'```

```curl -XPOST localhost:9696/v2.0/networks -H 'Content-Type: application/json' -d '{"network": {"name": "SNET-Cust", "provider:physical_network": "private", "provider:network_type": "vlan", "provider:segmentation_id": 201, "tenant_id": "mytenant"}}'```

#### Read
```curl localhost:9696/v2.0/networks```

Subnet (Neutron Object)
-----------------------

Default neutron subnet object.

#### Create
```curl -XPOST localhost:9696/v2.0/subnets -H 'Content-Type: application/json' -d '{"subnet": {"network_id": "<PUBLIC_network_id>", "ip_version": 4, "cidr": "10.127.104.0/25", "tenant_id": "mytenant"}}'```

```curl -XPOST localhost:9696/v2.0/subnets -H 'Content-Type: application/json' -d '{"subnet": {"network_id": "<PRIVATE_network_id>", "ip_version": 4, "cidr": "10.128.0.0/25", "tenant_id": "mytenant"}}'```

### Read
```curl localhost:9696/v2.0/subnets```

Port (Neutron Object)
---------------------

Mostly default neutron port object, which some extra extensions:

#### Create

By default, both 'commit' and 'trunked' are false. You may create a port at any time without any extra extension information at all and the model will be created, however no configuration of the ToR will occur.

Before you can 'commit' the configuration to the switch(es), you must provide a hardware_id to the port that has suitable portmappings.

As a convenience, you can include switchports in the create_port request, which will either create or update the port mappings for the given hardware_id.

You will also want to ensure that 'trunked' is set properly. Ultimately it's up to the mechanism to decide what to do with it, but in the case of the existing 'cisco' mech, the port(s) will be configured differently (either 'trunked' or 'access') based on the value of this flag.

## Creating and Committing

The following will create a port and commit the configuration immediately as all the required elements are available and commit=true.

```
curl -XPOST localhost:9696/v2.0/ports -H 'Content-Type: application/json' -d '{"port": {"commit": true, "trunked": true, "network_id": "<network_uuid>", "tenant_id": "mytenant", "switch:hardware_id": "device21", "switch:ports": [{"switch_id": "switch1", "name": "eth0", "port": "Eth1/21"}, {"switch_id": "switch2", "name": "eth1", "port": "Eth1/21"}]}}'
```

The following will create the port object but not push the configuration.

```
curl -XPOST localhost:9696/v2.0/ports -H 'Content-Type: application/json' -d '{"port": {"commit": false, "trunked": true, "network_id": "<network_uuid>", "tenant_id": "mytenant", "switch:hardware_id": "device21", "switch:ports": [{"switch_id": "switch1", "name": "eth0", "port": "Eth1/21"}, {"switch_id": "switch2", "name": "eth1", "port": "Eth1/21"}]}}'
```

You might then, at a later time, commit the configuration.
```
curl -XPUT localhost:9696/v2.0/ports/<port_uuid> -H 'Content-Type: application/json' -d '{"port": {"commit": true}}'
```

You can specify very little information at port-create time.
```
curl -XPOST localhost:9696/v2.0/ports -H 'Content-Type: application/json' -d '{"port": {"network_id": "<network_uuid>", "tenant_id": "mytenant"}}'
```

And add it and push the config later with an update.
```
curl -XPUT localhost:9696/v2.0/ports/<port_uuid> -H 'Content-Type: application/json' -d '{"port": {"commit": true, "trunked": false, "switch:hardware_id": "device21", "switch:ports": [{"switch_id": "switch1", "name": "eth0", "port": "Eth1/21"}, {"switch_id": "switch2", "name": "eth1", "port": "Eth1/21"}]}}'
```

Caveats:
1. Portmaps may not be updated if they are in use with an active configuration.
2. You may have multiple ports with conflicting configuration options (trunked true and false, for example) but you may not commit both at the same time. fcfs

#### Read

```curl localhost:9696/v2.0/ports```

```curl localhost:9696/v2.0/ports?hardware_id=<hardware_id>```

#### Update

```
curl -XPUT localhost:9696/v2.0/ports/<port_uuid> -H 'Content-Type: application/json' -d '{"port": {"commit": true}}'
```

#### Delete

```curl -XDELETE localhost:9696/v2.0/ports/<port_id>```