# Copyright (c) 2014 OpenStack Foundation.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.


def ok():
    res = """<?xml version="1.0" encoding="ISO-8859-1"?>
<rpc-reply xmlns="urn:ietf:params:xml:ns:netconf:base:1.0"
           xmlns:if="http://www.cisco.com/nxos:1.0:if_manager"
           xmlns:nxos="http://www.cisco.com/nxos:1.0"
           message-id="urn:uuid:e7ef8254-10a6-11e4-b86d-becafe000bed">
  <data/>
</rpc-reply>"""
    return res


def show_dhcp(port):

    dhcp = ("ip source binding 10.0.0.1 FFFF.FFFF.FFFF.FFFF "
            "vlan 1 interface port-channel%s") % (port)

    res = """<?xml version="1.0" encoding="ISO-8859-1"?>
<rpc-reply xmlns="urn:ietf:params:xml:ns:netconf:base:1.0"
           xmlns:if="http://www.cisco.com/nxos:1.0:if_manager"
           xmlns:nxos="http://www.cisco.com/nxos:1.0"
           message-id="urn:uuid:4a9be8b4-df85-11e3-ab20-becafe000bed">
  <data>
    !Command: show running-config dhcp | egrep port-channel%(port)s$
    !Time: Mon May 19 18:40:08 2014

    version 6.0(2)U2(4)

    interface port-channel%(port)s
    %(dhcp)s
  </data>
</rpc-reply>"""
    return res % ({'port': port,
                   'dhcp': dhcp})


def show_port_channel_config_trunked(port):

    res = """<?xml version="1.0" encoding="ISO-8859-1"?>
    <rpc-reply xmlns="urn:ietf:params:xml:ns:netconf:base:1.0"
               xmlns:if="http://www.cisco.com/nxos:1.0:if_manager"
               xmlns:nxos="http://www.cisco.com/nxos:1.0"
               message-id="urn:uuid:4a9be8b4-df85-11e3-ab20-becafe000bed">
      <data>
        !Command: show running-config interface port-channel%(port)s
        !Time: Mon May 19 18:40:08 2014

        version 6.0(2)U2(4)

        interface port-channel%(port)s
          description CUST39a8365c-3b84-4169-bc1a-1efa3ab20e04-host
          switchport mode trunk
          switchport trunk allowed vlan 1,2
          ip verify source dhcp-snooping-vlan
          spanning-tree port type edge trunk
          no negotiate auto
          vpc %(port)s

      </data>
    </rpc-reply>"""
    return res % ({'port': port})


def show_ethernet_config_trunked(port):

    res = """<?xml version="1.0" encoding="ISO-8859-1"?>
    <rpc-reply xmlns="urn:ietf:params:xml:ns:netconf:base:1.0"
               xmlns:if="http://www.cisco.com/nxos:1.0:if_manager"
               xmlns:nxos="http://www.cisco.com/nxos:1.0"
               message-id="urn:uuid:4a9be8b4-df85-11e3-ab20-becafe000bed">
      <data>
        !Command: show running-config interface Ethernet1/%(port)s
        !Time: Mon May 19 18:40:08 2014

        version 6.0(2)U2(4)

        interface Ethernet1/%(port)s
          description CUST39a8365c-3b84-4169-bc1a-1efa3ab20e04-host
          no lldp transmit
          switchport mode trunk
          switchport trunk allowed vlan 1,2
          spanning-tree port type edge trunk
          spanning-tree bpduguard enable
          channel-group %(port)s mode active

      </data>
    </rpc-reply>"""
    return res % ({'port': port})


def show_ethernet_config_access(port):

    res = """<?xml version="1.0" encoding="ISO-8859-1"?>
    <rpc-reply xmlns="urn:ietf:params:xml:ns:netconf:base:1.0"
               xmlns:if="http://www.cisco.com/nxos:1.0:if_manager"
               xmlns:nxos="http://www.cisco.com/nxos:1.0"
               message-id="urn:uuid:4a9be8b4-df85-11e3-ab20-becafe000bed">
      <data>
        !Command: show running-config interface Ethernet1/%(port)s
        !Time: Mon May 19 18:40:08 2014

        version 6.0(2)U2(4)

        interface Ethernet1/%(port)s
          description CUST32fdc565-7860-47b9-be57-f5d5ee1875a0-host
          switchport access vlan 3
          spanning-tree port type edge
          spanning-tree bpduguard enable

      </data>
    </rpc-reply>"""
    return res % ({'port': port})


def show_port_channel_status(port):
    status = "vPC Status: Up, vPC number: %s" % (port)

    res = """<?xml version="1.0" encoding="ISO-8859-1"?>
<rpc-reply xmlns="urn:ietf:params:xml:ns:netconf:base:1.0"
           xmlns:if="http://www.cisco.com/nxos:1.0:if_manager"
           xmlns:nxos="http://www.cisco.com/nxos:1.0"
           message-id="urn:uuid:c87305ee-0d19-11e4-ab20-becafe000bed">
  <data>
    <show>
      <interface>
        <__XML__INTF_ifeth>
          <__XML__PARAM_value>
            <__XML__INTF_output>port-channel%(port)s</__XML__INTF_output>
          </__XML__PARAM_value>
          <__XML__OPT_Cmd_show_interface_if_eth___readonly__>
            <__readonly__>
              <TABLE_interface>
                <ROW_interface>
                  <interface>port-channel%(port)s</interface>
                  <state>up</state>
                  <vpc_status>%(status)s</vpc_status>
                </ROW_interface>
              </TABLE_interface>
            </__readonly__>
          </__XML__OPT_Cmd_show_interface_if_eth___readonly__>
        </__XML__INTF_ifeth>
      </interface>
    </show>
  </data>
</rpc-reply>"""
    return res % ({'port': port,
                   'status': status})


def show_ethernet_status(port):

    res = """<?xml version="1.0" encoding="ISO-8859-1"?>
<rpc-reply xmlns="urn:ietf:params:xml:ns:netconf:base:1.0"
           xmlns:if="http://www.cisco.com/nxos:1.0:if_manager"
           xmlns:nxos="http://www.cisco.com/nxos:1.0"
           message-id="urn:uuid:c87305ee-0d19-11e4-ab20-becafe000bed">
  <data>
    <show>
      <interface>
        <__XML__INTF_ifeth>
          <__XML__PARAM_value>
            <__XML__INTF_output>ethernet1/%(port)s</__XML__INTF_output>
          </__XML__PARAM_value>
          <__XML__OPT_Cmd_show_interface_if_eth___readonly__>
            <__readonly__>
              <TABLE_interface>
                <ROW_interface>
                  <interface>ethernet1/%(port)s</interface>
                  <state>up</state>
                </ROW_interface>
              </TABLE_interface>
            </__readonly__>
          </__XML__OPT_Cmd_show_interface_if_eth___readonly__>
        </__XML__INTF_ifeth>
      </interface>
    </show>
  </data>
</rpc-reply>"""
    return res % ({'port': port})
