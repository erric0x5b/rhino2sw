# Backlog iniziale (da trasformare in issue)

1. **Raccordi a toro**: convertirli in tori veri (oggi restano B-spline perché davano facce non valide). Serve per quotare i raggi in tavola.
2. **Ricucitura gap**: chiudere gli spigoli con gap > 0,001 mm invece di segnalarli soltanto.
3. **Assiemi**: leggere lo STEP con struttura, convertire ogni pezzo una volta, riscrivere l'assieme con nomi e posizioni. Prima verificare cosa esporta davvero Rhino.
4. **Conversione per corpo**: in un file multicorpo, se un corpo fallisce oggi fallisce tutto il file. Scrivere i corpi buoni e segnalare solo quelli falliti.
5. ~~**Eseguibile unico**~~: fatto nella 0.2.0 (installatore + portatile via GitHub Actions).
6. ~~**Raccolta rapporti**~~: fatto nella 0.2.0 (CSV unico, anche su cartella di rete).
7. **Test automatici**: base fatta nella 0.2.0; mancano casi reali anonimizzati (es. pezzi con tori, multicorpo).
8. **Firma del codice**: senza certificato SmartScreen avvisa all'installazione e alcuni antivirus aziendali possono bloccare l'exe.
