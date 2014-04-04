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

from oslo.config import cfg

ironic_opts = [
    cfg.BoolOpt("dry_run",
                default=False,
                help="Do not attempt to actually configure switch.")
]

cfg.CONF.register_opts(ironic_opts, "ironic")


def get_ironic_config():
    return cfg.CONF.ironic
