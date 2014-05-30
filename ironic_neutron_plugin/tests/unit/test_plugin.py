# Copyright (c) 2012 OpenStack Foundation.
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

from ironic_neutron_plugin.tests import base

from neutron.tests.unit import test_db_plugin


class TestIronicBasicGet(base.IronicMl2MechanismTestCase,
                        test_db_plugin.TestBasicGet):
    pass


class TestIronicV2HTTPResponse(base.IronicMl2MechanismTestCase,
                              test_db_plugin.TestV2HTTPResponse):
    pass


class TestIronicPortsV2(base.IronicMl2MechanismTestCase,
                       test_db_plugin.TestPortsV2):
    pass


class TestIronicNetworksV2(base.IronicMl2MechanismTestCase,
                          test_db_plugin.TestNetworksV2):
    pass


class TestIronicSubnetsV2(base.IronicMl2MechanismTestCase,
                         test_db_plugin.TestSubnetsV2):
    pass


