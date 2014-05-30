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

from ironic_neutron_plugin.db import db as ironic_db
from ironic_neutron_plugin.tests import base

import webob


class TestSwitches(base.IronicMl2MechanismTestCase):

    def setUp(self):
        super(TestSwitches, self).setUp()

    def test_get_raises_404(self):
        req = self.new_show_request('switches', 'foobar')
        res = req.get_response(self.ext_api)

        self.assertEqual(res.status_int, webob.exc.HTTPNotFound.code)

    def test_get(self):
        switch = self._create_switch(self.fmt, 'switch0', '1.2.3.4')
        switch = self.deserialize(self.fmt, switch)

        req = self.new_show_request('switches', switch['switch']['id'])
        res = self.deserialize(self.fmt, req.get_response(self.ext_api))

        self.assertEqual(res['switch']['host'], '1.2.3.4')

    def test_create(self):
        switch = self._create_switch(self.fmt, 'switch0', '1.2.3.4')
        switch = self.deserialize(self.fmt, switch)

        self.assertEqual(switch['switch']['host'], '1.2.3.4')

    def test_delete(self):
        switch = self.deserialize(
            self.fmt, self._create_switch(self.fmt, 'switch0', '1.2.3.4')
        )
        switch_id = switch['switch']['id']

        req = self.new_delete_request('switches', switch_id)
        res = req.get_response(self.ext_api)

        self.assertEqual(res.status_int, webob.exc.HTTPNoContent.code)

        switch = ironic_db.get_switch(switch_id)
        self.assertEqual(switch, None)

    def test_delete_cascade_delete_switchports(self):
        pass


class TestSwitchPorts(base.IronicMl2MechanismTestCase):

    def setUp(self):
        super(TestSwitchPorts, self).setUp()

        self.switch = self.deserialize(
            self.fmt, self._create_switch(self.fmt, 'switch0', '1.2.3.4')
        )
        self.switch_id = self.switch['switch']['id']

    def test_get_raises_404(self):
        req = self.new_show_request('switchports', 'foobar')
        res = req.get_response(self.ext_api)

        self.assertEqual(res.status_int, webob.exc.HTTPNotFound.code)
