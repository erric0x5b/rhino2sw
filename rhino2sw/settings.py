"""Impostazioni utente, salvate in JSON nella cartella dati dell'utente."""
import json
import os
import sys


def cartella_dati():
    """%LOCALAPPDATA%\\rhino2sw su Windows, ~/.local/share/rhino2sw altrove."""
    if sys.platform.startswith("win"):
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~\\AppData\\Local")
    else:
        base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    d = os.path.join(base, "rhino2sw")
    os.makedirs(d, exist_ok=True)
    return d


PREDEFINITE = {
    "cartella_rapporti": "",       # vuoto = cartella dati dell'utente
    "cartella_uscita_fissa": "",   # vuoto = accanto agli originali in per_SolidWorks
    "processi_paralleli": 2,
    "timeout_minuti": 15,
    "controlla_aggiornamenti": True,
    "ultimo_controllo": 0,          # epoch dell'ultimo controllo aggiornamenti riuscito
    "versione_saltata": "",         # "Salta questa versione"
}


def _file():
    return os.path.join(cartella_dati(), "impostazioni.json")


def carica():
    s = dict(PREDEFINITE)
    try:
        with open(_file(), encoding="utf-8") as fh:
            s.update({k: v for k, v in json.load(fh).items() if k in PREDEFINITE})
    except (OSError, ValueError):
        pass
    try:
        s["processi_paralleli"] = max(1, min(8, int(s["processi_paralleli"])))
        s["timeout_minuti"] = max(1, int(s["timeout_minuti"]))
    except (TypeError, ValueError):
        s["processi_paralleli"] = PREDEFINITE["processi_paralleli"]
        s["timeout_minuti"] = PREDEFINITE["timeout_minuti"]
    return s


def salva(s):
    with open(_file(), "w", encoding="utf-8") as fh:
        json.dump({k: s.get(k, v) for k, v in PREDEFINITE.items()}, fh, indent=2, ensure_ascii=False)


def cartella_rapporti(s=None):
    s = s or carica()
    return s.get("cartella_rapporti") or cartella_dati()
