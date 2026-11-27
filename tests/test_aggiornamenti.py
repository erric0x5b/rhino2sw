"""Test del controllo aggiornamenti con un finto server GitHub locale.

    python tests/test_aggiornamenti.py
"""
import http.server
import json
import os
import sys
import tempfile
import threading

QUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(QUI))
RISPOSTA = {}


class Finto(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        codice, corpo = RISPOSTA["codice"], json.dumps(RISPOSTA.get("dati", {})).encode()
        self.send_response(codice)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(corpo)

    def log_message(self, *a):
        pass


def main():
    srv = http.server.HTTPServer(("127.0.0.1", 0), Finto)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    os.environ["RHINO2SW_UPDATE_URL"] = f"http://127.0.0.1:{srv.server_port}/latest"
    os.environ["XDG_DATA_HOME"] = tempfile.mkdtemp()
    os.environ["LOCALAPPDATA"] = os.environ["XDG_DATA_HOME"]
    from rhino2sw import __version__, updater
    errori = []

    def verifica(nome, cond):
        print(f"  {'ok ' if cond else 'NO '} {nome}")
        if not cond:
            errori.append(nome)

    verifica("confronto versioni", updater.piu_recente("0.10.0", "0.9.9") and not updater.piu_recente("0.2.1", "0.2.1")
             and not updater.piu_recente("v0.2.0", "0.2.1") and updater.piu_recente("v1.0.0", "0.2.1"))
    verifica("tag non validi ignorati", not updater.piu_recente("latest", "0.2.1"))
    verifica("controllo una volta al giorno",
             updater.da_controllare({"controlla_aggiornamenti": True, "ultimo_controllo": 0}, 100000)
             and not updater.da_controllare({"controlla_aggiornamenti": True, "ultimo_controllo": 99000}, 100000)
             and not updater.da_controllare({"controlla_aggiornamenti": False, "ultimo_controllo": 0}, 100000))

    asset = [{"name": "rhino2sw-9.9.9-setup.exe", "browser_download_url": "https://x/setup.exe"},
             {"name": "SHA256SUMS.txt", "browser_download_url": "https://x/sha"}]
    RISPOSTA.update(codice=200, dati={"tag_name": "v9.9.9", "html_url": "https://x/rel", "assets": asset})
    e, info = updater.controlla({})
    verifica("versione nuova trovata", e == "nuova" and info["setup_url"] == "https://x/setup.exe"
             and info["sha256_url"] == "https://x/sha")
    verifica("versione saltata", updater.controlla({"versione_saltata": "9.9.9"})[0] == "saltata")
    verifica("saltata ma controllo manuale", updater.controlla({"versione_saltata": "9.9.9"}, manuale=True)[0] == "nuova")
    RISPOSTA.update(codice=200, dati={"tag_name": "v" + __version__, "assets": []})
    verifica("gia' aggiornato", updater.controlla({})[0] == "aggiornato")
    RISPOSTA.update(codice=200, dati={"tag_name": "v9.9.9", "prerelease": True})
    verifica("pre-release ignorata", updater.controlla({})[0] == "errore")
    RISPOSTA.update(codice=404, dati={"message": "Not Found"})
    verifica("nessuna release", updater.controlla({}) == ("errore", "nessuna release pubblicata"))
    os.environ["RHINO2SW_UPDATE_URL"] = "http://127.0.0.1:9/latest"
    import importlib
    importlib.reload(updater)
    verifica("rete assente -> errore silenzioso", updater.controlla({}, timeout=2)[0] == "errore")
    srv.shutdown()
    if errori:
        print("\nFALLITO")
        return 1
    print("\nTutti i test superati")
    return 0


if __name__ == "__main__":
    sys.exit(main())
