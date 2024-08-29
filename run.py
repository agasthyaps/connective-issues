import os
from gevent import monkey
monkey.patch_all()

from app import app, socketio
from gevent.pywsgi import WSGIServer
from geventwebsocket.handler import WebSocketHandler

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    http_server = WSGIServer(('0.0.0.0', port), app, handler_class=WebSocketHandler)
    print(f"Server is running on port {port}")
    http_server.serve_forever()