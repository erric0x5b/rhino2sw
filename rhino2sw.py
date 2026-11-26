"""
rhino2sw - Pulizia di file STEP esportati da Rhino per SolidWorks.

Converte le facce B-spline che sono in realta' piani, cilindri e coni in
geometria analitica vera, unisce le facce spezzate, verifica il solido e
scrive uno STEP AP214 per SolidWorks. Se il risultato non supera i controlli
il file NON viene scritto e il rapporto lo segnala.

Uso:
    python rhino2sw.py file1.stp file2.step cartella ...
    python rhino2sw.py            (apre una finestra per scegliere i file)
"""
import sys, os, csv, time, math, collections, traceback

VERSIONE = "0.1.1"
TOL_CONV = 0.001        # mm: scostamento massimo ammesso per riconoscere piano/cilindro/cono
TOL_DEV_MAX = 0.005     # mm: scostamento massimo ammesso tra originale e ripulito
TOL_VOL_REL = 1e-5      # differenza relativa di volume massima ammessa
TOL_GAP = 0.001         # mm: soglia per segnalare spigoli con gap
CONVERTI_TORI = False   # i raccordi a toro davano facce non valide: per ora restano B-spline
CARTELLA_USCITA = "per_SolidWorks"

from OCP.STEPControl import STEPControl_Reader, STEPControl_Writer, STEPControl_AsIs
from OCP.Interface import Interface_Static
from OCP.IFSelect import IFSelect_RetDone
from OCP.TopExp import TopExp_Explorer
from OCP.TopAbs import TopAbs_FACE, TopAbs_EDGE, TopAbs_SOLID, TopAbs_SHELL, TopAbs_IN
from OCP.TopoDS import TopoDS, TopoDS_Compound
from OCP.BRep import BRep_Tool, BRep_Builder
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepBuilderAPI import (BRepBuilderAPI_Copy, BRepBuilderAPI_Sewing,
                                BRepBuilderAPI_MakeSolid, BRepBuilderAPI_MakeVertex)
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps
from OCP.ShapeAnalysis import ShapeAnalysis_Surface
from OCP.ShapeUpgrade import ShapeUpgrade_UnifySameDomain
from OCP.ShapeFix import ShapeFix_Shape, ShapeFix_Edge, ShapeFix_Solid
from OCP.GeomConvert import GeomConvert_SurfToAnaSurf
from OCP.GeomLProp import GeomLProp_SLProps
from OCP.BRepTools import BRepTools
from OCP.BRepExtrema import BRepExtrema_DistShapeShape
from OCP.BRepClass import BRepClass_FaceClassifier
from OCP.gp import gp_Pnt2d
from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib
from OCP.TopLoc import TopLoc_Location

import contextlib

try:  # spegne i messaggi tecnici di OpenCASCADE
    from OCP.Message import Message
    _m = Message.DefaultMessenger_s()
    for _p in list(_m.Printers()):
        _m.RemovePrinter(_p)
except Exception:
    pass

@contextlib.contextmanager
def silenzio():
    """Nasconde i messaggi tecnici di OpenCASCADE (scritti direttamente su stdout/stderr)."""
    sys.stdout.flush(); sys.stderr.flush()
    salvati = []
    try:
        nul = os.open(os.devnull, os.O_WRONLY)
        for fd in (1, 2):
            salvati.append((fd, os.dup(fd))); os.dup2(nul, fd)
        os.close(nul)
    except Exception:
        pass
    try:
        yield
    finally:
        for fd, copia in salvati:
            os.dup2(copia, fd); os.close(copia)

NOMI = {"Plane": "piani", "Cylinder": "cilindri", "Cone": "coni", "Sphere": "sfere",
        "Torus": "tori", "BSpline": "B-spline", "Bezier": "Bezier",
        "SurfaceOfRevolution": "rivoluzione", "SurfaceOfExtrusion": "estrusione",
        "OffsetSurface": "offset", "OtherSurface": "altre"}


def facce(sh):
    e = TopExp_Explorer(sh, TopAbs_FACE)
    while e.More():
        yield TopoDS.Face(e.Current()); e.Next()


def conta(sh, tipo):
    n = 0; e = TopExp_Explorer(sh, tipo)
    while e.More():
        n += 1; e.Next()
    return n


def tipo_faccia(f):
    t = str(BRepAdaptor_Surface(f).GetType()).split("GeomAbs_")[-1]
    return t[:-7] if t.endswith("Surface") and t not in ("OffsetSurface", "OtherSurface",
                                                         "SurfaceOfRevolution", "SurfaceOfExtrusion") else t


def tipi(sh):
    return collections.Counter(tipo_faccia(f) for f in facce(sh))


def volume(sh):
    g = GProp_GProps(); BRepGProp.VolumeProperties_s(sh, g, 1e-7); return g.Mass()


def gap_spigoli(sh):
    visti = set(); n = 0; mx = 0.0
    e = TopExp_Explorer(sh, TopAbs_EDGE)
    while e.More():
        ed = e.Current(); h = ed.HashCode(2**31 - 1) if hasattr(ed, "HashCode") else hash(ed)
        if h not in visti:
            visti.add(h)
            t = BRep_Tool.Tolerance_s(TopoDS.Edge(ed))
            mx = max(mx, t)
            if t > TOL_GAP: n += 1
        e.Next()
    return n, mx


def _copia_temp(path):
    """OpenCASCADE puo' avere problemi con percorsi con accenti/rete: lavora su una copia locale."""
    import tempfile, shutil
    d = tempfile.mkdtemp(prefix="rhino2sw_")
    dst = os.path.join(d, "in" + os.path.splitext(path)[1].lower())
    shutil.copyfile(path, dst)
    return dst


def leggi_step(path):
    path = _copia_temp(path)
    with silenzio():
        r = STEPControl_Reader()
        ok = r.ReadFile(path) == IFSelect_RetDone
        if ok:
            r.TransferRoots()
            s = r.OneShape()
    if not ok:
        raise RuntimeError("file STEP non leggibile")
    if s is None or s.IsNull():
        raise RuntimeError("nessuna geometria nel file")
    return s


def chiudi_in_solidi(s):
    """Se arrivano solo superfici prova a cucirle e farne solidi."""
    if conta(s, TopAbs_SOLID) > 0 or conta(s, TopAbs_SHELL) == 0:
        return s, False
    sew = BRepBuilderAPI_Sewing(0.01); sew.Add(s); sew.Perform()
    cucito = sew.SewedShape()
    B = BRep_Builder(); comp = TopoDS_Compound(); B.MakeCompound(comp); fatti = 0
    e = TopExp_Explorer(cucito, TopAbs_SHELL)
    while e.More():
        sh = TopoDS.Shell(e.Current())
        if not BRep_Tool.IsClosed_s(sh):      # guscio aperto: non e' un solido
            e.Next(); continue
        ms = BRepBuilderAPI_MakeSolid(sh)
        if ms.IsDone():
            fs = ShapeFix_Solid(ms.Solid()); fs.Perform(); B.Add(comp, fs.Solid()); fatti += 1
        e.Next()
    return (comp, True) if fatti else (s, False)


def converti_analitiche(s):
    B = BRep_Builder(); n = 0
    for f in list(facce(s)):
        if tipo_faccia(f) not in ("BSpline", "Bezier"):
            continue
        surf = BRep_Tool.Surface_s(f)
        ns = GeomConvert_SurfToAnaSurf(surf).ConvertToAnalytical(TOL_CONV)
        if ns is None:
            continue
        if not CONVERTI_TORI and "Toroidal" in type(ns).__name__:
            continue
        u1, u2, v1, v2 = BRepTools.UVBounds_s(f)
        pr = GeomLProp_SLProps(surf, (u1 + u2) / 2, (v1 + v2) / 2, 1, 1e-6)
        if not pr.IsNormalDefined():
            continue
        sa = ShapeAnalysis_Surface(ns); uv = sa.ValueOfUV(pr.Value(), 1e-3)
        if sa.Gap() > TOL_CONV * 2:
            continue
        pr2 = GeomLProp_SLProps(ns, uv.X(), uv.Y(), 1, 1e-6)
        if not pr2.IsNormalDefined():
            continue
        if pr.Normal().Dot(pr2.Normal()) < 0:
            ns.UReverse()
        tol = max(BRep_Tool.Tolerance_s(f), sa.Gap())
        spig = []; e = TopExp_Explorer(f, TopAbs_EDGE)
        while e.More():
            spig.append(TopoDS.Edge(e.Current())); e.Next()
        B.UpdateFace(f, ns, TopLoc_Location(), tol)   # surf e' gia' in coordinate globali
        for ed in spig:
            B.UpdateEdge(ed, None, f, tol)   # toglie le vecchie curve parametriche
        n += 1
    fe = ShapeFix_Edge()
    for f in facce(s):
        e = TopExp_Explorer(f, TopAbs_EDGE)
        while e.More():
            fe.FixAddPCurve(TopoDS.Edge(e.Current()), f, False, 1e-4); e.Next()
    return n


def scostamento_max(nuovo, orig, campioni=4):
    """Distanza massima di punti campionati sulle facce nuove dalla geometria originale."""
    rif = []
    for f in facce(orig):
        b = Bnd_Box(); BRepBndLib.Add_s(f, b); b.Enlarge(0.05)
        rif.append((f, b, ShapeAnalysis_Surface(BRep_Tool.Surface_s(f))))
    dss = None
    mx = 0.0; npt = 0
    for f in facce(nuovo):
        S = BRep_Tool.Surface_s(f); u1, u2, v1, v2 = BRepTools.UVBounds_s(f)
        for i in range(1, campioni + 1):
            for j in range(1, campioni + 1):
                u = u1 + (u2 - u1) * i / (campioni + 1); v = v1 + (v2 - v1) * j / (campioni + 1)
                if BRepClass_FaceClassifier(f, gp_Pnt2d(u, v), 1e-6).State() != TopAbs_IN:
                    continue
                p = S.Value(u, v); best = None
                for fo, bo, sa in rif:
                    if bo.IsOut(p):
                        continue
                    uv = sa.ValueOfUV(p, 1e-7)
                    if BRepClass_FaceClassifier(fo, uv, 1e-4).State() == TopAbs_IN:
                        g = sa.Gap(); best = g if best is None else min(best, g)
                if best is None or best > TOL_DEV_MAX:   # verifica esatta solo se serve
                    if dss is None:
                        dss = BRepExtrema_DistShapeShape(); dss.LoadS2(orig)
                    dss.LoadS1(BRepBuilderAPI_MakeVertex(p).Vertex()); dss.Perform()
                    best = dss.Value()
                mx = max(mx, best); npt += 1
    return mx, npt


def scrivi_step(s, path_finale):
    import tempfile, shutil
    path = os.path.join(tempfile.mkdtemp(prefix="rhino2sw_"), "out.stp")
    Interface_Static.SetCVal_s("write.step.schema", "AP214IS")
    Interface_Static.SetCVal_s("write.step.unit", "MM")
    with silenzio():
        w = STEPControl_Writer(); w.Transfer(s, STEPControl_AsIs)
        ok = w.Write(path) == IFSelect_RetDone
    if not ok:
        raise RuntimeError("scrittura STEP fallita")
    shutil.copyfile(path, path_finale)


def fmt_tipi(c):
    return ", ".join(f"{v} {NOMI.get(k, k)}" for k, v in sorted(c.items(), key=lambda x: -x[1]))


def elabora(path):
    t0 = time.time()
    r = {"file": os.path.basename(path), "esito": "", "note": ""}
    orig = leggi_step(path)
    orig, cucito = chiudi_in_solidi(orig)
    r["solidi"] = conta(orig, TopAbs_SOLID)
    if r["solidi"] == 0:
        r["esito"] = "NON CONVERTITO"
        r["note"] = "nel file ci sono solo superfici aperte: il pezzo non e' chiuso, va sistemato in Rhino"
        return r, None
    v0 = volume(orig); c0 = tipi(orig)
    r["facce_prima"] = sum(c0.values()); r["tipi_prima"] = fmt_tipi(c0)
    r["valido_prima"] = BRepCheck_Analyzer(orig).IsValid()

    s = BRepBuilderAPI_Copy(orig).Shape()
    r["convertite"] = converti_analitiche(s)
    fx = ShapeFix_Shape(s); fx.Perform(); s = fx.Shape()
    u = ShapeUpgrade_UnifySameDomain(s, True, True, False); u.Build(); s = u.Shape()
    fx = ShapeFix_Shape(s); fx.Perform(); s = fx.Shape()

    c1 = tipi(s); v1 = volume(s)
    r["facce_dopo"] = sum(c1.values()); r["tipi_dopo"] = fmt_tipi(c1)
    r["bspline_rimaste"] = c1.get("BSpline", 0) + c1.get("Bezier", 0)
    r["valido_dopo"] = BRepCheck_Analyzer(s).IsValid()
    r["solidi_dopo"] = conta(s, TopAbs_SOLID)
    r["volume_mm3"] = round(v0, 2)
    r["diff_volume_%"] = round(100 * (v1 - v0) / v0, 6) if v0 else 0
    r["scost_max_mm"], _ = scostamento_max(s, orig)
    r["scost_max_mm"] = round(r["scost_max_mm"], 5)
    r["spigoli_gap"], gmax = gap_spigoli(s); r["gap_max_mm"] = round(gmax, 4)

    problemi = []
    if not r["valido_dopo"]: problemi.append("solido non valido dopo la conversione")
    if r["solidi_dopo"] != r["solidi"]: problemi.append("numero di solidi cambiato")
    if v0 and abs(v1 - v0) / abs(v0) > TOL_VOL_REL: problemi.append("volume cambiato")
    if r["scost_max_mm"] > TOL_DEV_MAX: problemi.append("geometria spostata oltre la tolleranza")
    note = []
    if cucito: note.append("il file conteneva superfici: cucite in solido")
    if r["spigoli_gap"]: note.append(f"{r['spigoli_gap']} spigoli con gap > {TOL_GAP} mm (max {r['gap_max_mm']} mm): se SolidWorks segnala errori, guardare li'")
    if r["bspline_rimaste"]: note.append(f"{r['bspline_rimaste']} facce restano B-spline (forme libere o raccordi): su quelle niente accoppiamenti/quote di raggio")
    if problemi:
        r["esito"] = "NON CONVERTITO"
        r["note"] = "; ".join(problemi + note) + " -> usare il file originale"
        return r, None
    r["esito"] = "OK"
    r["note"] = "; ".join(note)
    r["secondi"] = round(time.time() - t0, 1)
    return r, s


def raccogli(argomenti):
    out = []
    for a in argomenti:
        a = a.strip('"')
        if os.path.isdir(a):
            for root, dirs, files in os.walk(a):
                if CARTELLA_USCITA in os.path.basename(root):
                    continue
                out += [os.path.join(root, f) for f in files if f.lower().endswith((".stp", ".step"))]
        elif a.lower().endswith((".stp", ".step")) and os.path.isfile(a):
            out.append(a)
    return sorted(set(out))


def scegli_file():
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk(); root.withdraw()
        f = filedialog.askopenfilenames(title="Scegli i file STEP esportati da Rhino",
                                        filetypes=[("STEP", "*.stp *.step"), ("Tutti", "*.*")])
        root.destroy(); return list(f)
    except Exception:
        return []


def main():
    print(f"rhino2sw {VERSIONE} - pulizia STEP da Rhino per SolidWorks\n")
    files = raccogli(sys.argv[1:]) if len(sys.argv) > 1 else raccogli(scegli_file())
    if not files:
        print("Nessun file .stp/.step trovato. Trascina file o cartelle sull'icona 'Converti'.")
        return 1
    risultati = []
    for i, p in enumerate(files, 1):
        print(f"[{i}/{len(files)}] {os.path.basename(p)} ... ", end="", flush=True)
        try:
            r, s = elabora(p)
            if s is not None:
                dout = os.path.join(os.path.dirname(p), CARTELLA_USCITA); os.makedirs(dout, exist_ok=True)
                fout = os.path.join(dout, os.path.splitext(os.path.basename(p))[0] + "_SW.stp")
                scrivi_step(s, fout); r["file_uscita"] = fout
                print(f"OK  ({r['convertite']} facce convertite, {r['bspline_rimaste']} B-spline rimaste)")
            else:
                print(f"NON CONVERTITO: {r['note']}")
        except RuntimeError as ex:
            r = {"file": os.path.basename(p), "esito": "ERRORE", "note": str(ex)}
            print(f"ERRORE: {ex}")
        except Exception as ex:
            r = {"file": os.path.basename(p), "esito": "ERRORE", "note": f"errore interno: {ex!r}"}
            print(f"ERRORE INTERNO: {ex!r}")
            traceback.print_exc()
        r["percorso"] = p
        risultati.append(r)

    # rapporto nella cartella del primo file
    dout = os.path.join(os.path.dirname(files[0]), CARTELLA_USCITA); os.makedirs(dout, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    campi = ["file", "esito", "solidi", "facce_prima", "facce_dopo", "convertite", "bspline_rimaste",
             "tipi_prima", "tipi_dopo", "volume_mm3", "diff_volume_%", "scost_max_mm",
             "spigoli_gap", "gap_max_mm", "note", "percorso", "file_uscita"]
    with open(os.path.join(dout, f"rapporto_{stamp}.csv"), "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=campi, delimiter=";", extrasaction="ignore"); w.writeheader()
        for r in risultati: w.writerow(r)
    with open(os.path.join(dout, f"rapporto_{stamp}.txt"), "w", encoding="utf-8") as fh:
        fh.write(f"rhino2sw {VERSIONE} - {time.strftime('%d/%m/%Y %H:%M')}\n\n")
        for r in risultati:
            fh.write(f"=== {r['file']}: {r['esito']}\n")
            if "facce_prima" in r:
                fh.write(f"  prima: {r['facce_prima']} facce ({r['tipi_prima']})\n")
            if "facce_dopo" in r:
                fh.write(f"  dopo:  {r['facce_dopo']} facce ({r['tipi_dopo']})\n")
                fh.write(f"  volume {r['volume_mm3']} mm3, differenza {r['diff_volume_%']}%, scostamento max {r['scost_max_mm']} mm\n")
            if r.get("note"): fh.write(f"  note: {r['note']}\n")
            if r.get("file_uscita"): fh.write(f"  -> {r['file_uscita']}\n")
            fh.write("\n")
    ok = sum(r["esito"] == "OK" for r in risultati)
    print(f"\nFatto: {ok}/{len(risultati)} convertiti. File e rapporto in: {dout}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
