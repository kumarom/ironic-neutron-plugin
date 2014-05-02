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

import abc
import six


class DriverException(Exception):
    pass


@six.add_metaclass(abc.ABCMeta)
class Driver(object):
    """Define stable abstract interface for ironic neutron plugin
    hardware drivers.
    """

    @abc.abstractmethod
    def create(self, port_info):
        """Create base configuration for a previously unconfigured
        port. This will be called in place of attach() the first
        time you attach a network to a physical switchport.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def delete(self, port_info):
        """Remove all configuration for a previously configured
        port. This will be called instead of detach() when removing
        the last network from a physical switchport.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def attach(self, port_info):
        """Attach an additional network to a physical switchport."""
        raise NotImplementedError

    @abc.abstractmethod
    def detach(self, port_info):
        """Remove a network from a physical switchport."""
        raise NotImplementedError


class PortInfo(object):
    """Instead of leaking the database models into the drivers, we
    make a standard interface instead and set it up in the driver
    manager before actually calling attach()/detach().
    """

    def __init__(self, switch_ip, switch_username, switch_password,
                 hardware_id, interface, vlan_id, ip, mac_address, trunked):
        self.switch_ip = switch_ip,
        self.switch_username = switch_username,
        self.switch_password = switch_password,
        self.hardware_id = hardware_id
        self.interface = interface
        self.vlan_id = vlan_id
        self.ip = ip
        self.mac_address = mac_address
        self.trunked = trunked


class DummyDriver(Driver):

    def create(self, port_info):
        pass

    def delete(self, port_info):
        pass

    def attach(self, port_info):
        pass

    def detach(self, port_info):
        pass
