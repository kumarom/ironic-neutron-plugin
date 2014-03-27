from ncclient import manager

from ironic_neutron_plugin.drivers.cisco import commands

def _print_commands(cmd):

  print "COMMAND LIST"
  print "------------"

  for c in cmd:
    print c

  print "----------------"
  print "END COMMAND LIST"

def create_port(device_id, interface, vlan_id, ip, mac_address, trunked=True):
  cmd = commands.create_port(device_id, interface, vlan_id, ip, mac_address, trunked)

  _print_commands(cmd)

  print m.command(cmd)

def shutdown_port(interface):
  cmd = commands.shutdown_port(interface)

  _print_commands(cmd)

  print m.command(cmd)

def add_vlan(interface, vlan_id, ip, mac_address):
  cmd = commands.add_vlan(interface, vlan_id, ip, mac_address)

  _print_commands(cmd)

  print m.command(cmd)

def remove_vlan(interface, vlan_id, ip, mac_address):

  cmd = commands.remove_vlan(interface, vlan_id, ip, mac_address)

  _print_commands(cmd)

  print m.command(cmd)

def show_interface_configuration(type, interface):
  print m.command(commands.show_interface_configuration(interface))

with manager.connect(host='10.127.75.135', port=22, username='admin', password='admin') as m:
    #create_port('device_123', 40, 201, '10.128.0.100', 'aa:aa:aa:aa:aa:aa', False)
    #add_vlan(40, 301, '10.128.0.101', 'aa:aa:aa:aa:aa:00')
    #remove_vlan(40, 301, '10.128.0.101', 'aa:aa:aa:aa:aa:00' )
    #remove_vlan(40, 201, '10.128.0.100', 'aa:aa:aa:aa:aa:aa' )
    shutdown_port(40)
