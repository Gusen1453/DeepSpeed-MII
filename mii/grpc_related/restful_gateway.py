# Copyright (c) Microsoft Corporation.
# SPDX-License-Identifier: Apache-2.0

# DeepSpeed Team
import json
import threading
import time

from flask import Flask, request
from flask_restful import Resource, Api
from werkzeug.serving import make_server

import mii
from mii.constants import RESTFUL_GATEWAY_SHUTDOWN_TIMEOUT, RESTFUL_API_PATH


def shutdown(thread):
    time.sleep(RESTFUL_GATEWAY_SHUTDOWN_TIMEOUT)
    thread.server.shutdown()


def createRestfulGatewayApp(deployment_name, server_thread):
    # client must be thread-safe
    client = mii.client(deployment_name)

    class RestfulGatewayService(Resource):
        def __init__(self):
            super().__init__()

        def post(self):
            data = request.get_json()
            result = client.generate(**data)
            result_json = json.dumps([r.to_msg_dict() for r in result])
            return result_json

    app = Flask("RestfulGateway")

    @app.route("/terminate", methods=["GET"])
    def terminate():
        # Need to shutdown *after* completing the request
        threading.Thread(target=shutdown, args=(server_thread, )).start()
        return "Shutting down RESTful API gateway server"

    api = Api(app)
    path = "/{}/{}".format(RESTFUL_API_PATH, deployment_name)
    api.add_resource(RestfulGatewayService, path)

    return app


class RestfulGatewayThread(threading.Thread):
    def __init__(self, deployment_name, rest_port):
        threading.Thread.__init__(self)

        app = createRestfulGatewayApp(deployment_name, self)
        self.server = make_server("127.0.0.1", rest_port, app)
        self.ctx = app.app_context()
        self.ctx.push()

        self._stop_event = threading.Event()

    def run(self):
        self.server.serve_forever()
        self._stop_event.set()

    def get_stop_event(self):
        return self._stop_event
