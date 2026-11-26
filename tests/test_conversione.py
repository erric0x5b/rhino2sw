"""Test di regressione sui pezzi sintetici.

    python tests/test_conversione.py              usa il codice sorgente
    python tests/test_conversione.py --exe PATH   prova anche l'eseguibile costruito (modo --worker)
"""
import json
import os
import subprocess
import sys
import tempfile

QUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(QUI))

ATTESI = {
    "blocco_nurbs.stp": ("OK", {"Plane": 6, "Cylinder": 5}),
    "blocco_spostato.step": ("OK", {"Plane": 6, "Cylinder": 5}),
    "aperto.stp": ("NON CONVERTITO", None),
    "rotto.stp": ("ERRORE", None),
}


def main():
    exe = sys.argv[sys.argv.index("--exe") + 1] if "--exe" in sys.argv else None
    d = tempfile.mkdtemp(prefix="r2sw_test_")
    subprocess.check_call([sys.executable, os.path.join(QUI, "crea_pezzi_prova.py"), d],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    from rhino2sw.core import converti_file, raccogli
    files = raccogli([d])
    assert len(files) == len(ATTESI), files
    errori = []
    for p in files:
        nome = os.path.basename(p)
        esito, _ = ATTESI[nome]
        r = converti_file(p)
        if r["esito"] != esito:
            errori.append(f"{nome}: atteso {esito}, ottenuto {r['esito']} ({r.get('note')})")
        if esito == "OK":
            if r["bspline_rimaste"] != 0 or r["scost_max_mm"] > 1e-4 or not os.path.exists(r["file_uscita"]):
                errori.append(f"{nome}: conversione incompleta {r}")
            if r["tipi_dopo"] != "6 piani, 5 cilindri":
                errori.append(f"{nome}: facce inattese {r['tipi_dopo']}")
        print(f"  {nome:24s} {r['esito']}")
        if exe:
            js = os.path.join(d, nome + ".json")
            subprocess.run([exe, "--worker", p, js], timeout=600)
            try:
                with open(js, encoding="utf-8") as fh:
                    re_ = json.load(fh)
            except OSError:
                errori.append(f"{nome}: l'eseguibile non ha prodotto il risultato")
                continue
            if re_["esito"] != esito:
                errori.append(f"{nome} (exe): atteso {esito}, ottenuto {re_['esito']} ({re_.get('note')})")
            print(f"  {nome:24s} {re_['esito']}  (eseguibile)")
    if errori:
        print("\nFALLITO:\n  " + "\n  ".join(errori))
        return 1
    print("\nTutti i test superati")
    return 0


if __name__ == "__main__":
    sys.exit(main())
