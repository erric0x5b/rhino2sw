"""Divisione di un "assieme" Rhino (STEP con piu' corpi e blocchi) in file di parti.

Da ogni STEP esportato da Rhino si ricavano:
- le **definizioni**: ogni corpo distinto (un blocco usato 7 volte e' una definizione con 7 istanze);
- per ogni definizione il nome dell'oggetto Rhino, il nome del blocco e il layer;
- per ogni istanza la posizione nell'assieme.

Due modi di uscita:
- "assieme"  : una parte per definizione + ASSIEME_<nome>.stp che le richiama nelle posizioni di Rhino.
               Gli oggetti sciolti mantengono l'origine di Rhino; i blocchi il loro punto base.
- "assolute" : un file per ogni istanza, in coordinate assolute di Rhino (inseriti tutti
               all'origine in SolidWorks si ricompone l'assieme).
"""
import os
import re
import time

from OCP.STEPControl import STEPControl_Reader, STEPControl_AsIs
from OCP.STEPCAFControl import STEPCAFControl_Writer
from OCP.IFSelect import IFSelect_RetDone
from OCP.Interface import Interface_Static
from OCP.TopExp import TopExp_Explorer
from OCP.TopAbs import TopAbs_SOLID, TopAbs_SHELL, TopAbs_FACE
from OCP.TopLoc import TopLoc_Location
from OCP.TDocStd import TDocStd_Document
from OCP.TCollection import TCollection_ExtendedString
from OCP.TDataStd import TDataStd_Name
from OCP.XCAFApp import XCAFApp_Application
from OCP.XCAFDoc import XCAFDoc_DocumentTool

from . import core

NOME_GENERICO = re.compile(r"^(brep|shell|solid|surface|body|corpo)_?\d*$", re.I)
LAYER_GENERICI = {"livello 01", "layer 01", "default", "predefinito", ""}


class Definizione:
    def __init__(self, forma, tipo, oggetto, layer):
        self.forma = forma          # forma nelle coordinate della sua definizione (blocco o mondo)
        self.tipo = tipo            # "solido" | "superfici"
        self.oggetto = oggetto      # nome oggetto Rhino (nome della brep nello STEP)
        self.layer = layer
        self.blocchi = []           # nomi dei blocchi che la contengono
        self.istanze = []           # TopLoc_Location assolute
        self.nome = ""


def _nome_ent(e):
    try:
        return e.Name().ToCString().strip()
    except Exception:
        return ""


def _blocco(ent):
    """Nome del prodotto (blocco Rhino) di un'occorrenza d'assieme."""
    try:
        return ent.RelatedProductDefinition().Formation().OfProduct().Name().ToCString().strip()
    except Exception:
        return ""


def leggi_assieme(path):
    """Restituisce la lista di Definizione con le loro istanze."""
    tmp = core._copia_temp(path)
    try:
        with core.silenzio():
            r = STEPControl_Reader()
            if r.ReadFile(tmp) != IFSelect_RetDone:
                raise RuntimeError("file STEP non leggibile")
            r.TransferRoots()
            tutto = r.OneShape()
    finally:
        import shutil
        shutil.rmtree(os.path.dirname(tmp), ignore_errors=True)
    if tutto is None or tutto.IsNull():
        raise RuntimeError("nessuna geometria nel file")
    model = r.Model()
    trr = r.WS().TransferReader()

    # layer: entita' (brep / shell) -> nome del layer. Le entita' pybind sono confrontabili e hashabili.
    layer = {}
    for i in range(1, model.NbEntities() + 1):
        e = model.Value(i)
        if e.DynamicType().Name() == "StepVisual_PresentationLayerAssignment":
            it = e.AssignedItems()
            for k in range(it.Lower(), it.Upper() + 1):
                try:
                    layer.setdefault(it.Value(k).Value(), _nome_ent(e))
                except Exception:
                    pass

    defs = {}       # entita' STEP della definizione -> Definizione
    ordine = []

    def aggiungi(sh, tipo):
        d = sh.Located(TopLoc_Location())
        ent = trr.EntityFromShapeResult(d, -1)
        chiave = ent if ent is not None else ("forma", len(ordine))
        if chiave not in defs:
            defs[chiave] = Definizione(d, tipo, _nome_ent(ent) if ent is not None else "",
                                       layer.get(ent, "") if ent is not None else "")
            ordine.append(defs[chiave])
        df = defs[chiave]
        df.istanze.append(sh.Location())
        occ = trr.EntityFromShapeResult(sh, -1)
        if occ is not None and occ.DynamicType().Name().endswith("AssemblyUsageOccurrence"):
            b = _blocco(occ)
            if b and b not in df.blocchi:
                df.blocchi.append(b)

    e = TopExp_Explorer(tutto, TopAbs_SOLID)
    while e.More():
        aggiungi(e.Current(), "solido"); e.Next()
    e = TopExp_Explorer(tutto, TopAbs_SHELL, TopAbs_SOLID)     # gusci non chiusi in un solido
    while e.More():
        if core.conta(e.Current(), TopAbs_FACE):
            aggiungi(e.Current(), "superfici")
        e.Next()
    return ordine


def _pulisci_nome(n):
    n = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "_", n).strip(" .")
    return n[:120] or "parte"


def _ultimo_segmento(layer):
    return re.split(r"::|>", layer)[-1].strip() if layer else ""


def assegna_nomi(defs, priorita="oggetto"):
    """priorita: "oggetto" (oggetto, blocco, layer) oppure "layer" (layer, oggetto, blocco)."""
    usati = {}
    for d in defs:
        ogg = "" if NOME_GENERICO.match(d.oggetto or "") else d.oggetto
        blk = d.blocchi[0] if d.blocchi else ""
        lay = _ultimo_segmento(d.layer)
        lay = "" if lay.lower() in LAYER_GENERICI else lay
        ordine = [ogg, blk, lay] if priorita == "oggetto" else [lay, ogg, blk]
        base = next((x for x in ordine if x), "") or (d.layer or "parte")
        base = _pulisci_nome(base)
        k = base.lower()
        usati[k] = usati.get(k, 0) + 1
        d.nome = base if usati[k] == 1 else f"{base}_{usati[k]}"
    return defs


def scrivi_assieme(parti, path, nome_assieme):
    """parti: lista di (nome, forma, [TopLoc_Location]). Scrive uno STEP d'assieme con le parti incluse."""
    app = XCAFApp_Application.GetApplication_s()
    doc = TDocStd_Document(TCollection_ExtendedString("MDTV-XCAF"))
    app.InitDocument(doc)
    st = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
    asm = st.NewShape()
    TDataStd_Name.Set_s(asm, TCollection_ExtendedString(nome_assieme))
    for nome, forma, istanze in parti:
        lab = st.AddShape(forma, False, False)
        TDataStd_Name.Set_s(lab, TCollection_ExtendedString(nome))
        for loc in istanze:
            comp = st.AddComponent(asm, lab, loc)
            TDataStd_Name.Set_s(comp, TCollection_ExtendedString(nome))
    st.UpdateAssemblies()
    Interface_Static.SetCVal_s("write.step.schema", "AP214IS")
    Interface_Static.SetCVal_s("write.step.unit", "MM")
    import tempfile, shutil
    tmp = os.path.join(tempfile.mkdtemp(prefix="rhino2sw_"), "asm.stp")
    try:
        with core.silenzio():
            w = STEPCAFControl_Writer()
            w.SetNameMode(True)
            ok = w.Transfer(doc, STEPControl_AsIs) and w.Write(tmp) == IFSelect_RetDone
        if not ok:
            raise RuntimeError("scrittura dello STEP d'assieme fallita")
        shutil.copyfile(tmp, path)
    finally:
        shutil.rmtree(os.path.dirname(tmp), ignore_errors=True)


def converti_auto(path, cartella_fissa=None, modo="assieme", priorita="oggetto", includi_superfici=False):
    """Se il file contiene un solo corpo lo tratta come parte singola, altrimenti lo divide."""
    try:
        defs = leggi_assieme(path)
    except Exception:
        return core.converti_file(path, cartella_fissa)      # stesso messaggio d'errore della parte singola
    solidi = [d for d in defs if d.tipo == "solido"]
    if len(solidi) == 1 and len(solidi[0].istanze) == 1 and (len(defs) == 1 or not includi_superfici):
        return core.converti_file(path, cartella_fissa)
    return dividi_file(path, cartella_fissa, modo, priorita, includi_superfici, defs=defs)


def dividi_file(path, cartella_fissa=None, modo="assieme", priorita="oggetto", includi_superfici=False, defs=None):
    """Divide e pulisce. Restituisce il rapporto del file con l'elenco 'parti' (non solleva eccezioni)."""
    t0 = time.time()
    base = os.path.splitext(os.path.basename(path))[0]
    r = {"file": os.path.basename(path), "percorso": path, "esito": "", "note": "", "parti": []}
    try:
        defs = assegna_nomi(defs if defs is not None else leggi_assieme(path), priorita)
        dout = os.path.join(core.cartella_uscita(path, cartella_fissa), base)
        os.makedirs(dout, exist_ok=True)
        saltate = [d for d in defs if d.tipo == "superfici" and not includi_superfici]
        da_fare = [d for d in defs if d not in saltate]
        per_assieme = []
        tot_conv = 0
        for d in da_fare:
            try:
                rp, pulita = core.elabora_forma(d.forma, d.nome)
            except Exception as ex:      # errore del motore su questa parte: le altre proseguono
                rp, pulita = {"esito": "ERRORE", "note": f"errore del motore geometrico: {ex}"}, None
            if pulita is None:
                forma = d.forma          # la parte serve comunque per l'assieme: originale non pulito
                if d.tipo == "superfici":
                    rp["esito"] = "SUPERFICI"
                    rp["note"] = "superfici aperte (non un solido): esportate senza pulizia"
                else:
                    rp["note"] = (rp.get("note") or "") + " -> esportata la parte originale, non pulita"
            else:
                forma = pulita
                tot_conv += rp.get("convertite", 0)
            rp.update(file=f"{d.nome}  [{r['file']}]", percorso=path, istanze=len(d.istanze),
                      oggetto_rhino=d.oggetto, blocco=", ".join(d.blocchi), layer=d.layer)
            if modo == "assolute":
                uscite = []
                for i, loc in enumerate(d.istanze, 1):
                    nome = d.nome if len(d.istanze) == 1 else f"{d.nome}_{i:02d}"
                    fout = os.path.join(dout, nome + "_SW.stp")
                    core.scrivi_step(forma.Moved(loc), fout)
                    uscite.append(fout)
                rp["file_uscita"] = uscite[0]
            else:
                fout = os.path.join(dout, "parti", d.nome + "_SW.stp")
                os.makedirs(os.path.dirname(fout), exist_ok=True)
                core.scrivi_step(forma, fout)
                rp["file_uscita"] = fout
                per_assieme.append((d.nome, forma, d.istanze))
            r["parti"].append(rp)
        if modo == "assieme" and per_assieme:
            fa = os.path.join(dout, f"ASSIEME_{base}.stp")
            scrivi_assieme(per_assieme, fa, base)
            r["file_uscita"] = fa
        else:
            r["file_uscita"] = dout
        esiti = [p["esito"] for p in r["parti"]]
        n_ok = esiti.count("OK")
        r["convertite"] = tot_conv
        r["bspline_rimaste"] = sum(p.get("bspline_rimaste") or 0 for p in r["parti"])
        r["scost_max_mm"] = max([p.get("scost_max_mm") or 0 for p in r["parti"]] or [0])
        r["parti_tot"] = len(r["parti"])
        r["istanze_tot"] = sum(len(d.istanze) for d in da_fare)
        r["esito"] = "OK" if n_ok == len(esiti) and esiti else ("PARZIALE" if n_ok else "NON CONVERTITO")
        note = [f"{len(r['parti'])} parti ({r['istanze_tot']} istanze), {n_ok} pulite"]
        if n_ok < len(esiti):
            note.append(f"{len(esiti) - n_ok} esportate senza pulizia (vedi righe delle parti)")
        if saltate:
            note.append(f"{len(saltate)} gruppi di superfici aperte non esportati")
        r["note"] = "; ".join(note)
    except RuntimeError as ex:
        r.update(esito="ERRORE", note=str(ex))
    except Exception as ex:
        r.update(esito="ERRORE", note=f"errore interno: {ex!r}")
    r["secondi"] = round(time.time() - t0, 1)
    r["data_ora"] = time.strftime("%Y-%m-%d %H:%M:%S")
    r["versione"] = core.VERSIONE
    for p in r["parti"]:
        p.setdefault("data_ora", r["data_ora"]); p.setdefault("versione", r["versione"])
    return r
