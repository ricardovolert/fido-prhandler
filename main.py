from datetime import date
import tornado.ioloop
import tornado.web
import json
import logging
from tasks import *


KEYS = ["approve", "comment_created", "comment_deleted", "comment_updated",
        "created", "updated", "unapprove", "declined", "merged"]


class PRHandler(tornado.web.RequestHandler):

    def get(self):
        response = {'version': '1.0.0',
                    'last_build':  date.today().isoformat()}
        self.write(response)

    def post(self):
        logging.debug("payload = %s" % self.request.body)
        payload = json.loads(self.request.body)

        actions = [key for key in KEYS if "pullrequest_%s" % key in payload]
        logging.debug("Action that will be performed: %s" % ",".join(actions))
        if not actions:
            logging.warn("Unexpected payload: %s" % payload)
        else:
            for action in actions:
                logging.debug("Using handle_%s" % action)
                handler = eval("handle_%s" % action)
                handler(payload["pullrequest_%s" % action])


application = tornado.web.Application([
    (r"/", PRHandler)
])

if __name__ == "__main__":
    logging.getLogger().setLevel(logging.DEBUG)
    application.listen(8888)
    tornado.ioloop.IOLoop.instance().start()
