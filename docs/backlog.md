# Backlog iniziale (da trasformare in issue)

1. **Raccordi a toro**: convertirli in tori veri (oggi restano B-spline perché davano facce non valide). Serve per quotare i raggi in tavola.
2. **Ricucitura gap**: chiudere gli spigoli con gap > 0,001 mm invece di segnalarli soltanto.
3. **Assiemi**: leggere lo STEP con struttura, convertire ogni pezzo una volta, riscrivere l'assieme con nomi e posizioni. Prima verificare cosa esporta davvero Rhino.
4. **Conversione per corpo**: in un file multicorpo, se un corpo fallisce oggi fallisce tutto il file. Scrivere i corpi buoni e segnalare solo quelli falliti.
5. **Eseguibile unico**: build .exe con PyInstaller tramite GitHub Actions, per eliminare l'installazione di Python.
6. **Raccolta rapporti**: cartella condivisa dei CSV per misurare quanti pezzi passano e perché falliscono.
7. **Test automatici**: pezzi di prova (blocco con foro e raccordi, guscio aperto, file corrotto) + casi reali anonimizzati.
