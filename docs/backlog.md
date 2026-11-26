# Backlog iniziale (da trasformare in issue)

1. **Raccordi a toro**: convertirli in tori veri (oggi restano B-spline perché davano facce non valide). Serve per quotare i raggi in tavola. Con il controllo per faccia della 0.2.1 si può riprovare: sul pezzo di riferimento sono 13 facce.
2. **Ricucitura gap**: chiudere gli spigoli con gap > 0,001 mm invece di segnalarli soltanto.
3. **Assiemi**: leggere lo STEP con struttura, convertire ogni pezzo una volta, riscrivere l'assieme con nomi e posizioni. Prima verificare cosa esporta davvero Rhino.
4. **Conversione per corpo**: in un file multicorpo, se un corpo fallisce oggi fallisce tutto il file. Scrivere i corpi buoni e segnalare solo quelli falliti.
5. ~~**Eseguibile unico**~~: fatto nella 0.2.0 (installatore + portatile via GitHub Actions).
6. ~~**Raccolta rapporti**~~: fatto nella 0.2.0 (CSV unico, anche su cartella di rete).
7. **Test automatici**: base fatta nella 0.2.0; mancano casi reali anonimizzati (es. pezzi con tori, multicorpo).
8. **Firma del codice**: senza certificato SmartScreen avvisa all'installazione e alcuni antivirus aziendali possono bloccare l'exe.
9. **Facce quasi piane**: piccole facce piane entro 0,01–0,05 mm ma non entro 0,001 mm (sul pezzo di riferimento 13 facce, circa 6 mm² in tutto). Valutare una tolleranza più larga solo per facce molto piccole.
10. **Filettature**: le eliche restano B-spline (non sono geometria analitica). Idea: opzione per sostituire la filettatura modellata con un cilindro al diametro nominale, così in SolidWorks si usa la filettatura cosmetica.
