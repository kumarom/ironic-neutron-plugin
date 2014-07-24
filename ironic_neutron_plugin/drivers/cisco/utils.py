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


def filter_interface_conf(c):
    """Determine if an interface configuration string is relevant."""
    c = c.strip()
    if c.startswith("!"):
        return False
    if c.startswith("version "):
        return False
    if c.startswith("interface"):
        return False
    if not c:
        return False
    return True


def negate_conf(c):
    """Negate a line of configuration."""
    return "no %s" % c


def parse_command_result(res):
    """Get text reponse from an ncclient command.

    Example XML from ncclient:

    <?xml version="1.0" encoding="ISO-8859-1"?>
    <rpc-reply xmlns="urn:ietf:params:xml:ns:netconf:base:1.0"
               xmlns:if="http://www.cisco.com/nxos:1.0:if_manager"
               xmlns:nxos="http://www.cisco.com/nxos:1.0"
               message-id="urn:uuid:4a9be8b4-df85-11e3-ab20-becafe000bed">
      <data>
        !Command: show running-config interface Ethernet1/20
        !Time: Mon May 19 18:40:08 2014

        version 6.0(2)U2(4)

        interface Ethernet1/20
          shutdown
          spanning-tree port type edge
          spanning-tree bpduguard enable

      </data>
    </rpc-reply>

    Example return value:
    ['shutdown',
     'spanning-tree port type edge',
     'spanning-tree bpduguard enable']
    """
    if not res:
        return []

    # get the first child from the xml response
    res = res._root.getchildren()
    if len(res) != 1:
        raise Exception("cannot parse command response")

    # split the raw text by newline
    text = res[0].text
    if not text:
        return []

    res = text.split("\n")

    # filter comments and other unrelated data
    conf = [c.strip() for c in res]
    conf = [c.strip() for c in res if filter_interface_conf(c)]
    return conf


def parse_interface_status(res):
    """Parse 'show interface X' commands.

    Example XML from ncclient:
    <?xml version="1.0" encoding="ISO-8859-1"?>
    <rpc-reply xmlns="urn:ietf:params:xml:ns:netconf:base:1.0"
               xmlns:if="http://www.cisco.com/nxos:1.0:if_manager"
               xmlns:nxos="http://www.cisco.com/nxos:1.0" '
               message-id="urn:uuid:c87305ee-0d19-11e4-ab20-becafe000bed">
      <data>
        <show>
          <interface>
            <__XML__INTF_ifeth>
              <__XML__PARAM_value>
                <__XML__INTF_output>port-channel7</__XML__INTF_output>
              </__XML__PARAM_value>
              <__XML__OPT_Cmd_show_interface_if_eth___readonly__>
                <__readonly__>
                  <TABLE_interface>
                    <ROW_interface>
                      <interface>port-channel7</interface>
                      <state>up</state>
                      <vpc_status>vPC Status: Up, vPC number: 7</vpc_status>
                      ...
                    </ROW_interface>
                  </TABLE_interface>
                </__readonly__>
              </__XML__OPT_Cmd_show_interface_if_eth___readonly__>
            </__XML__INTF_ifeth>
          </interface>
        </show>
      </data>
    </rpc-reply>
    """
    # XML namespace
    ns = '{urn:ietf:params:xml:ns:netconf:base:1.0}'

    root = res._root

    def _add_ns(key):
        return '%s%s' % (ns, key)

    def _strip_ns(tag):
        return tag[len(ns):]

    interfaces = list(root.iter(_add_ns('ROW_interface')))

    if not interfaces:
        raise Exception("no interface data found")

    if len(interfaces) > 1:
        raise Exception("more than 1 interface found")

    interface = interfaces[0]

    r = {}
    for e in interface.iter():

        k = _strip_ns(e.tag)
        v = e.text

        if not k or k == 'ROW_interface':
            continue

        r[k] = v

    return r
