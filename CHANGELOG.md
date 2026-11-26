# Changelog

## 0.2.0 – 2026-11-26
- **Applicazione Windows** con installatore (Inno Setup) e pacchetto portatile: Python e librerie
  inclusi, installazione per utente senza diritti di amministratore, voce opzionale nel menu «Invia a».
- **Finestra** (PySide6): elenco file con trascinamento di file e cartelle, conversione in parallelo
  con avanzamento e pulsante Ferma, tabella dei rapporti con ricerca e filtro per esito, impostazioni.
- Ogni file viene convertito in un **processo separato** con tempo massimo: un crash del motore
  geometrico su un pezzo non blocca gli altri e viene riportato come ERRORE.
- **Rapporti in un unico CSV** (`%LOCALAPPDATA%\rhino2sw\rapporti_rhino2sw.csv` o cartella di rete
  configurabile), con data, utente, PC e versione; decimali con la virgola per Excel; righe tenute da
  parte se il CSV è bloccato. Importazione dei rapporti della 0.1.
- Cartella di uscita configurabile (accanto agli originali o cartella fissa).
- Pulizia dei file temporanei; test automatici e build su GitHub Actions.
- Codice riorganizzato nel pacchetto `rhino2sw/`; `script_windows/` per l'avvio da sorgente.

## 0.1.1 – 2026-11-19
- Installatore accetta Python 3.11–3.14 (la 3.15 non ha ancora la libreria geometrica).

## 0.1 – 2026-11-19
- Prima versione: conversione piani/cilindri/coni, unione facce, controlli di
  validità/volume/scostamento, rapporto txt/csv, avvio con trascinamento su Windows.
- Testato su un pezzo meccanico reale: 258 facce B-spline -> 212 facce (53 piani,
  96 cilindri, 12 coni, 51 B-spline), scostamento 0,000 mm, verificato in SolidWorks 2019.
