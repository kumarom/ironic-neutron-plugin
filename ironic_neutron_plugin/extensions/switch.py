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

from neutron.api import extensions
from neutron import wsgi

from ironic_neutron_plugin.common import faults
from ironic_neutron_plugin.db import db

from simplejson import scanner as json_scanner

from neutron.openstack.common import log as logging

LOG = logging.getLogger(__name__)

#TODO(morgabra) 'switch' is a terrible extension name

EXTRA_ATTRIBUTES = {
    'ports': {
        'switch:portmaps': {'allow_post': False, 'allow_put': False,
                            'validate': {'type:list': None},
                            'is_visible': True}
    },
    'networks': {
        'switch:trunked': {'allow_post': True, 'allow_put': False,
                           'validate': {'type:boolean': None},
                           'is_visible': True}
    }
}


class SwitchController(wsgi.Controller):

    def index(self, request):
        switches = db.get_all_switches()
        return dict(switches=[s.as_dict() for s in switches])

    def show(self, request, id):
        switch = db.get_switch(id)
        if not switch:
            raise faults.NotFound(
                title='Switch %s not found' % (id))
        return dict(switch=switch.as_dict())

    def delete(self, request, id):
        db.delete_switch(id)

    def create(self, request):

        try:
            body = request.json_body
        except json_scanner.JSONDecodeError:
            raise faults.BadRequest(title='Invalid JSON Body')

        try:
            body = body.pop('switch')
        except KeyError:
            raise faults.BadRequest(
                title='Invalid JSON Body',
                explanation='"switch" not found in request body')

        try:
            switch_ip = body.pop('ip')
            username = body.pop('username')
            password = body.pop('password')
            switch_type = body.pop('type')
        except KeyError:
            raise faults.BadRequest(
                title='Invalid JSON Body',
                explanation='Missing required key')

        switch = db.get_switch(switch_ip)

        if switch:
            raise faults.BadRequest(
                title='Switch %s already exists' % (switch_ip))

        switch = db.create_switch(switch_ip, username, password, switch_type)
        return dict(switch=switch.as_dict())


class PortMapController(wsgi.Controller):

    def index(self, request):
        if request.GET.get('device_id'):
            portmaps = db.filter_portmaps(
                device_id=request.GET.get('device_id'))
        elif request.GET.get('switch_id'):
            portmaps = db.filter_portmaps(
                switch_id=request.GET.get('switch_id'))
        else:
            portmaps = db.get_all_portmaps()
        return dict(portmaps=[p.as_dict() for p in portmaps])

    def show(self, request, id):
        portmap = db.get_portmap(id)
        if not portmap:
            raise faults.NotFound(
                title='PortMap %s not found' % (id))
        return dict(portmap=portmap.as_dict())

    def delete(self, request, id):
        db.delete_portmap(id)

    def create(self, request):

        try:
            body = request.json_body
        except json_scanner.JSONDecodeError:
            raise faults.BadRequest(title='Invalid JSON Body')

        try:
            body = body.pop('portmap')
        except KeyError:
            raise faults.BadRequest(
                title='Invalid JSON Body',
                explanation='"portmap" missing from request body')

        try:
            switch_id = body.pop('switch_id')
            device_id = body.pop('device_id')
            port = body.pop('port')
            primary = body.pop('primary')
        except KeyError:
            raise faults.BadRequest(
                title='Invalid JSON Body',
                explanation='Missing required key')

        switch = db.get_switch(switch_id)

        if not switch:
            raise faults.BadRequest(
                title='Switch %s does not exist' % (switch_id))

        # Validation - max 2 portmaps and only 1 primary
        portmaps = list(db.filter_portmaps(device_id=device_id))

        # TODO(morgabra) Is this worth making configurable?
        if len(portmaps) > 1:
            raise faults.BadRequest(
                title='Not allowed more than 2 portmaps')

        if (primary is True) and (any([p.primary for p in portmaps])):
            raise faults.BadRequest(
                title='Not allowed more than 1 primary portmap')

        portmap = db.create_portmap(switch_id, device_id, port, primary)
        return dict(portmap=portmap.as_dict())


class Switch(extensions.ExtensionDescriptor):

    @classmethod
    def get_name(cls):
        return "Switch"

    @classmethod
    def get_alias(cls):
        return "switch"

    @classmethod
    def get_description(cls):
        return ("Physical switch with access credentials "
                "and device_id <-> switch port mapping")

    @classmethod
    def get_namespace(cls):
        return "http://github.com/rackerlabs/ironic-neutron-plugin"

    @classmethod
    def get_updated(cls):
        return "2014-03-11T00:00:00-00:00"

    def get_resources(self):
        resources = []
        sresource = extensions.ResourceExtension('switches',
                                                 SwitchController())
        resources.append(sresource)

        presource = extensions.ResourceExtension('portmaps',
                                                 PortMapController())
        resources.append(presource)
        return resources

    def get_extended_resources(self, version):
        if version == "2.0":
            return EXTRA_ATTRIBUTES
        else:
            return {}
