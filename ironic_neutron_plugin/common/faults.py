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

import webob.dec


class BadRequest(webob.exc.HTTPBadRequest):

    code = 400
    title = 'Bad Request'
    explanation = 'Bad Request'

    def __init__(self, title=None, explanation=None):
        if title:
            self.title = title

        if explanation:
            self.explanation = explanation

        super(BadRequest, self).__init__()


class NotFound(webob.exc.HTTPBadRequest):

    code = 404
    title = 'Not Found'
    explanation = 'Not Found'

    def __init__(self, title=None, explanation=None):
        if title:
            self.title = title

        if explanation:
            self.explanation = explanation

        super(NotFound, self).__init__()
