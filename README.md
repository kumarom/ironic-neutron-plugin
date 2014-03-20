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
```curl -XPOST localhost:9696/v2.0/portmaps -H 'Content-Type: application/json' -d '{"portmap": {"switch_id": "<switch_id>", "device_id": "device", "port": "Ethernet1/40"}}'```

#### Read
```curl localhost:9696/v2.0/portmaps```

```curl localhost:9696/v2.0/portmaps/<portmap_id>```

```curl localhost:9696/v2.0/portmaps?device_id=<device_id>```

#### Update
```curl -XPUT localhost:9696/v2.0/portmaps -H 'Content-Type: application/json' -d '{"portmap": {"port": "1/2"}}'```

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
````curl -XPOST localhost:9696/v2.0/subnets -H 'Content-Type: application/json' -d '{"subnet": {"network_id": "<network_id>", "ip_version": 4, "cidr": "10.127.104.1/25", "tenant_id": "mytenant"}}'```

### Read
```curl localhost:9696/v2.0/subnets```

#### Update

#### Delete

Port (Neutron Object)
---------------------

Default neutron port object. We require mac_address and device_id be set so we can find which switchports to configure via the PortMap object. Switchport information is returned in the default response.

#### Create

```curl -XPOST localhost:9696/v2.0/ports -H 'Content-Type: application/json' -d '{"port": {"network_id": "<network_id>", "tenant_id": "mytenant", "mac_address": "aa:aa:aa:aa:aa:aa", "device_id": "<device_id>"}}'```

#### Read

```curl localhost:9696/v2.0/ports```
```curl localhost:9696/v2.0/ports?device_id=<device_id>```

#### Update

#### Delete





