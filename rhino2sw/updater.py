"""Controllo aggiornamenti tramite le release di GitHub.

Solo lettura: una richiesta GET all'API pubblica, nessun dato inviato. Se la rete o il proxy
bloccano la richiesta il controllo fallisce in silenzio (salvo controllo manuale).
"""
import json
import os
import re
import time
import urllib.error
import urllib.request

from . import REPO_URL, __version__

API = os.environ.get("RHINO2SW_UPDATE_URL") or \
    "https://api.github.com/repos/" + REPO_URL.split("github.com/")[1] + "/releases/latest"
INTERVALLO = 24 * 3600


def versione_tupla(v):
    """'v0.2.10' -> (0, 2, 10); None se non e' una versione X.Y.Z."""
    m = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", (v or "").strip())
    return tuple(int(x) for x in m.groups()) if m else None


def piu_recente(remota, locale=__version__):
    r, l_ = versione_tupla(remota), versione_tupla(locale)
    return bool(r and l_ and r > l_)


def da_controllare(s, adesso=None):
    """True se il controllo automatico e' attivo e l'ultimo controllo e' piu' vecchio di 24 ore."""
    adesso = time.time() if adesso is None else adesso
    return bool(s.get("controlla_aggiornamenti", True)) and adesso - float(s.get("ultimo_controllo") or 0) > INTERVALLO


def ultima_release(timeout=5):
    """Restituisce un dict con versione, pagina, note, setup_url, sha256_url. Solleva OSError/ValueError."""
    req = urllib.request.Request(API, headers={"Accept": "application/vnd.github+json",
                                               "User-Agent": f"rhino2sw/{__version__}"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:   # usa il proxy di sistema
        dati = json.loads(resp.read().decode("utf-8"))
    if dati.get("draft") or dati.get("prerelease"):
        raise ValueError("ultima release non definitiva")
    versione = (dati.get("tag_name") or "").lstrip("v")
    if not versione_tupla(versione):
        raise ValueError(f"tag di release non valido: {dati.get('tag_name')!r}")
    setup = sha = None
    for a in dati.get("assets") or []:
        nome = (a.get("name") or "").lower()
        if nome.endswith("-setup.exe"):
            setup = a.get("browser_download_url")
        elif nome == "sha256sums.txt":
            sha = a.get("browser_download_url")
    return {"versione": versione, "pagina": dati.get("html_url") or REPO_URL + "/releases",
            "note": dati.get("body") or "", "setup_url": setup, "sha256_url": sha}


def controlla(s, manuale=False, timeout=5):
    """Esegue il controllo. Restituisce (esito, info):
       ("nuova", info) | ("aggiornato", info) | ("saltata", info) | ("errore", messaggio)."""
    try:
        info = ultima_release(timeout)
    except urllib.error.HTTPError as ex:
        if ex.code == 404:
            return "errore", "nessuna release pubblicata"
        return "errore", f"GitHub ha risposto {ex.code}"
    except (OSError, ValueError) as ex:
        return "errore", str(getattr(ex, "reason", ex))
    if not piu_recente(info["versione"]):
        return "aggiornato", info
    if not manuale and info["versione"] == s.get("versione_saltata"):
        return "saltata", info
    return "nuova", info
