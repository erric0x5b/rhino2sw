# Guida d'uso di rhino2sw

## 1. Installazione
1. Scaricare `rhino2sw-X.Y.Z-setup.exe` da [Releases](https://github.com/erric0x5b/rhino2sw/releases).
2. Lanciarlo. Se Windows mostra «Windows ha protetto il PC»: *Ulteriori informazioni* → *Esegui comunque*.
3. Scegliere se creare l'icona sul desktop e se aggiungere rhino2sw al menu **Invia a**.

Non servono Python né diritti di amministratore.

## 2. Esportare da Rhino
File → Esporta selezione → **STEP (*.stp)**, schema **AP214**. Un pezzo per file è il modo più semplice
per montare poi l'assieme in SolidWorks.

## 3. Convertire
Tre modi, tutti equivalenti:
- aprire rhino2sw e **trascinare** file o cartelle nella finestra (le sottocartelle sono incluse);
- **Aggiungi file…** / **Aggiungi cartella…**;
- in Esplora risorse: tasto destro sui file → **Invia a → rhino2sw** (se scelto durante l'installazione).

Poi **Converti**. Le righe si colorano:

| Colore | Esito | Cosa fare |
|---|---|---|
| verde | **OK** | aprire in SolidWorks il file `NOME_SW.stp` |
| giallo | **NON CONVERTITO** | un controllo è fallito: usare l'originale, leggere le note |
| rosso | **ERRORE** | file illeggibile, tempo scaduto o crash del motore: segnalare |

Doppio clic su una riga apre la cartella del file convertito.
Per default i file convertiti vanno nella cartella `per_SolidWorks` accanto agli originali; gli originali
non vengono mai modificati.

## 4. Rapporti
La scheda **Rapporti** mostra lo storico di tutte le conversioni: ricerca, filtro per esito, ordinamento
per colonna. *Apri in Excel* apre il CSV.

Il CSV unico si trova, salvo diversa impostazione, in `%LOCALAPPDATA%\rhino2sw\rapporti_rhino2sw.csv`.
Per un unico storico di tutto l'ufficio: **File → Impostazioni → Rapporti** e indicare una cartella di rete
condivisa da tutti. Se il CSV è aperto in Excel o la rete non risponde, le righe vengono tenute da parte e
scritte alla conversione successiva.

I rapporti della versione 0.1 (`rapporto_AAAAMMGG_HHMMSS.csv`) si recuperano con
**Importa rapporti vecchi…**.

## 5. Note nel rapporto
- *facce restano B-spline*: forme libere o raccordi. Su quelle facce niente accoppiamenti né quote di raggio.
- *spigoli con gap*: punti dove le facce non combaciano entro 0,001 mm; se SolidWorks segnala errori, sono lì.
- *superfici aperte*: il pezzo non è chiuso in Rhino; va sistemato prima di esportare.

## 6. Problemi
Menu **Aiuto → Segnala un problema** apre una issue su GitHub. Non allegare i modelli: copiare la riga del
rapporto (esito, numero di facce, note).
