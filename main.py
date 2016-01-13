from datetime import date
import tornado.ioloop
import tornado.web
import json
import logging
import tasks


class PRHandler(tornado.web.RequestHandler):

    def get(self):
        response = {'version': '1.0.0',
                    'last_build':  date.today().isoformat()}
        self.write(response)

    def post(self):
        logging.debug("payload = %s" % self.request.body)
        payload = json.loads(self.request.body.decode('utf8'))
        event = self.request.headers.get("X-Event-Key", None)
        if event is None:
            logging.warn("No event key in request")
            raise tornado.web.HTTPError(400)
        event = event.replace(':', '_')

        if hasattr(tasks, event):
            action = eval("tasks.{}".format(event))
            action(payload)
        else:
            logging.warn("No task for {}".format(event))
            raise tornado.web.HTTPError(400)


application = tornado.web.Application([
    (r"/", PRHandler)
])

if __name__ == "__main__":
    logging.getLogger().setLevel(logging.DEBUG)
    application.listen(8888)
    tornado.ioloop.IOLoop.instance().start()
