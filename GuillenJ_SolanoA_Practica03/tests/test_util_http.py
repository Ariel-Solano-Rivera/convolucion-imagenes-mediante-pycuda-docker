import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from scripts.util_http import enviar_bytes


def test_tiempo_cliente_incluye_descarga_del_resultado():
    resultado_descargado = threading.Event()

    class Manejador(BaseHTTPRequestHandler):
        def do_POST(self):
            self.rfile.read(int(self.headers["Content-Length"]))
            cuerpo = json.dumps({"resultado_url": "/resultado.png"}).encode()
            self.send_response(201)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(cuerpo)))
            self.end_headers()
            self.wfile.write(cuerpo)

        def do_GET(self):
            resultado_descargado.set()
            cuerpo = b"PNG simulado"
            self.send_response(200)
            self.send_header("Content-Length", str(len(cuerpo)))
            self.end_headers()
            self.wfile.write(cuerpo)

        def log_message(self, _formato, *_args):
            pass

    servidor = ThreadingHTTPServer(("127.0.0.1", 0), Manejador)
    hilo = threading.Thread(target=servidor.serve_forever, daemon=True)
    hilo.start()
    try:
        url = f"http://127.0.0.1:{servidor.server_port}"
        respuesta = enviar_bytes(url, "entrada.png", b"imagen", "media", 3)
    finally:
        servidor.shutdown()
        servidor.server_close()
        hilo.join(timeout=2)
    assert respuesta.estado_http == 201
    assert resultado_descargado.is_set()
    assert respuesta.tiempo_cliente_ms > 0
