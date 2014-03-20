from abc import ABCMeta, abstractmethod
import six

@six.add_metaclass(ABCMeta)
class Driver(object):
    """Define stable abstract interface for ironic neutron plugin hardware drivers."""

    @abstractmethod
    def attach(self, switch_port, vlanid):
        """Realize a neutron port configuration on given physical switch ports."""
        pass

    @abstractmethod
    def detatch(self, switch_port, vlanid):
        """Remove a neutron port configuration on given physical switch ports."""
        pass