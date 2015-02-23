from datetime import date
import tornado.ioloop
import tornado.web
import json

class PRHandler(tornado.web.RequestHandler):
    def get(self):
        response = { 'version': '1.0.0',
                     'last_build':  date.today().isoformat() }
        self.write(response)

    def post(self):
        payload = json.loads(self.request.body)
        print payload

application = tornado.web.Application([
    (r"/", PRHandler)
])

if __name__ == "__main__":
    application.listen(8888)
    tornado.ioloop.IOLoop.instance().start()
