"""Fixed-destination local HTTP bridge. Never executes application source."""
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

import httpx

TARGET = os.environ.get("TARGET", "http://demoapp:8080")
if TARGET != "http://demoapp:8080":
    raise SystemExit("Only the isolated demo application is a permitted target")


class Bridge(BaseHTTPRequestHandler):
    def do_GET(self): self.forward()
    def do_POST(self): self.forward()
    def log_message(self, *args): pass

    def forward(self):
        origin = self.headers.get("Origin")
        if origin and origin not in {"http://127.0.0.1:8000", "http://localhost:8000"}:
            self.send_error(403, "Local workbench origin required")
            return
        if self.command == "POST" and self.headers.get("X-Workbench-Proxy") != "local-control-plane":
            self.send_error(403, "Use the session-protected workbench API")
            return
        path = urlparse(self.path).path
        if not path.startswith(("/api/urls", "/r/", "/actuator/health")):
            self.send_error(404)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length < 0 or length > 65536:
                self.send_error(413)
                return
            with httpx.Client(timeout=15, trust_env=False, follow_redirects=False) as client:
                response = client.request(self.command, TARGET + path, content=self.rfile.read(length),
                                          headers={"Content-Type": "application/json"})
            self.send_response(response.status_code)
            for key in ["Content-Type", "Location", "Retry-After"]:
                if key in response.headers:
                    self.send_header(key, response.headers[key])
            self.send_header("Content-Length", str(len(response.content)))
            self.end_headers()
            self.wfile.write(response.content)
        except (httpx.HTTPError, ValueError):
            self.send_error(503, "Demo application unavailable")


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 8080), Bridge).serve_forever()
