def _configure():
    return ['configure terminal']

def _configure_interface(type, interface):
    return (
        _configure() +
        ['interface %s %s' % (type, interface)]
    )

# shared port-channel/ethernet interface configuration for trunked interfaces
def _base_trunked_configuration(device_id, interface, vlan_id):
    return [
        'description CUST%s-host' % device_id,
        'switchport mode trunk',
        'switchport trunk allowed vlan %s' % vlan_id,
        'spanning-tree port type edge trunk',
        'no shutdown'
    ]

# shared port-channel/ethernet interface configuration for access interfaces
def _base_access_configuration(device_id, interface, vlan_id):
    return [
        'description CUST%s-host' % device_id,
        'switchport mode access',
        'switchport access vlan %s' % vlan_id,
        'spanning-tree port type edge',
        'no shutdown'
    ]

def _add_vpc(interface):
    return [
        'vpc %s' % interface,
    ]

def _add_channel_group(interface):
    return [
        'channel-group %s mode active' % interface,
    ]

def _bind_ip(ip, mac_address, vlan_id, interface):
    return (
        _configure() +
        ['ip source binding %s %s vlan %s interface port-channel%s' % (ip, mac_address, vlan_id, interface)]
    )

def _unbind_ip(ip, mac_address, vlan_id, interface):
    return (
        _configure() +
        ['no ip source binding %s %s vlan %s interface port-channel%s' % (ip, mac_address, vlan_id, interface)]
    )

def _shutdown_port_channel_interface(interface):
    return (
        _configure() +
        ['no interface port-channel %s' % (interface)]
    )

# TODO(morgabra) We actually need to clear settings here, but I'm not sure how to do that, for now
# if you switch between an access port and a trunked port it will break.
def _shutdown_ethernet_interface(interface):
    return (
        _configure_interface('ethernet', '1/%s' % (interface)) +
        ['shutdown']
    )

def show_interface_configuration(type, interface):
    return ['show running interface %s %s' % (type, interface)]

def create_port(device_id, interface, vlan_id, ip, mac_address, trunked=True):

    conf = []
    if trunked:
        conf = (
            # port-channel
            _configure_interface('port-channel', interface) +
            _base_trunked_configuration(device_id, interface, vlan_id) +
            _add_vpc(interface) +

            # IPSG
            _bind_ip(ip, mac_address, vlan_id, interface) +

            # ethernet
            _configure_interface('ethernet', '1/%s' % (interface)) +
            _base_trunked_configuration(device_id, interface, vlan_id) +
            _add_channel_group(interface)
        )
    else:
        conf = (
            _configure_interface('ethernet', '1/%s' % (interface)) +
            _base_access_configuration(device_id, interface, vlan_id)
        )

    return conf

def shutdown_port(interface):

    return (
        # TODO(morgabra) this will leave orphaned port bindings! Make sure you remove all vlans before shutting down a port
        _shutdown_port_channel_interface(interface) +
        _shutdown_ethernet_interface(interface)
    )

def add_vlan(interface, vlan_id, ip, mac_address):
    return (
        # port-channel
        _configure_interface('port-channel', interface) +
        ['switchport trunk allowed vlan add %s' % (vlan_id)] +

        # IPSG
        # TODO(morgbara) This doesn't appear to do anything on the 3172s
        _bind_ip(ip, mac_address, vlan_id, interface)
    )

def remove_vlan(interface, vlan_id, ip, mac_address):
    return (
        # port-channel
        _configure_interface('port-channel', interface) +
        ['switchport trunk allowed vlan remove %s' % (vlan_id)] +

        # IPSG
        _unbind_ip(ip, mac_address, vlan_id, interface)
    )