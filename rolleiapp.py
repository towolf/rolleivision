#!/usr/bin/env python

import web, json, rolleicom

FUNCS = rolleicom.RolleiCom.__dict__.keys()
r = rolleicom.RolleiCom('/dev/ttyUSB0')

urls = (
    '/rolleicom', 'rolleicom'
)

class rolleicom:

    def GET(self):
        input = web.input(action = None)
        web.header('Content-Type', 'application/json')

        action = input.action
        if action is None:
            return json.dumps({'response': 'specify ?action=<action>', "input": input})
        else:
            del input['action']

        if action not in FUNCS:
            return json.dumps({'response': 'unknown action', "input": input})
        else:
            try:
                response = getattr(r, action)(**input)
            except AttributeError, v:
                response = 'action failed to execute: ' + v
                return json.dumps({'response': response, "action": action, "input": input})
            except TypeError, v:
                response = 'Incorrect args: ' + str(v)
                return json.dumps({'response': response, "action": action, "input": input})
            return json.dumps({'response': response, "action": action, "input": input})

    def POST(self):
        data = web.data()
        response = r.runbatch(data)
        web.header('Content-Type', 'application/json')
        return json.dumps({'response': response})

# For serving using any wsgi server
wsgi_app = web.application(urls, globals()).wsgifunc()

if __name__ == "__main__":
    app = web.application(urls, globals())
    app.run()
