# rhino2sw

*Cleans up Rhino STEP exports for SolidWorks: rebuilds planar, cylindrical and conical B-spline faces as exact analytic geometry so mates and drawing dimensions work. Documentation in Italian.*

Pulizia dei file STEP esportati da Rhino per l'uso in SolidWorks 2019.

Rhino esporta tutte le facce come B-spline, compresi piani e fori: in SolidWorks
mancano assi e piani veri, quindi niente accoppiamenti concentrici e niente quote
di diametro in tavola. `rhino2sw` riconosce le facce che sono piani, cilindri e coni,
le riscrive come geometria analitica senza spostare la geometria, unisce le facce
spezzate e controlla il risultato. Se un controllo fallisce il file non viene scritto.

## Uso (Windows)
Vedi [`windows/LEGGIMI.txt`](windows/LEGGIMI.txt).
In breve: Python 3.11–3.14 (non 3.15), `1_INSTALLA.bat` una volta, poi trascinare
file o cartelle STEP su `Converti_per_SolidWorks.bat`.

## Uso (riga di comando)
```
pip install -r requirements.txt
python rhino2sw.py file.stp cartella/ ...
```
Uscita in `per_SolidWorks/` accanto agli originali: `*_SW.stp` + rapporto `.txt` e `.csv`.

## Controlli eseguiti su ogni pezzo
| Controllo | Soglia |
|---|---|
| Riconoscimento piano/cilindro/cono | 0,001 mm |
| Solido valido dopo la conversione | obbligatorio |
| Differenza di volume | ≤ 0,001 % |
| Scostamento massimo (punti campionati) | ≤ 0,005 mm |
| Spigoli con gap segnalati | > 0,001 mm |

## Limiti noti
Vedi le issue aperte. Principali: raccordi a toro lasciati B-spline, gap non ricuciti,
assiemi scritti come parte multicorpo.

## Pacchetto da distribuire
Lo zip da distribuire contiene `rhino2sw.py` + il contenuto di `windows/` nella stessa cartella.
I file `.bat` funzionano anche lanciati da `windows/` dentro il repository.

## Dati dei pezzi
Il `.gitignore` esclude tutti i file CAD (`.stp`, `.step`, `.x_t`, `.3dm`): i modelli reali non vanno nel repository.
Per i test usare solo pezzi generati da `tests/crea_pezzi_prova.py`.

## Licenza
MIT, vedi [`LICENSE`](LICENSE).
