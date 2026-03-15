#!/usr/bin/env python3
"""
Gorkcode Browser Bridge - Simple HTTP server for communication between
gorkcode CLI and the Chrome extension.
"""
import json
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

HOST = "localhost"
PORT = 9876

latest_state = {"url": "", "title": "", "timestamp": 0, "logs": []}
pending_execute = None
last_result = None

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith("/state") or self.path.startswith("/context"):
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({
                "ok": True,
                "url": latest_state["url"],
                "title": latest_state["title"],
                "last_updated": time.time() - latest_state["timestamp"],
                "logs": latest_state.get("logs", [])[-20:]
            }).encode())
        elif self.path.startswith("/command"):
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            if pending_execute:
                self.wfile.write(json.dumps({
                    "command": "execute",
                    "code": pending_execute
                }).encode())
                # clear after sending once
                global pending_execute
                pending_execute = None
            else:
                self.wfile.write(json.dumps({"command": "none"}).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length)
        try:
            data = json.loads(body)
        except:
            data = {}

        if self.path.startswith("/update"):
            latest_state.update({
                "url": data.get("url", ""),
                "title": data.get("title", ""),
                "timestamp": time.time(),
                "logs": data.get("logs", latest_state.get("logs", []))
            })
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"ok": True}).encode())

        elif self.path.startswith("/execute"):
            global pending_execute
            pending_execute = data.get("code", "")
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"ok": True, "status": "pending"}).encode())

        elif self.path.startswith("/result"):
            global last_result
            last_result = data
            latest_state["logs"] = data.get("logs", [])
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"ok": True}).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        return  # quiet

def run_server():
    server = HTTPServer((HOST, PORT), Handler)
    print(f"Gorkcode Browser Bridge running on http://{HOST}:{PORT}")
    print("Extension can connect. gorkcode can call browser_execute tool.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nBridge stopped.")

if __name__ == "__main__":
    run_server()