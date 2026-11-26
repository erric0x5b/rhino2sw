# Changelog

## 0.3.0 – non ancora pubblicata
- **Divisione degli assiemi Rhino in parti**: un file STEP con più corpi diventa una cartella con un file
  per parte (nome dall'oggetto Rhino, poi dal blocco, poi dal layer; impostabile "prima il layer") e un
  `ASSIEME_<nome>.stp` che rimette le parti nelle posizioni di Rhino. I blocchi ripetuti diventano una parte
  sola usata più volte. In alternativa: un file per istanza in coordinate assolute. Le superfici aperte non
  vengono esportate (opzione per includerle). Se una parte non si pulisce, nell'assieme va l'originale.
- **Cilindri e coni completi (360°)**: la cucitura della nuova superficie viene allineata a quella esistente
  e le curve di cucitura ricostruite; prima queste facce si annullavano e il pezzo veniva rifiutato.
- Le superfici nuove sono sempre con assi destrorsi; se la normale è opposta si gira la faccia
  (prima si invertiva la superficie e lo STEP scritto poteva rileggersi con facce rovesciate).
- **Verifica per rilettura**: ogni pezzo convertito viene scritto, riletto e confrontato con la rilettura
  dell'originale; le facce che si rileggono male restano B-spline e si riprova (fino a 3 volte).
- L'unione delle facce spezzate viene saltata se rende il solido non valido (prima poteva gonfiare le
  tolleranze di millimetri); nuovo controllo sulle tolleranze degli spigoli.
- Controllo volume proporzionale all'area (area × 0,001 mm) e area totale entro 0,01 %: i limiti fissi
  rifiutavano pezzi piccoli con molte facce già corretti. Facce sotto 0,01 mm² non vengono convertite.
- **Controllo aggiornamenti**: all'avvio (al massimo una volta al giorno, in background) rhino2sw chiede a
  GitHub qual è l'ultima release; se è più recente compare una barra con *Novità*, *Scarica* e
  *Salta questa versione*. Il download avviene nel browser. Se rete o proxy bloccano la richiesta non
  compare nessun errore. Disattivabile nelle impostazioni; controllo manuale da Aiuto → Controlla aggiornamenti.
- Le release pubblicano anche `SHA256SUMS.txt` (base per l'installazione con un clic).

## 0.2.1 – 2026-11-26
- **File di Rhino già difettosi**: se l'originale ha facce non valide, il pezzo viene convertito purché
  la conversione non aggiunga difetti; il rapporto lo segnala. Prima veniva rifiutato.
- **Scostamento verificato faccia per faccia** durante la conversione (punti interni e lungo i bordi):
  una faccia che non rispetta 0,005 mm resta B-spline invece di far fallire tutto il file.
- Nuovo controllo sull'**area totale** (`diff_area_%`), oltre al volume.
- Pezzi con molte superfici libere (filettature): eliminato il controllo che esauriva la memoria;
  sul caso segnalato da ~276 s a ~50 s.
- CSV dei rapporti: le colonne nuove vengono aggiunte al file esistente senza perdere lo storico.

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
