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

## 4. Assiemi Rhino (file con più corpi)
Con l'impostazione predefinita un file STEP con più corpi viene diviso:
```
per_SolidWorks\NOMEFILE\
    ASSIEME_NOMEFILE.stp        <- aprire questo in SolidWorks: ricrea l'assieme
    parti\NOME_SW.stp           <- una parte per corpo (i blocchi ripetuti una volta sola)
```
- **Nome delle parti**: nome dell'oggetto in Rhino; se manca (Rhino scrive «brep_1») il nome del blocco;
  poi l'ultimo livello del layer. Nomi uguali ricevono `_2`, `_3`. Si può dare la precedenza al layer.
- **Origine**: gli oggetti sciolti mantengono l'origine di Rhino; le parti che vengono da un blocco hanno
  l'origine nel punto base del blocco. Le posizioni nell'assieme sono quelle di Rhino.
- In alternativa (**Impostazioni → File con più corpi**): un file per ogni istanza in coordinate assolute,
  senza file d'assieme: inseriti tutti all'origine in SolidWorks ricompongono l'assieme.
- Le superfici aperte non vengono esportate (si possono includere dalle impostazioni). Una parte che non si
  riesce a pulire entra nell'assieme come originale e nel rapporto è segnata.
- Nel rapporto c'è una riga per parte, con layer, blocco e numero di istanze.

## 5. Rapporti
La scheda **Rapporti** mostra lo storico di tutte le conversioni: ricerca, filtro per esito, ordinamento
per colonna. *Apri in Excel* apre il CSV.

Il CSV unico si trova, salvo diversa impostazione, in `%LOCALAPPDATA%\rhino2sw\rapporti_rhino2sw.csv`.
Per un unico storico di tutto l'ufficio: **File → Impostazioni → Rapporti** e indicare una cartella di rete
condivisa da tutti. Se il CSV è aperto in Excel o la rete non risponde, le righe vengono tenute da parte e
scritte alla conversione successiva.

I rapporti della versione 0.1 (`rapporto_AAAAMMGG_HHMMSS.csv`) si recuperano con
**Importa rapporti vecchi…**.

## 6. Note nel rapporto
- *facce restano B-spline*: forme libere o raccordi. Su quelle facce niente accoppiamenti né quote di raggio.
- *spigoli con gap*: punti dove le facce non combaciano entro 0,001 mm; se SolidWorks segnala errori, sono lì.
- *superfici aperte*: il pezzo non è chiuso in Rhino; va sistemato prima di esportare.

## 7. Aggiornamenti
All'avvio rhino2sw controlla (al massimo una volta al giorno) se su GitHub c'è una versione nuova. Se c'è,
compare una barra azzurra in alto: *Scarica* apre il download dell'installatore nel browser; chiudere
rhino2sw e lanciare il file scaricato. Rapporti e impostazioni restano.
Si disattiva da **File → Impostazioni → Aggiornamenti**; controllo manuale da **Aiuto → Controlla aggiornamenti**.

## 8. Problemi
Menu **Aiuto → Segnala un problema** apre una issue su GitHub. Non allegare i modelli: copiare la riga del
rapporto (esito, numero di facce, note).
