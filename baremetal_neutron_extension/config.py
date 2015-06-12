# Copyright (c) 2014 OpenStack Foundation.
# (c) Copyright 2015 Hewlett-Packard Development Company, L.P.
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

from oslo.config import cfg

ironic_opts = [
    cfg.BoolOpt("dry_run",
                default=False,
                help="Log only, but exersize the mechanism."),
    cfg.StrOpt("credential_secret",
               help=("Secret AES key for encrypting switch credentials "
                     " in the datastore.")),
    cfg.IntOpt("auth_failure_retries",
               default=5,
               help="Number of times to retry commands due to auth failure"),
    cfg.IntOpt("auth_failure_retry_interval",
               default=2,
               help="Seconds to wait between retrying commands due to auth "
                    "failure"),
    cfg.IntOpt("save_queue_max_age",
               default=30,
               help="Seconds to wait before processing switch config save "
                    "commands"),
    cfg.IntOpt("save_queue_get_wait",
               default=5,
               help="Seconds to wait between polling for new switch config "
                    "save commands")
]

cfg.CONF.register_opts(ironic_opts, "ironic")
