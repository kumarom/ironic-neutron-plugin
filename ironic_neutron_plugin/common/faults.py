# vim: tabstop=4 shiftwidth=4 softtabstop=4
#
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