"""Test della divisione in parti su un assieme sintetico.

    python tests/test_assieme.py
"""
import os
import sys
import tempfile

QUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(QUI))


def main():
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder
    from OCP.BRepBuilderAPI import BRepBuilderAPI_NurbsConvert
    from OCP.gp import gp_Trsf, gp_Vec, gp_Ax2, gp_Pnt, gp_Dir
    from OCP.TopLoc import TopLoc_Location
    from rhino2sw import assieme, core

    d = tempfile.mkdtemp(prefix="r2sw_ass_")
    perno = BRepBuilderAPI_NurbsConvert(BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1)), 4, 30).Shape(), True).Shape()
    piastra = BRepBuilderAPI_NurbsConvert(BRepPrimAPI_MakeBox(100, 50, 10).Shape(), True).Shape()

    def loc(x, y, z):
        t = gp_Trsf(); t.SetTranslation(gp_Vec(x, y, z)); return TopLoc_Location(t)

    src = os.path.join(d, "gruppo.stp")
    assieme.scrivi_assieme([("PERNO 8x30", perno, [loc(20, 25, 10), loc(80, 25, 10)]),
                            ("PIASTRA", piastra, [loc(0, 0, 0)])], src, "gruppo")
    errori = []

    def verifica(nome, cond):
        print(f"  {'ok ' if cond else 'NO '} {nome}")
        if not cond:
            errori.append(nome)

    defs = assieme.assegna_nomi(assieme.leggi_assieme(src))
    nomi = sorted(x.nome for x in defs)
    verifica("2 definizioni, 3 istanze", len(defs) == 2 and sum(len(x.istanze) for x in defs) == 3)
    verifica("nomi dai blocchi", nomi == ["PERNO 8x30", "PIASTRA"])

    r = assieme.dividi_file(src, os.path.join(d, "out1"), modo="assieme")
    verifica("esito OK", r["esito"] == "OK")
    verifica("file d'assieme scritto", os.path.exists(r["file_uscita"]))
    rilet = assieme.leggi_assieme(r["file_uscita"])
    verifica("assieme riletto: 3 istanze", sum(len(x.istanze) for x in rilet) == 3)
    tutte = core.leggi_step(r["file_uscita"])
    from OCP.Bnd import Bnd_Box
    from OCP.BRepBndLib import BRepBndLib
    b = Bnd_Box(); BRepBndLib.AddOptimal_s(tutte, b, False, False)
    verifica("posizioni conservate (box 0..100 x 0..50 x 0..40)",
             abs(b.CornerMax().X() - 100) < 0.01 and abs(b.CornerMax().Z() - 40) < 0.01 and abs(b.CornerMin().X()) < 0.01)
    perno_rp = [p for p in r["parti"] if p["file"].startswith("PERNO")][0]
    verifica("perno: cilindro riconosciuto", "cilindri" in perno_rp.get("tipi_dopo", ""))

    assieme.dividi_file(src, os.path.join(d, "out2"), modo="assolute")
    files = sorted(os.listdir(os.path.join(d, "out2", "gruppo")))
    verifica("modo assolute: 3 file", len(files) == 3)
    p2 = core.leggi_step(os.path.join(d, "out2", "gruppo", "PERNO 8x30_02_SW.stp"))
    b = Bnd_Box(); BRepBndLib.AddOptimal_s(p2, b, False, False)
    verifica("modo assolute: perno 2 in coordinate assolute (x 76..84)",
             abs(b.CornerMin().X() - 76) < 0.01 and abs(b.CornerMax().X() - 84) < 0.01)

    r3 = assieme.converti_auto(os.path.join(d, "out1", "gruppo", "parti", "PIASTRA_SW.stp"), os.path.join(d, "out3"))
    verifica("parte singola non divisa", "parti" not in r3 and r3["esito"] == "OK")
    if errori:
        print("\nFALLITO")
        return 1
    print("\nTutti i test superati")
    return 0


if __name__ == "__main__":
    sys.exit(main())
