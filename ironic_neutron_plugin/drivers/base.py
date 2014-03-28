from abc import ABCMeta, abstractmethod
import six

class DriverException(Exception):
    pass

@six.add_metaclass(ABCMeta)
class Driver(object):
    """Define stable abstract interface for ironic neutron plugin hardware drivers."""

    @abstractmethod
    def attach(self, neutron_port, switch_port, trunked):
        """Realize a neutron port configuration on given physical switch ports."""
        pass

    @abstractmethod
    def detach(self, neutron_port, switch_port, trunked):
        """Remove a neutron port configuration on given physical switch ports."""
        pass