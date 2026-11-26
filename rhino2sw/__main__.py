"""Punto di ingresso.

    rhino2sw                         apre la finestra
    rhino2sw file.stp cartella ...   apre la finestra con i file gia' in elenco
                                     (trascinamento sull'icona, menu "Invia a")
    rhino2sw --cli file ...          conversione da riga di comando
    rhino2sw --worker IN OUT.json [--uscita DIR] [--dividi --modo assieme|assolute --nomi oggetto|layer --superfici]
                                     uso interno: converte un file in un processo separato
"""
import json
import os
import sys


def _opzione(argv, nome, predefinito=None):
    return argv[argv.index(nome) + 1] if nome in argv else predefinito


def _converti(path, uscita, dividi, modo, nomi, superfici):
    if dividi:
        from .assieme import converti_auto
        return converti_auto(path, uscita, modo, nomi, superfici)
    from .core import converti_file
    return converti_file(path, uscita)


def _worker(argv):
    inp, out_json = argv[0], argv[1]
    r = _converti(inp, _opzione(argv, "--uscita") or None, "--dividi" in argv,
                  _opzione(argv, "--modo", "assieme"), _opzione(argv, "--nomi", "oggetto"), "--superfici" in argv)
    tmp = out_json + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(r, fh, ensure_ascii=False, default=str)
    os.replace(tmp, out_json)
    return 0


def _cli(argv):
    from . import __version__, report, settings
    from .core import raccogli
    s = settings.carica()
    files = raccogli(argv)
    print(f"rhino2sw {__version__}\n")
    if not files:
        print("Nessun file .stp/.step trovato.")
        return 1
    risultati = []
    for i, p in enumerate(files, 1):
        print(f"[{i}/{len(files)}] {os.path.basename(p)} ... ", end="", flush=True)
        r = _converti(p, s["cartella_uscita_fissa"] or None, s["dividi_assiemi"], s["modo_parti"],
                      s["nome_parti"], s["includi_superfici"])
        risultati.append(r)
        if r.get("parti"):
            print(f"{r['esito']}: {r['note']}")
        elif r["esito"] == "OK":
            print(f"OK ({r['convertite']} facce convertite, {r['bspline_rimaste']} B-spline rimaste)")
        else:
            print(f"{r['esito']}: {r.get('note', '')}")
    dest, attesa = report.aggiungi(risultati, s)
    ok = sum(r["esito"] == "OK" for r in risultati)
    print(f"\nFatto: {ok}/{len(risultati)} convertiti. Rapporto: {dest}" + (" (CSV principale non raggiungibile)" if attesa else ""))
    return 0


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:1] == ["--worker"]:
        return _worker(argv[1:])
    if argv[:1] == ["--cli"]:
        return _cli(argv[1:])
    if argv[:1] in (["--versione"], ["--version"]):
        from . import __version__
        print(__version__)
        return 0
    from .gui import avvia
    return avvia(argv)


if __name__ == "__main__":
    sys.exit(main())
