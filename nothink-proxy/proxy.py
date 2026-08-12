# Vermittler zwischen AnythingLLM und Ollama:
# haengt "think": false an Chat-Anfragen, damit Gemma nicht laut denkt.
# Alles andere wird unveraendert durchgereicht.
#
# Der OpenAI-Weg (/v1/chat/completions) steht mit in der Liste, damit alle
# Chat-Wege gleich behandelt werden. ACHTUNG: Ollama wertet dieses Feld auf
# DIESEM Weg NICHT aus (gemessen). Die Anfrage denkt weiter
# laut, egal was hier gesetzt wird. Der Eintrag ist also wirkungslos und
# steht nur der Vollstaendigkeit halber hier. Wer das Denken auf dem
# OpenAI-Weg abstellen will, braucht einen anderen Hebel.
#
# Praktische Folge fuer Docling-Bildbeschreibungen ueber diesen Weg: genug
# max_tokens mitgeben. Gemessen wurden 513 Completion-Tokens fuer einen
# einzigen Satz, rund 470 davon fuers Nachdenken. Mit 60 Tokens kam gar
# keine Antwort, mit 800 eine korrekte.
import json, urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

UPSTREAM = "http://ollama:11434"

class H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    def _relay(self, method):
        body = None
        n = int(self.headers.get("Content-Length") or 0)
        if n: body = self.rfile.read(n)
        if body and self.path.startswith(("/api/chat", "/api/generate",
                                          "/v1/chat/completions")):
            try:
                d = json.loads(body)
                d["think"] = False
                # ⚠ "think" versteht nur der native Weg /api/chat. Auf dem
                #   OpenAI-Weg /v1/chat/completions - den Docling fuer die
                #   Bildbeschreibung benutzt - wird es stillschweigend
                #   ignoriert; das Modell denkt weiter laut. Gemessen: 71,2 s mit Denken, 16,7 s ohne, und die Antwort
                #   OHNE Denken war sogar laenger.
                if self.path.startswith("/v1/"):
                    d["reasoning_effort"] = "none"
                body = json.dumps(d).encode()
            except Exception:
                pass
        req = urllib.request.Request(UPSTREAM + self.path, data=body, method=method)
        for k, v in self.headers.items():
            if k.lower() not in ("host", "content-length", "connection"):
                req.add_header(k, v)
        try:
            with urllib.request.urlopen(req, timeout=3600) as r:
                self.send_response(r.status)
                for k, v in r.headers.items():
                    if k.lower() not in ("transfer-encoding", "connection", "content-length"):
                        self.send_header(k, v)
                self.send_header("Connection", "close")
                self.end_headers()
                while True:
                    chunk = r.read(8192)
                    if not chunk: break
                    self.wfile.write(chunk); self.wfile.flush()
        except Exception as e:
            msg = json.dumps({"error": str(e)}).encode()
            self.send_response(502)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(msg)))
            self.end_headers(); self.wfile.write(msg)
    def do_GET(self): self._relay("GET")
    def do_POST(self): self._relay("POST")
    def log_message(self, *a): pass

ThreadingHTTPServer(("0.0.0.0", 11435), H).serve_forever()
