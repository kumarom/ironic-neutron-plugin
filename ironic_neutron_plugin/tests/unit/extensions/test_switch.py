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