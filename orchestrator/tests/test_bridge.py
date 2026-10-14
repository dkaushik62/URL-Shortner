import importlib.util
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path

import httpx


def test_bridge_blocks_foreign_origin_and_direct_browser_mutations():
    source = Path(__file__).resolve().parents[2] / "infra/acceptance/bridge.py"
    spec = importlib.util.spec_from_file_location("trusted_bridge", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    server = ThreadingHTTPServer(("127.0.0.1", 0), module.Bridge)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with httpx.Client(base_url=f"http://127.0.0.1:{server.server_port}", trust_env=False) as client:
            assert client.post("/api/urls", json={"url": "https://example.com"}).status_code == 403
            assert client.post("/api/urls", headers={"Origin": "https://foreign.example", "X-Workbench-Proxy": "local-control-plane"}, json={}).status_code == 403
            assert client.post("/engineering/runs", headers={"X-Workbench-Proxy": "local-control-plane"}, json={}).status_code == 404
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
