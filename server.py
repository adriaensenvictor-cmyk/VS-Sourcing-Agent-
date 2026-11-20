"""Local sourcing desk: serve the latest report and run live scans on demand or on a schedule."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading
import time
import webbrowser

import scout


class Desk:
    def __init__(self, history):
        self.history = history
        self.page = history.parent / "desk.html"
        self.snapshot = history.parent / "latest-snapshot.json"
        self.lock = threading.Lock()
        self.scanning = False
        self.started = None
        self.last = None
        self.error = None
        self.next_scan = None

    def start_scan(self):
        with self.lock:
            if self.scanning:
                return False
            self.scanning, self.started, self.error = True, time.time(), None
        threading.Thread(target=self._run, daemon=True).start()
        return True

    def _run(self):
        try:
            self.last = scout.run_live(self.history, self.page, self.snapshot, server=True)
        except scout.RUN_ERRORS as error:
            self.error = str(error)
        finally:
            with self.lock:
                self.scanning = False

    def show(self, snapshot, replay):
        reviews, config = scout.load_config()
        snapshot = scout.prepare_replay(snapshot)
        leads = scout.build_inbox(snapshot, snapshot.get("reviews", reviews), snapshot.get("assessments", config["stages"]))
        self.page.write_text(scout.render(snapshot, leads, replay, server=True), encoding="utf-8")
        self.last = scout.summarize(snapshot, leads)

    def prepare(self):
        """Show the latest live capture; on a first start, show the labeled demo capture and scan in the background."""
        self.history.parent.mkdir(parents=True, exist_ok=True)
        snapshot = None
        if self.snapshot.exists():
            snapshot = json.loads(self.snapshot.read_text(encoding="utf-8"))
        # Captures from before company research existed are rescanned instead of shown half-empty.
        if snapshot and "web" in snapshot:
            self.show(snapshot, replay=False)
            return
        demo = scout.ROOT / "data/demo-snapshot.json"
        if demo.exists():
            # The page opens at once; it reloads with live data when the scan finishes, or keeps the demo offline.
            self.show(json.loads(demo.read_text(encoding="utf-8")), replay=True)
            print("Showing the captured demo scan while the first live scan runs (about a minute).")
            self.start_scan()
            return
        print("Running the first live scan...")
        self.start_scan()
        while self.scanning:
            time.sleep(0.2)
        if self.error:
            raise SystemExit(f"First scan failed: {self.error}")

    def status(self):
        return {
            "scanning": self.scanning,
            "elapsed": round(time.time() - self.started, 1) if self.scanning else None,
            "last": self.last, "error": self.error, "next_scan": self.next_scan,
        }

    def schedule(self, hours):
        def loop():
            while True:
                self.next_scan = time.time() + hours * 3600
                time.sleep(hours * 3600)
                self.start_scan()
        threading.Thread(target=loop, daemon=True).start()


def handler_for(desk):
    class Handler(BaseHTTPRequestHandler):
        def send(self, code, body, kind="application/json"):
            data = body if isinstance(body, bytes) else json.dumps(body).encode()
            self.send_response(code)
            self.send_header("Content-Type", f"{kind}; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if self.path in {"/", "/index.html"}:
                self.send(200, desk.page.read_bytes(), "text/html")
            elif self.path == "/api/status":
                self.send(200, desk.status())
            else:
                self.send(404, {"error": "Not found"})

        def do_POST(self):
            # A custom header cannot be sent cross-site without a CORS preflight this server never approves.
            if self.path != "/api/scan" or self.headers.get("X-FirstTrace") != "scan":
                self.send(403, {"error": "Forbidden"})
            elif desk.start_scan():
                self.send(202, {"started": True})
            else:
                self.send(409, {"error": "A scan is already running"})

        def log_message(self, *args):
            pass

    return Handler


def serve(history, port=8765, every=None, open_browser=True):
    desk = Desk(history)
    desk.prepare()
    if every:
        desk.schedule(every)
    server = ThreadingHTTPServer(("127.0.0.1", port), handler_for(desk))
    url = f"http://127.0.0.1:{port}/"
    print(f"FirstTrace desk running at {url}" + (f" - rescanning every {every:g} h" if every else ""))
    print("Your browser opens automatically. If it does not, open the address above.")
    print("Press Ctrl+C to stop.")
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        server.server_close()
