# Test
`python tests/crea_pezzi_prova.py` crea in `cartella/` dei pezzi sintetici:
blocco con foro e raccordi convertito in B-spline, lo stesso spostato nello spazio,
un guscio aperto (deve risultare NON CONVERTITO) e un file corrotto (deve dare ERRORE).
Poi: `python rhino2sw.py cartella`
