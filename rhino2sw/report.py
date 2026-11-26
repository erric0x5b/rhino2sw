"""Storico unico delle conversioni in un solo CSV (separatore ';', decimali con la virgola per Excel)."""
import csv
import getpass
import os
import platform
import re
import time

from . import __version__
from .settings import cartella_dati, cartella_rapporti

NOME_FILE = "rapporti_rhino2sw.csv"
IN_ATTESA = "rapporti_in_attesa.csv"   # righe non scritte perche' il CSV era bloccato o la rete assente

CAMPI = ["data_ora", "utente", "pc", "versione", "file", "esito", "solidi", "facce_prima", "facce_dopo",
         "convertite", "bspline_rimaste", "tipi_prima", "tipi_dopo", "volume_mm3", "diff_volume_%",
         "diff_area_%", "scost_max_mm", "spigoli_gap", "gap_max_mm", "secondi", "note", "percorso", "file_uscita"]
DECIMALI = {"volume_mm3": 2, "diff_volume_%": 6, "diff_area_%": 6, "scost_max_mm": 5, "gap_max_mm": 4, "secondi": 1}
NUMERICI = set(DECIMALI)


def percorso_csv(s=None):
    return os.path.join(cartella_rapporti(s), NOME_FILE)


def _fmt(k, v):
    if v is None:
        return ""
    if k in NUMERICI and isinstance(v, (int, float)):
        return f"{v:.{DECIMALI[k]}f}".replace(".", ",")
    return str(v)


def riga_da_risultato(r):
    riga = {k: _fmt(k, r.get(k)) for k in CAMPI}
    riga["data_ora"] = r.get("data_ora") or time.strftime("%Y-%m-%d %H:%M:%S")
    riga["utente"] = r.get("utente") or getpass.getuser()
    riga["pc"] = r.get("pc") or platform.node()
    riga["versione"] = r.get("versione") or __version__
    return riga


def _intestazione_ok(path):
    try:
        with open(path, encoding="utf-8-sig", newline="") as fh:
            return next(csv.reader(fh, delimiter=";"), None) == CAMPI
    except OSError:
        return False


def _migra(path):
    """Riscrive un CSV con colonne di una versione precedente nel formato attuale (colonne nuove vuote)."""
    with open(path, encoding="utf-8-sig", newline="") as fh:
        vecchie = list(csv.DictReader(fh, delimiter=";"))
    copia = path[:-4] + time.strftime("_backup_%Y%m%d_%H%M%S.csv")
    os.replace(path, copia)
    with open(path, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=CAMPI, delimiter=";", extrasaction="ignore", restval="")
        w.writeheader()
        w.writerows(vecchie)
    os.remove(copia)


def _scrivi(path, righe):
    """Aggiunge righe; se il file ha un formato vecchio lo archivia e ne crea uno nuovo."""
    d = os.path.dirname(path)
    os.makedirs(d, exist_ok=True)
    if os.path.exists(path) and os.path.getsize(path) > 0 and not _intestazione_ok(path):
        _migra(path)
    nuovo = not os.path.exists(path) or os.path.getsize(path) == 0
    with open(path, "a", encoding="utf-8-sig" if nuovo else "utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=CAMPI, delimiter=";", extrasaction="ignore")
        if nuovo:
            w.writeheader()
        w.writerows(righe)


def _leggi_attesa():
    p = os.path.join(cartella_dati(), IN_ATTESA)
    if not os.path.exists(p):
        return []
    with open(p, encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh, delimiter=";"))


def aggiungi(risultati, s=None, tentativi=5):
    """Scrive i risultati nel CSV unico. Restituisce (percorso_scritto, in_attesa: bool)."""
    righe = _leggi_attesa() + [riga_da_risultato(r) for r in risultati]
    dest = percorso_csv(s)
    for i in range(tentativi):
        try:
            _scrivi(dest, righe)
            try:
                os.remove(os.path.join(cartella_dati(), IN_ATTESA))
            except OSError:
                pass
            return dest, False
        except OSError:          # file aperto in Excel o cartella di rete non raggiungibile
            time.sleep(0.5 * (i + 1))
    attesa = os.path.join(cartella_dati(), IN_ATTESA)
    if os.path.exists(attesa):
        os.remove(attesa)
    _scrivi(attesa, righe)
    return attesa, True


def leggi(s=None):
    p = percorso_csv(s)
    if not os.path.exists(p):
        return []
    with open(p, encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh, delimiter=";"))


def righe_in_attesa():
    return len(_leggi_attesa())


def importa_vecchi(percorsi, s=None):
    """Importa i rapporto_AAAAMMGG_HHMMSS.csv della versione 0.1. Restituisce il numero di righe importate."""
    gia = {(r.get("data_ora"), r.get("percorso")) for r in leggi(s)}
    nuove = []
    for p in percorsi:
        m = re.search(r"(\d{8})_(\d{6})", os.path.basename(p))
        if m:
            d, t = m.groups()
            data = f"{d[:4]}-{d[4:6]}-{d[6:]} {t[:2]}:{t[2:4]}:{t[4:]}"
        else:
            data = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(os.path.getmtime(p)))
        with open(p, encoding="utf-8-sig", newline="") as fh:
            for r in csv.DictReader(fh, delimiter=";"):
                if not r.get("file"):
                    continue
                riga = {k: (r.get(k) or "") for k in CAMPI}
                for k in NUMERICI:
                    try:
                        riga[k] = _fmt(k, float(riga[k].replace(",", ".")))
                    except ValueError:
                        pass
                riga.update(data_ora=data, utente="", pc="", versione="0.1")
                if (riga["data_ora"], riga["percorso"]) not in gia:
                    nuove.append(riga); gia.add((riga["data_ora"], riga["percorso"]))
    if nuove:
        _scrivi(percorso_csv(s), nuove)
    return len(nuove)
