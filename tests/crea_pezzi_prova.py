from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder
from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut
from OCP.BRepFilletAPI import BRepFilletAPI_MakeFillet
from OCP.BRepBuilderAPI import BRepBuilderAPI_NurbsConvert, BRepBuilderAPI_Transform
from OCP.STEPControl import STEPControl_Writer, STEPControl_AsIs
from OCP.gp import gp_Ax2,gp_Pnt,gp_Dir,gp_Trsf,gp_Vec
from OCP.TopExp import TopExp_Explorer
from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE
from OCP.TopoDS import TopoDS
from OCP.BRep import BRep_Builder
from OCP.TopoDS import TopoDS_Compound
b=BRepPrimAPI_MakeBox(100,60,20).Shape()
c=BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(50,30,-1),gp_Dir(0,0,1)),8,30).Shape()
s=BRepAlgoAPI_Cut(b,c).Shape()
fl=BRepFilletAPI_MakeFillet(s); e=TopExp_Explorer(s,TopAbs_EDGE); i=0
while e.More() and i<4: fl.Add(3,TopoDS.Edge(e.Current())); i+=1; e.Next()
s=fl.Shape()
n=BRepBuilderAPI_NurbsConvert(s,True).Shape()
t=gp_Trsf(); t.SetTranslation(gp_Vec(200,-50,300)); n2=BRepBuilderAPI_Transform(n,t,False).Shape()
def w(sh,p):
    W=STEPControl_Writer(); W.Transfer(sh,STEPControl_AsIs); W.Write(p)
import os; os.makedirs('cartella/sub',exist_ok=True)
w(n,'cartella/blocco_nurbs.stp'); w(n2,'cartella/sub/blocco_spostato.step')
# open shell: drop one face
B=BRep_Builder(); comp=TopoDS_Compound(); B.MakeCompound(comp); e=TopExp_Explorer(n,TopAbs_FACE); first=True
while e.More():
    if not first: B.Add(comp,e.Current())
    first=False; e.Next()
w(comp,'cartella/aperto.stp')
open('cartella/rotto.stp','w').write('non sono uno step')
