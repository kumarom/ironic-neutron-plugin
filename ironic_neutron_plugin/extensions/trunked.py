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
from neutron.api.v2 import attributes as attr

EXTRA_ATTRIBUTES = {
    "ports": {
        "trunked": {"allow_post": True, "allow_put": True,
                    "validate": {"type:boolean": None},
                    "default": False,
                    "is_visible": True}
    }
}

class Trunked(extensions.ExtensionDescriptor):

    @classmethod
    def get_name(cls):
        return "Trunked"

    @classmethod
    def get_alias(cls):
        return "trunked"

    @classmethod
    def get_description(cls):
        return ('Flag ports with "trunked".')

    @classmethod
    def get_namespace(cls):
        return "http://github.com/rackerlabs/ironic-neutron-plugin"

    @classmethod
    def get_updated(cls):
        return "2014-03-11T00:00:00-00:00"

    def get_extended_resources(self, version):
        if version == "2.0":
            return EXTRA_ATTRIBUTES
        else:
            return {}
