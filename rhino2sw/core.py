"""
rhino2sw.core - motore di conversione.

Converte le facce B-spline che sono in realta' piani, cilindri e coni in
geometria analitica vera, unisce le facce spezzate, verifica il solido e
scrive uno STEP AP214 per SolidWorks. Se il risultato non supera i controlli
il file NON viene scritto e il rapporto lo segnala.

"""
import sys, os, time, collections, shutil, tempfile

from . import __version__ as VERSIONE
TOL_CONV = 0.001        # mm: scostamento massimo ammesso per riconoscere piano/cilindro/cono
TOL_DEV_MAX = 0.005     # mm: scostamento massimo ammesso tra originale e ripulito
TOL_VOL_REL = 1e-5      # differenza relativa di volume massima ammessa
TOL_AREA_REL = 1e-5     # differenza relativa di area totale massima ammessa
TOL_GAP = 0.001         # mm: soglia per segnalare spigoli con gap
CONVERTI_TORI = False   # i raccordi a toro davano facce non valide: per ora restano B-spline
CARTELLA_USCITA = "per_SolidWorks"

from OCP.STEPControl import STEPControl_Reader, STEPControl_Writer, STEPControl_AsIs
from OCP.Interface import Interface_Static
from OCP.IFSelect import IFSelect_RetDone
from OCP.TopExp import TopExp_Explorer
from OCP.TopAbs import TopAbs_FACE, TopAbs_EDGE, TopAbs_SOLID, TopAbs_SHELL, TopAbs_OUT
from OCP.TopoDS import TopoDS, TopoDS_Compound
from OCP.BRep import BRep_Tool, BRep_Builder
from OCP.BRepAdaptor import BRepAdaptor_Surface, BRepAdaptor_Curve2d
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepBuilderAPI import (BRepBuilderAPI_Copy, BRepBuilderAPI_Sewing,
                                BRepBuilderAPI_MakeSolid)
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps
from OCP.ShapeAnalysis import ShapeAnalysis_Surface
from OCP.ShapeUpgrade import ShapeUpgrade_UnifySameDomain
from OCP.ShapeFix import ShapeFix_Shape, ShapeFix_Edge, ShapeFix_Solid
from OCP.GeomConvert import GeomConvert_SurfToAnaSurf
from OCP.GeomLProp import GeomLProp_SLProps
from OCP.BRepTools import BRepTools
from OCP.BRepClass import BRepClass_FaceClassifier
from OCP.gp import gp_Pnt2d
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
    for st in (sys.stdout, sys.stderr):   # in un exe senza console sono None
        try:
            if st is not None:
                st.flush()
        except Exception:
            pass
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


def area(sh):
    g = GProp_GProps(); BRepGProp.SurfaceProperties_s(sh, g, 1e-7); return g.Mass()


def facce_non_valide(sh):
    return sum(1 for f in facce(sh) if not BRepCheck_Analyzer(f).IsValid())


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
    d = tempfile.mkdtemp(prefix="rhino2sw_")
    dst = os.path.join(d, "in" + os.path.splitext(path)[1].lower())
    shutil.copyfile(path, dst)
    return dst


def leggi_step(path):
    path = _copia_temp(path)
    try:
        with silenzio():
            r = STEPControl_Reader()
            ok = r.ReadFile(path) == IFSelect_RetDone
            if ok:
                r.TransferRoots()
                s = r.OneShape()
    finally:
        shutil.rmtree(os.path.dirname(path), ignore_errors=True)
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


def _scostamento_faccia(f, surf_orig, ns, campioni=5):
    """Distanza massima tra punti della faccia originale (dentro i suoi bordi) e la nuova superficie."""
    sa = ShapeAnalysis_Surface(ns)
    u1, u2, v1, v2 = BRepTools.UVBounds_s(f)
    mx = 0.0; n = 0
    for i in range(campioni + 2):
        for j in range(campioni + 2):
            u = u1 + (u2 - u1) * i / (campioni + 1); v = v1 + (v2 - v1) * j / (campioni + 1)
            if BRepClass_FaceClassifier(f, gp_Pnt2d(u, v), 1e-6).State() == TopAbs_OUT:
                continue
            sa.ValueOfUV(surf_orig.Value(u, v), 1e-7)
            mx = max(mx, sa.Gap()); n += 1
    # anche lungo i bordi: punti delle curve parametriche sulla superficie originale
    e = TopExp_Explorer(f, TopAbs_EDGE)
    while e.More():
        c2 = BRepAdaptor_Curve2d(TopoDS.Edge(e.Current()), f)
        a, b = c2.FirstParameter(), c2.LastParameter()
        for k in range(1, 6):
            uv = c2.Value(a + (b - a) * k / 6)
            sa.ValueOfUV(surf_orig.Value(uv.X(), uv.Y()), 1e-7)
            mx = max(mx, sa.Gap()); n += 1
        e.Next()
    return mx if n else float("inf")


def converti_analitiche(s):
    """Sostituisce le B-spline riconosciute. Restituisce (facce convertite, scostamento massimo, scartate)."""
    B = BRep_Builder(); n = 0; dev_max = 0.0; scartate = 0
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
        dev = _scostamento_faccia(f, surf, ns)
        if dev > TOL_DEV_MAX:       # entro la tolleranza al centro ma non su tutta la faccia: non tocco
            scartate += 1
            continue
        dev_max = max(dev_max, dev)
        tol = max(BRep_Tool.Tolerance_s(f), sa.Gap(), dev)
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
    return n, dev_max, scartate


def scrivi_step(s, path_finale):
    path = os.path.join(tempfile.mkdtemp(prefix="rhino2sw_"), "out.stp")
    Interface_Static.SetCVal_s("write.step.schema", "AP214IS")
    Interface_Static.SetCVal_s("write.step.unit", "MM")
    with silenzio():
        w = STEPControl_Writer(); w.Transfer(s, STEPControl_AsIs)
        ok = w.Write(path) == IFSelect_RetDone
    try:
        if not ok:
            raise RuntimeError("scrittura STEP fallita")
        shutil.copyfile(path, path_finale)
    finally:
        shutil.rmtree(os.path.dirname(path), ignore_errors=True)


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
    v0 = volume(orig); a0 = area(orig); c0 = tipi(orig)
    r["facce_prima"] = sum(c0.values()); r["tipi_prima"] = fmt_tipi(c0)
    r["valido_prima"] = BRepCheck_Analyzer(orig).IsValid()
    r["facce_non_valide_prima"] = 0 if r["valido_prima"] else facce_non_valide(orig)

    s = BRepBuilderAPI_Copy(orig).Shape()
    r["convertite"], dev, scartate = converti_analitiche(s)
    fx = ShapeFix_Shape(s); fx.Perform(); s = fx.Shape()
    u = ShapeUpgrade_UnifySameDomain(s, True, True, False); u.Build(); s = u.Shape()
    fx = ShapeFix_Shape(s); fx.Perform(); s = fx.Shape()

    c1 = tipi(s); v1 = volume(s); a1 = area(s)
    r["facce_dopo"] = sum(c1.values()); r["tipi_dopo"] = fmt_tipi(c1)
    r["bspline_rimaste"] = c1.get("BSpline", 0) + c1.get("Bezier", 0)
    r["valido_dopo"] = BRepCheck_Analyzer(s).IsValid()
    r["solidi_dopo"] = conta(s, TopAbs_SOLID)
    r["volume_mm3"] = round(v0, 2)
    r["diff_volume_%"] = round(100 * (v1 - v0) / v0, 6) if v0 else 0
    r["diff_area_%"] = round(100 * (a1 - a0) / a0, 6) if a0 else 0
    r["scost_max_mm"] = round(dev, 5)
    r["spigoli_gap"], gmax = gap_spigoli(s); r["gap_max_mm"] = round(gmax, 4)

    problemi = []
    if not r["valido_dopo"]:
        if r["valido_prima"]:
            problemi.append("solido non valido dopo la conversione")
        else:
            # il file di Rhino era gia' difettoso: accettiamo se la conversione non aggiunge difetti
            r["facce_non_valide_dopo"] = facce_non_valide(s)
            if r["facce_non_valide_dopo"] > r["facce_non_valide_prima"]:
                problemi.append(f"la conversione aggiunge facce non valide ({r['facce_non_valide_prima']} -> "
                                f"{r['facce_non_valide_dopo']})")
    if r["solidi_dopo"] != r["solidi"]: problemi.append("numero di solidi cambiato")
    if v0 and abs(v1 - v0) / abs(v0) > TOL_VOL_REL: problemi.append("volume cambiato")
    if a0 and abs(a1 - a0) / abs(a0) > TOL_AREA_REL: problemi.append("superficie totale cambiata (bordi delle facce alterati)")
    if r["scost_max_mm"] > TOL_DEV_MAX: problemi.append("geometria spostata oltre la tolleranza")
    note = []
    if cucito: note.append("il file conteneva superfici: cucite in solido")
    if not r["valido_prima"]:
        note.append(f"il file originale di Rhino ha gia' {r['facce_non_valide_prima']} facce difettose "
                    f"(la conversione non le peggiora): se SolidWorks le segnala, la correzione va fatta in Rhino")
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


ESTENSIONI = (".stp", ".step")


def cartella_uscita(path, cartella_fissa=None):
    if cartella_fissa:
        return cartella_fissa
    return os.path.join(os.path.dirname(path), CARTELLA_USCITA)


def converti_file(path, cartella_fissa=None):
    """Converte un file e restituisce il dizionario del rapporto (non solleva eccezioni)."""
    t0 = time.time()
    try:
        r, s = elabora(path)
        if s is not None:
            dout = cartella_uscita(path, cartella_fissa)
            os.makedirs(dout, exist_ok=True)
            fout = os.path.join(dout, os.path.splitext(os.path.basename(path))[0] + "_SW.stp")
            scrivi_step(s, fout)
            r["file_uscita"] = fout
    except RuntimeError as ex:
        r = {"file": os.path.basename(path), "esito": "ERRORE", "note": str(ex)}
    except Exception as ex:  # errore interno: lo riportiamo, non blocchiamo il resto
        r = {"file": os.path.basename(path), "esito": "ERRORE", "note": f"errore interno: {ex!r}"}
    r["percorso"] = path
    r["secondi"] = round(time.time() - t0, 1)
    r["data_ora"] = time.strftime("%Y-%m-%d %H:%M:%S")
    r["versione"] = VERSIONE
    return r


def raccogli(argomenti):
    """Espande file e cartelle in un elenco di file STEP."""
    out = []
    for a in argomenti:
        a = str(a).strip('"')
        if os.path.isdir(a):
            for root, dirs, files in os.walk(a):
                dirs[:] = [d for d in dirs if d != CARTELLA_USCITA]
                out += [os.path.join(root, f) for f in files if f.lower().endswith(ESTENSIONI)]
        elif a.lower().endswith(ESTENSIONI) and os.path.isfile(a):
            out.append(a)
    return sorted(set(os.path.normpath(p) for p in out))


