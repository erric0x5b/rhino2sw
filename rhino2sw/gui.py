"""Interfaccia grafica (PySide6)."""
import json
import os
import subprocess
import sys
import tempfile
import time

from PySide6.QtCore import Qt, QProcess, QThread, QTimer, QSortFilterProxyModel, QUrl, Signal
from PySide6.QtGui import (QAction, QBrush, QColor, QDesktopServices, QIcon, QStandardItem,
                           QStandardItemModel, QKeySequence)
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFrame,
                               QFileDialog, QFormLayout, QGroupBox, QHBoxLayout, QHeaderView, QLabel,
                               QLineEdit, QMainWindow, QMessageBox, QProgressBar, QPushButton,
                               QRadioButton, QSpinBox, QStyle, QTableView, QTabWidget, QVBoxLayout,
                               QWidget)

from . import REPO_URL, __version__, report, settings, updater

ESTENSIONI = (".stp", ".step")
CARTELLA_USCITA = "per_SolidWorks"

COLORI = {"OK": "#d9f2dd", "PARZIALE": "#fff1c7", "NON CONVERTITO": "#fff1c7", "SUPERFICI": "#eeeeee",
          "ERRORE": "#f8d4d4"}


def _raccogli(percorsi):
    out = []
    for a in percorsi:
        if os.path.isdir(a):
            for root, dirs, files in os.walk(a):
                dirs[:] = [d for d in dirs if d != CARTELLA_USCITA]
                out += [os.path.join(root, f) for f in files if f.lower().endswith(ESTENSIONI)]
        elif a.lower().endswith(ESTENSIONI) and os.path.isfile(a):
            out.append(a)
    return [os.path.normpath(p) for p in out]


def comando_worker():
    """Eseguibile + argomenti per lanciare il motore in un processo separato."""
    if getattr(sys, "frozen", False):
        return sys.executable, []
    return sys.executable, ["-m", "rhino2sw"]


def mostra_in_esplora(path):
    if not path:
        return
    if sys.platform.startswith("win"):
        if os.path.isfile(path):
            subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])
        else:
            os.startfile(path)  # noqa
    else:
        QDesktopServices.openUrl(QUrl.fromLocalFile(path if os.path.isdir(path) else os.path.dirname(path)))


def apri_file(path):
    QDesktopServices.openUrl(QUrl.fromLocalFile(path))


# ---------------------------------------------------------------------------------------------
class TabellaFile(QTableView):
    """Tabella che accetta file e cartelle trascinati."""

    def __init__(self, on_drop, parent=None):
        super().__init__(parent)
        self.on_drop = on_drop
        self.setAcceptDrops(True)
        self.setDragDropMode(QAbstractItemView.DropOnly)
        self.vuoto = QLabel("Trascina qui file STEP (.stp, .step) o cartelle\n\noppure usa \"Aggiungi file\"",
                            self.viewport())
        self.vuoto.setAlignment(Qt.AlignCenter)
        self.vuoto.setStyleSheet("color: #888; font-size: 14px;")

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self.vuoto.resize(self.viewport().size())

    def aggiorna_vuoto(self):
        m = self.model()
        self.vuoto.setVisible(m is None or m.rowCount() == 0)

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    dragMoveEvent = dragEnterEvent

    def dropEvent(self, e):
        self.on_drop([u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile()])
        e.acceptProposedAction()


# ---------------------------------------------------------------------------------------------
class PaginaConversione(QWidget):
    COLONNE = ["File", "Cartella", "Stato", "Convertite", "B-spline rimaste", "Scostamento max (mm)", "Note"]

    def __init__(self, finestra):
        super().__init__()
        self.finestra = finestra
        self.voci = []            # dict: path, stato, risultato
        self.in_corso = {}        # QProcess -> (indice, json_path, timer)
        self.coda = []
        self.fermato = False
        self.risultati_lotto = []

        self.modello = QStandardItemModel(0, len(self.COLONNE))
        self.modello.setHorizontalHeaderLabels(self.COLONNE)
        self.tabella = TabellaFile(self.aggiungi_percorsi)
        self.tabella.setModel(self.modello)
        self.tabella.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tabella.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tabella.verticalHeader().setVisible(False)
        h = self.tabella.horizontalHeader()
        h.setSectionResizeMode(QHeaderView.Interactive)
        h.setStretchLastSection(True)
        for i, w in enumerate([220, 260, 130, 80, 110, 140]):
            self.tabella.setColumnWidth(i, w)
        self.tabella.doubleClicked.connect(self._doppio_clic)

        st = self.style()
        self.b_file = QPushButton(st.standardIcon(QStyle.SP_FileIcon), "Aggiungi file…")
        self.b_cartella = QPushButton(st.standardIcon(QStyle.SP_DirIcon), "Aggiungi cartella…")
        self.b_rimuovi = QPushButton("Rimuovi selezionati")
        self.b_svuota = QPushButton("Svuota elenco")
        self.b_converti = QPushButton(st.standardIcon(QStyle.SP_MediaPlay), "Converti")
        self.b_converti.setDefault(True)
        self.b_converti.setStyleSheet("font-weight: bold; padding: 6px 18px;")
        self.b_ferma = QPushButton(st.standardIcon(QStyle.SP_MediaStop), "Ferma")
        self.b_ferma.setEnabled(False)
        self.b_file.clicked.connect(self._scegli_file)
        self.b_cartella.clicked.connect(self._scegli_cartella)
        self.b_rimuovi.clicked.connect(self._rimuovi)
        self.b_svuota.clicked.connect(self._svuota)
        self.b_converti.clicked.connect(self.avvia)
        self.b_ferma.clicked.connect(self.ferma)

        barra = QHBoxLayout()
        for b in (self.b_file, self.b_cartella, self.b_rimuovi, self.b_svuota):
            barra.addWidget(b)
        barra.addStretch(1)
        barra.addWidget(self.b_ferma)
        barra.addWidget(self.b_converti)

        self.avanzamento = QProgressBar()
        self.avanzamento.setTextVisible(True)
        self.avanzamento.setFormat("%v / %m")
        self.avanzamento.setVisible(False)
        self.etichetta_uscita = QLabel()
        self.etichetta_uscita.setTextInteractionFlags(Qt.TextBrowserInteraction)
        self.etichetta_uscita.linkActivated.connect(lambda _: self.finestra.impostazioni())
        self.aggiorna_etichetta_uscita()

        lay = QVBoxLayout(self)
        lay.addLayout(barra)
        lay.addWidget(self.tabella, 1)
        lay.addWidget(self.avanzamento)
        lay.addWidget(self.etichetta_uscita)
        self.tabella.aggiorna_vuoto()

    # -- elenco ----------------------------------------------------------------------------
    def aggiorna_etichetta_uscita(self):
        s = settings.carica()
        dove = s["cartella_uscita_fissa"] or f"accanto agli originali, nella cartella «{CARTELLA_USCITA}»"
        if s["dividi_assiemi"]:
            ass = ("una parte per corpo + file d'assieme" if s["modo_parti"] == "assieme"
                   else "un file per istanza in coordinate assolute")
            ass = f" — file con più corpi: {ass}, nomi da {'oggetto' if s['nome_parti'] == 'oggetto' else 'layer'}"
        else:
            ass = " — file con più corpi: parte multicorpo"
        self.etichetta_uscita.setText(f"File convertiti: {dove}{ass} &nbsp; <a href='#'>cambia…</a>")

    def aggiungi_percorsi(self, percorsi):
        presenti = {v["path"] for v in self.voci}
        nuovi = [p for p in _raccogli(percorsi) if p not in presenti]
        for p in nuovi:
            self.voci.append({"path": p, "stato": "In attesa", "r": None})
            self.modello.appendRow([QStandardItem(x) for x in
                                    (os.path.basename(p), os.path.dirname(p), "In attesa", "", "", "", "")])
        self.tabella.aggiorna_vuoto()
        if percorsi and not nuovi:
            self.finestra.statusBar().showMessage("Nessun nuovo file STEP trovato", 4000)
        elif nuovi:
            self.finestra.statusBar().showMessage(f"Aggiunti {len(nuovi)} file", 4000)

    def _scegli_file(self):
        f, _ = QFileDialog.getOpenFileNames(self, "Scegli i file STEP esportati da Rhino", "",
                                            "STEP (*.stp *.step *.STP *.STEP);;Tutti i file (*.*)")
        self.aggiungi_percorsi(f)

    def _scegli_cartella(self):
        d = QFileDialog.getExistingDirectory(self, "Scegli una cartella (vengono incluse le sottocartelle)")
        if d:
            self.aggiungi_percorsi([d])

    def _rimuovi(self):
        if self.in_corso:
            return
        righe = sorted({i.row() for i in self.tabella.selectionModel().selectedRows()}, reverse=True)
        for r in righe:
            self.modello.removeRow(r)
            del self.voci[r]
        self.tabella.aggiorna_vuoto()

    def _svuota(self):
        if self.in_corso:
            return
        self.modello.removeRows(0, self.modello.rowCount())
        self.voci.clear()
        self.tabella.aggiorna_vuoto()

    def _doppio_clic(self, idx):
        v = self.voci[idx.row()]
        r = v["r"] or {}
        mostra_in_esplora(r.get("file_uscita") or v["path"])

    def _aggiorna_riga(self, i):
        v = self.voci[i]
        r = v["r"] or {}
        stato = v["stato"]
        if r:
            stato = r.get("esito", stato)
        valori = [os.path.basename(v["path"]), os.path.dirname(v["path"]), stato,
                  str(r.get("convertite", "")), str(r.get("bspline_rimaste", "")),
                  "" if not isinstance(r.get("scost_max_mm"), (int, float)) else f"{r['scost_max_mm']:.5f}".replace(".", ","),
                  r.get("note", "")]
        colore = COLORI.get(stato)
        for c, testo in enumerate(valori):
            it = self.modello.item(i, c)
            it.setText(testo)
            it.setToolTip(testo)
            it.setBackground(QBrush(QColor(colore)) if colore else QBrush())

    # -- conversione ---------------------------------------------------------------------------
    def _imposta_occupato(self, occupato):
        for b in (self.b_file, self.b_cartella, self.b_rimuovi, self.b_svuota, self.b_converti):
            b.setEnabled(not occupato)
        self.b_ferma.setEnabled(occupato)
        self.finestra.azione_impostazioni.setEnabled(not occupato)

    def avvia(self):
        da_fare = [i for i, v in enumerate(self.voci) if v["r"] is None or v["r"].get("esito") == "ERRORE"]
        if not da_fare:
            if not self.voci:
                QMessageBox.information(self, "rhino2sw", "Aggiungi prima dei file STEP da convertire.")
            else:
                self.finestra.statusBar().showMessage("Tutti i file in elenco sono già stati convertiti", 4000)
            return
        self.s = settings.carica()
        self.tmp = tempfile.mkdtemp(prefix="rhino2sw_gui_")
        self.coda = list(da_fare)
        self.fermato = False
        self.risultati_lotto = []
        for i in da_fare:
            self.voci[i]["r"] = None
            self.voci[i]["stato"] = "In coda"
            self._aggiorna_riga(i)
        self.avanzamento.setRange(0, len(da_fare))
        self.avanzamento.setValue(0)
        self.avanzamento.setVisible(True)
        self._imposta_occupato(True)
        self._riempi()

    def _riempi(self):
        while self.coda and len(self.in_corso) < self.s["processi_paralleli"] and not self.fermato:
            i = self.coda.pop(0)
            jp = os.path.join(self.tmp, f"r{i}.json")
            exe, pre = comando_worker()
            args = pre + ["--worker", self.voci[i]["path"], jp]
            if self.s["cartella_uscita_fissa"]:
                args += ["--uscita", self.s["cartella_uscita_fissa"]]
            if self.s["dividi_assiemi"]:
                args += ["--dividi", "--modo", self.s["modo_parti"], "--nomi", self.s["nome_parti"]]
                if self.s["includi_superfici"]:
                    args.append("--superfici")
            pr = QProcess(self)
            pr.setProcessChannelMode(QProcess.MergedChannels)
            pr.finished.connect(lambda code, status, pr=pr: self._finito(pr, code, status))
            pr.errorOccurred.connect(lambda err, pr=pr: self._errore_avvio(pr, err))
            timer = QTimer(self)
            timer.setSingleShot(True)
            timer.timeout.connect(lambda pr=pr: self._scaduto(pr))
            timer.start(self.s["timeout_minuti"] * 60 * 1000)
            self.in_corso[pr] = [i, jp, timer, None]
            self.voci[i]["stato"] = "In conversione…"
            self._aggiorna_riga(i)
            pr.start(exe, args)
        if not self.in_corso:
            self._fine_lotto()

    def _errore_avvio(self, pr, err):
        if err == QProcess.FailedToStart and pr in self.in_corso:
            self.in_corso[pr][3] = "impossibile avviare il motore di conversione"
            self._finito(pr, -1, QProcess.CrashExit)

    def _scaduto(self, pr):
        if pr in self.in_corso:
            self.in_corso[pr][3] = f"tempo scaduto ({self.s['timeout_minuti']} min)"
            pr.kill()

    def _finito(self, pr, code, status):
        if pr not in self.in_corso:
            return
        i, jp, timer, motivo = self.in_corso.pop(pr)
        timer.stop()
        path = self.voci[i]["path"]
        r = None
        try:
            with open(jp, encoding="utf-8") as fh:
                r = json.load(fh)
        except (OSError, ValueError):
            pass
        if r is None:
            if self.fermato and motivo is None:
                motivo = "interrotto dall'utente"
            out = bytes(pr.readAll()).decode("utf-8", "replace").strip().splitlines()
            dettaglio = f" ({out[-1][:200]})" if out else ""
            r = {"file": os.path.basename(path), "percorso": path, "esito": "ERRORE",
                 "note": (motivo or f"il motore di conversione si è chiuso in modo anomalo, codice {code}") + dettaglio}
        self.voci[i]["r"] = r
        self._aggiorna_riga(i)
        self.risultati_lotto.append(r)
        self.avanzamento.setValue(self.avanzamento.value() + 1)
        pr.deleteLater()
        QTimer.singleShot(0, self._riempi)

    def ferma(self):
        self.fermato = True
        for i in self.coda:
            self.voci[i]["stato"] = "In attesa"
            self._aggiorna_riga(i)
        self.coda.clear()
        for pr in list(self.in_corso):
            pr.kill()

    def _fine_lotto(self):
        self._imposta_occupato(False)
        if not self.risultati_lotto:
            self.avanzamento.setVisible(False)
            return
        reali = [r for r in self.risultati_lotto if r.get("note") != "interrotto dall'utente"]
        msg = ""
        if reali:
            try:
                dest, attesa = report.aggiungi(reali, self.s)
                if attesa:
                    msg = (" — ATTENZIONE: il CSV dei rapporti non era raggiungibile (aperto in Excel o rete assente); "
                           "le righe verranno aggiunte alla prossima conversione")
            except OSError as ex:
                msg = f" — impossibile scrivere il rapporto: {ex}"
        ok = sum(r.get("esito") == "OK" for r in self.risultati_lotto)
        pz = sum(r.get("esito") == "PARZIALE" for r in self.risultati_lotto)
        nc = sum(r.get("esito") == "NON CONVERTITO" for r in self.risultati_lotto)
        er = len(self.risultati_lotto) - ok - nc - pz
        extra = f", {pz} assiemi parziali" if pz else ""
        self.finestra.statusBar().showMessage(f"Fatto: {ok} OK{extra}, {nc} non convertiti, {er} errori{msg}")
        self.finestra.pagina_rapporti.ricarica()
        self.avanzamento.setVisible(False)
        auto = os.environ.get("RHINO2SW_AUTOTEST")
        if auto:   # usato dai test automatici: salva i risultati ed esce
            with open(auto, "w", encoding="utf-8") as fh:
                json.dump(self.risultati_lotto, fh, ensure_ascii=False, default=str)
            QApplication.instance().quit()


# ---------------------------------------------------------------------------------------------
class FiltroRapporti(QSortFilterProxyModel):
    def __init__(self):
        super().__init__()
        self.testo = ""
        self.esito = ""

    def filterAcceptsRow(self, riga, parent):
        m = self.sourceModel()
        if self.esito and m.item(riga, 2).text() != self.esito:
            return False
        if self.testo:
            t = self.testo.lower()
            return any(t in (m.item(riga, c).text() or "").lower() for c in range(m.columnCount()))
        return True


class PaginaRapporti(QWidget):
    VISTE = [("data_ora", "Data"), ("file", "File"), ("esito", "Esito"), ("convertite", "Convertite"),
             ("bspline_rimaste", "B-spline rimaste"), ("scost_max_mm", "Scostamento (mm)"),
             ("spigoli_gap", "Spigoli con gap"), ("gap_max_mm", "Gap max (mm)"), ("tipi_dopo", "Facce dopo"),
             ("note", "Note"), ("layer", "Layer"), ("blocco", "Blocco"), ("istanze", "Istanze"), ("utente", "Utente"), ("pc", "PC"), ("versione", "Versione"),
             ("percorso", "Originale"), ("file_uscita", "Convertito")]

    def __init__(self, finestra):
        super().__init__()
        self.finestra = finestra
        self.modello = QStandardItemModel(0, len(self.VISTE))
        self.modello.setHorizontalHeaderLabels([v[1] for v in self.VISTE])
        self.filtro = FiltroRapporti()
        self.filtro.setSourceModel(self.modello)
        self.filtro.setSortRole(Qt.UserRole)

        self.cerca = QLineEdit()
        self.cerca.setPlaceholderText("Cerca per nome file, note, utente…")
        self.cerca.setClearButtonEnabled(True)
        self.cerca.textChanged.connect(self._filtra)
        self.combo = QComboBox()
        self.combo.addItems(["Tutti gli esiti", "OK", "NON CONVERTITO", "SUPERFICI", "ERRORE"])
        self.combo.currentIndexChanged.connect(self._filtra)
        b_agg = QPushButton("Aggiorna")
        b_agg.clicked.connect(self.ricarica)
        b_excel = QPushButton("Apri in Excel")
        b_excel.clicked.connect(self._apri_excel)
        b_imp = QPushButton("Importa rapporti vecchi…")
        b_imp.setToolTip("Importa i file rapporto_AAAAMMGG_HHMMSS.csv creati dalla versione 0.1")
        b_imp.clicked.connect(self._importa)

        barra = QHBoxLayout()
        barra.addWidget(self.cerca, 1)
        barra.addWidget(self.combo)
        barra.addWidget(b_agg)
        barra.addWidget(b_imp)
        barra.addWidget(b_excel)

        self.tabella = QTableView()
        self.tabella.setModel(self.filtro)
        self.tabella.setSortingEnabled(True)
        self.tabella.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tabella.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tabella.verticalHeader().setVisible(False)
        self.tabella.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        for i, w in enumerate([140, 200, 120, 80, 110, 110, 100, 90, 240, 380]):
            self.tabella.setColumnWidth(i, w)
        self.tabella.doubleClicked.connect(self._doppio_clic)
        self.tabella.setToolTip("Doppio clic: apre la cartella del file convertito")

        self.riepilogo = QLabel()
        self.percorso = QLabel()
        self.percorso.setStyleSheet("color: #666;")
        self.percorso.setTextInteractionFlags(Qt.TextSelectableByMouse)

        lay = QVBoxLayout(self)
        lay.addLayout(barra)
        lay.addWidget(self.tabella, 1)
        lay.addWidget(self.riepilogo)
        lay.addWidget(self.percorso)
        self.ricarica()

    @staticmethod
    def _chiave(campo, testo):
        if campo in report.NUMERICI or campo in ("convertite", "bspline_rimaste", "spigoli_gap"):
            try:
                return float(testo.replace(",", "."))
            except ValueError:
                return -1e18
        return testo.lower()

    def ricarica(self):
        try:
            righe = report.leggi()
        except OSError as ex:
            righe = []
            self.finestra.statusBar().showMessage(f"Impossibile leggere i rapporti: {ex}")
        self.tabella.setSortingEnabled(False)
        self.modello.removeRows(0, self.modello.rowCount())
        for r in reversed(righe):   # piu' recenti in alto
            items = []
            for campo, _ in self.VISTE:
                t = r.get(campo) or ""
                it = QStandardItem(t)
                it.setToolTip(t)
                it.setData(self._chiave(campo, t), Qt.UserRole)
                col = COLORI.get(r.get("esito"))
                if col:
                    it.setBackground(QBrush(QColor(col)))
                items.append(it)
            self.modello.appendRow(items)
        self.tabella.setSortingEnabled(True)
        self.tabella.sortByColumn(0, Qt.DescendingOrder)
        self._filtra()
        attesa = report.righe_in_attesa()
        extra = f" — {attesa} righe in attesa di essere scritte (CSV non raggiungibile)" if attesa else ""
        self.percorso.setText(f"File rapporti: {report.percorso_csv()}{extra}")

    def _filtra(self):
        self.filtro.testo = self.cerca.text().strip()
        self.filtro.esito = "" if self.combo.currentIndex() == 0 else self.combo.currentText()
        self.filtro.invalidate()
        tot = self.filtro.rowCount()
        cont = {"OK": 0, "NON CONVERTITO": 0, "ERRORE": 0, "SUPERFICI": 0}
        for i in range(tot):
            e = self.filtro.index(i, 2).data()
            cont[e] = cont.get(e, 0) + 1
        self.riepilogo.setText(f"<b>{tot}</b> conversioni mostrate: {cont['OK']} OK, "
                               f"{cont['NON CONVERTITO']} non convertite, {cont['ERRORE']} errori")

    def _doppio_clic(self, idx):
        src = self.filtro.mapToSource(idx)
        uscita = self.modello.item(src.row(), len(self.VISTE) - 1).text()
        orig = self.modello.item(src.row(), len(self.VISTE) - 2).text()
        p = uscita if uscita and os.path.exists(uscita) else orig
        if p and os.path.exists(p):
            mostra_in_esplora(p)
        else:
            self.finestra.statusBar().showMessage("Il file non esiste più in quella posizione", 4000)

    def _apri_excel(self):
        p = report.percorso_csv()
        if os.path.exists(p):
            apri_file(p)
        else:
            QMessageBox.information(self, "rhino2sw", "Non ci sono ancora rapporti.")

    def _importa(self):
        f, _ = QFileDialog.getOpenFileNames(self, "Rapporti della versione 0.1", "", "CSV (*.csv)")
        if not f:
            return
        try:
            n = report.importa_vecchi(f)
        except (OSError, ValueError) as ex:
            QMessageBox.warning(self, "rhino2sw", f"Importazione non riuscita: {ex}")
            return
        self.ricarica()
        self.finestra.statusBar().showMessage(f"Importate {n} righe", 5000)


# ---------------------------------------------------------------------------------------------
class DialogoImpostazioni(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle("Impostazioni")
        self.setMinimumWidth(560)
        self.s = settings.carica()

        # uscita
        g1 = QGroupBox("Dove salvare i file convertiti")
        self.r_accanto = QRadioButton(f"Accanto agli originali, nella cartella «{CARTELLA_USCITA}»")
        self.r_fissa = QRadioButton("In una cartella fissa:")
        self.e_fissa = QLineEdit(self.s["cartella_uscita_fissa"])
        b_fissa = QPushButton("Sfoglia…")
        b_fissa.clicked.connect(lambda: self._sfoglia(self.e_fissa))
        (self.r_fissa if self.s["cartella_uscita_fissa"] else self.r_accanto).setChecked(True)
        self.r_fissa.toggled.connect(lambda on: (self.e_fissa.setEnabled(on), b_fissa.setEnabled(on)))
        self.e_fissa.setEnabled(self.r_fissa.isChecked())
        b_fissa.setEnabled(self.r_fissa.isChecked())
        l1 = QVBoxLayout(g1)
        l1.addWidget(self.r_accanto)
        riga = QHBoxLayout()
        riga.addWidget(self.r_fissa)
        riga.addWidget(self.e_fissa, 1)
        riga.addWidget(b_fissa)
        l1.addLayout(riga)

        # rapporti
        g2 = QGroupBox("Rapporti")
        self.e_rapp = QLineEdit(self.s["cartella_rapporti"])
        self.e_rapp.setPlaceholderText(f"predefinita: {settings.cartella_dati()}")
        b_rapp = QPushButton("Sfoglia…")
        b_rapp.clicked.connect(lambda: self._sfoglia(self.e_rapp))
        b_pred = QPushButton("Predefinita")
        b_pred.clicked.connect(lambda: self.e_rapp.setText(""))
        l2 = QVBoxLayout(g2)
        nota = QLabel("Per avere un unico storico per tutto l'ufficio indica una cartella di rete condivisa. "
                      "Se la cartella non è raggiungibile le righe vengono tenute da parte e scritte dopo.")
        nota.setWordWrap(True)
        nota.setStyleSheet("color: #666;")
        riga2 = QHBoxLayout()
        riga2.addWidget(self.e_rapp, 1)
        riga2.addWidget(b_rapp)
        riga2.addWidget(b_pred)
        l2.addLayout(riga2)
        l2.addWidget(nota)

        # prestazioni
        g3 = QGroupBox("Prestazioni")
        f3 = QFormLayout(g3)
        self.sp_proc = QSpinBox()
        self.sp_proc.setRange(1, 8)
        self.sp_proc.setValue(self.s["processi_paralleli"])
        self.sp_time = QSpinBox()
        self.sp_time.setRange(1, 240)
        self.sp_time.setSuffix(" min")
        self.sp_time.setValue(self.s["timeout_minuti"])
        f3.addRow("File convertiti in parallelo:", self.sp_proc)
        f3.addRow("Tempo massimo per file:", self.sp_time)

        g5 = QGroupBox("File con più corpi (assiemi Rhino)")
        l5 = QVBoxLayout(g5)
        self.cb_dividi = QCheckBox("Dividi in file di parti (un file per corpo; i blocchi ripetuti diventano una parte sola)")
        self.cb_dividi.setChecked(bool(self.s["dividi_assiemi"]))
        self.r_assieme = QRadioButton("Parti + file d'assieme che le rimette nelle posizioni di Rhino "
                                      "(i blocchi hanno origine nel punto base)")
        self.r_assolute = QRadioButton("Un file per ogni istanza in coordinate assolute di Rhino "
                                       "(inseriti all'origine si ricompone l'assieme)")
        (self.r_assolute if self.s["modo_parti"] == "assolute" else self.r_assieme).setChecked(True)
        self.co_nomi = QComboBox()
        self.co_nomi.addItems(["Nome oggetto (poi blocco, poi layer)", "Layer (poi nome oggetto, poi blocco)"])
        self.co_nomi.setCurrentIndex(1 if self.s["nome_parti"] == "layer" else 0)
        self.cb_sup = QCheckBox("Esporta anche le superfici aperte (non solidi)")
        self.cb_sup.setChecked(bool(self.s["includi_superfici"]))
        riga5 = QHBoxLayout()
        riga5.addWidget(QLabel("Nome dei file:"))
        riga5.addWidget(self.co_nomi, 1)
        for w in (self.cb_dividi, self.r_assieme, self.r_assolute):
            l5.addWidget(w)
        l5.addLayout(riga5)
        l5.addWidget(self.cb_sup)

        def _abilita(on):
            for w in (self.r_assieme, self.r_assolute, self.co_nomi, self.cb_sup):
                w.setEnabled(on)
        self.cb_dividi.toggled.connect(_abilita)
        _abilita(self.cb_dividi.isChecked())

        g4 = QGroupBox("Aggiornamenti")
        l4 = QVBoxLayout(g4)
        self.cb_agg = QCheckBox("Controlla all'avvio se c'è una versione nuova (una volta al giorno)")
        self.cb_agg.setChecked(bool(self.s["controlla_aggiornamenti"]))
        l4.addWidget(self.cb_agg)

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self._ok)
        bb.rejected.connect(self.reject)
        lay = QVBoxLayout(self)
        for w in (g1, g5, g2, g3, g4):
            lay.addWidget(w)
        lay.addWidget(bb)

    def _sfoglia(self, campo):
        d = QFileDialog.getExistingDirectory(self, "Scegli cartella", campo.text())
        if d:
            campo.setText(os.path.normpath(d))

    def _ok(self):
        fissa = self.e_fissa.text().strip() if self.r_fissa.isChecked() else ""
        if self.r_fissa.isChecked() and not fissa:
            QMessageBox.warning(self, "Impostazioni", "Indica la cartella fissa oppure scegli «accanto agli originali».")
            return
        rapp = self.e_rapp.text().strip()
        for d in filter(None, (fissa, rapp)):
            try:
                os.makedirs(d, exist_ok=True)
            except OSError as ex:
                QMessageBox.warning(self, "Impostazioni", f"Cartella non utilizzabile:\n{d}\n\n{ex}")
                return
        self.s.update(cartella_uscita_fissa=fissa, cartella_rapporti=rapp,
                      processi_paralleli=self.sp_proc.value(), timeout_minuti=self.sp_time.value(),
                      controlla_aggiornamenti=self.cb_agg.isChecked(),
                      dividi_assiemi=self.cb_dividi.isChecked(),
                      modo_parti="assolute" if self.r_assolute.isChecked() else "assieme",
                      nome_parti="layer" if self.co_nomi.currentIndex() == 1 else "oggetto",
                      includi_superfici=self.cb_sup.isChecked())
        settings.salva(self.s)
        self.accept()


# ---------------------------------------------------------------------------------------------
class ControlloAggiornamenti(QThread):
    """Esegue updater.controlla fuori dal thread della finestra."""
    finito = Signal(str, object)

    def __init__(self, s, manuale, parent=None):
        super().__init__(parent)
        self.s, self.manuale = s, manuale

    def run(self):
        esito, info = updater.controlla(self.s, manuale=self.manuale)
        self.finito.emit(esito, info)


class BarraAggiornamento(QFrame):
    def __init__(self, finestra):
        super().__init__()
        self.finestra = finestra
        self.info = None
        self.setStyleSheet("QFrame { background: #e3eefc; border: 1px solid #9bbbe8; border-radius: 4px; }"
                           "QLabel { border: none; }")
        self.testo = QLabel()
        b_novita = QPushButton("Novità")
        b_scarica = QPushButton("Scarica")
        b_scarica.setStyleSheet("font-weight: bold;")
        b_salta = QPushButton("Salta questa versione")
        b_chiudi = QPushButton("✕")
        b_chiudi.setFixedWidth(28)
        b_chiudi.setToolTip("Ricordamelo più tardi")
        b_novita.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(self.info["pagina"])))
        b_scarica.clicked.connect(self._scarica)
        b_salta.clicked.connect(self._salta)
        b_chiudi.clicked.connect(self.hide)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 4, 4, 4)
        lay.addWidget(self.testo, 1)
        for b in (b_novita, b_scarica, b_salta, b_chiudi):
            lay.addWidget(b)
        self.hide()

    def mostra(self, info):
        self.info = info
        self.testo.setText(f"È disponibile <b>rhino2sw {info['versione']}</b> (questa è la {__version__}).")
        self.show()

    def _scarica(self):
        # il download lo fa il browser: l'utente vede cosa scarica e l'antivirus lo controlla come sempre
        QDesktopServices.openUrl(QUrl(self.info.get("setup_url") or self.info["pagina"]))
        self.finestra.statusBar().showMessage(
            "Scaricamento avviato nel browser: chiudi rhino2sw e lancia l'installatore scaricato", 10000)

    def _salta(self):
        s = settings.carica()
        s["versione_saltata"] = self.info["versione"]
        settings.salva(s)
        self.hide()


# ---------------------------------------------------------------------------------------------
class Finestra(QMainWindow):
    def __init__(self, file_iniziali):
        super().__init__()
        self.setWindowTitle(f"rhino2sw {__version__} — STEP da Rhino per SolidWorks")
        self.resize(1200, 700)
        self.setAcceptDrops(True)

        self.azione_impostazioni = QAction("Impostazioni…", self)
        self.azione_impostazioni.setShortcut(QKeySequence("Ctrl+,"))
        self.azione_impostazioni.triggered.connect(self.impostazioni)
        menu = self.menuBar()
        m_file = menu.addMenu("&File")
        a_agg = m_file.addAction("Aggiungi file…")
        a_agg.setShortcut(QKeySequence.Open)
        m_file.addAction(self.azione_impostazioni)
        m_file.addSeparator()
        a_esci = m_file.addAction("Esci")
        a_esci.triggered.connect(self.close)
        m_help = menu.addMenu("&Aiuto")
        m_help.addAction("Pagina del progetto (GitHub)").triggered.connect(
            lambda: QDesktopServices.openUrl(QUrl(REPO_URL)))
        m_help.addAction("Segnala un problema").triggered.connect(
            lambda: QDesktopServices.openUrl(QUrl(REPO_URL + "/issues/new")))
        m_help.addAction("Controlla aggiornamenti").triggered.connect(lambda: self.controlla_aggiornamenti(True))
        m_help.addSeparator()
        m_help.addAction("Informazioni").triggered.connect(self._info)

        self.tab = QTabWidget()
        self.pagina_rapporti = PaginaRapporti(self)
        self.pagina_conversione = PaginaConversione(self)
        a_agg.triggered.connect(self.pagina_conversione._scegli_file)
        self.tab.addTab(self.pagina_conversione, "Conversione")
        self.tab.addTab(self.pagina_rapporti, "Rapporti")
        self.barra_agg = BarraAggiornamento(self)
        centro = QWidget()
        lc = QVBoxLayout(centro)
        lc.setContentsMargins(6, 6, 6, 0)
        lc.addWidget(self.barra_agg)
        lc.addWidget(self.tab, 1)
        self.setCentralWidget(centro)
        self.statusBar()
        self._thread_agg = None
        if not os.environ.get("RHINO2SW_AUTOTEST") and updater.da_controllare(settings.carica()):
            QTimer.singleShot(1500, lambda: self.controlla_aggiornamenti(False))
        if file_iniziali:
            self.pagina_conversione.aggiungi_percorsi(file_iniziali)

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        if not self.pagina_conversione.in_corso:
            self.tab.setCurrentIndex(0)
            self.pagina_conversione.aggiungi_percorsi([u.toLocalFile() for u in e.mimeData().urls()])

    def impostazioni(self):
        if self.pagina_conversione.in_corso:
            return
        if DialogoImpostazioni(self).exec():
            self.pagina_conversione.aggiorna_etichetta_uscita()
            self.pagina_rapporti.ricarica()

    def controlla_aggiornamenti(self, manuale):
        if self._thread_agg is not None and self._thread_agg.isRunning():
            return
        if manuale:
            self.statusBar().showMessage("Controllo aggiornamenti…")
        self._thread_agg = ControlloAggiornamenti(settings.carica(), manuale, self)
        self._thread_agg.finito.connect(lambda e, i: self._esito_aggiornamenti(e, i, manuale))
        self._thread_agg.start()

    def _esito_aggiornamenti(self, esito, info, manuale):
        if esito != "errore":
            s = settings.carica()
            s["ultimo_controllo"] = int(time.time())
            settings.salva(s)
        if esito == "nuova":
            self.barra_agg.mostra(info)
            if manuale:
                self.statusBar().clearMessage()
        elif manuale:
            self.statusBar().clearMessage()
            if esito == "errore":
                QMessageBox.warning(self, "Aggiornamenti",
                                    f"Impossibile controllare gli aggiornamenti:\n{info}\n\n"
                                    f"Le versioni sono comunque su {REPO_URL}/releases")
            else:
                QMessageBox.information(self, "Aggiornamenti", f"rhino2sw {__version__} è aggiornato.")

    def _info(self):
        QMessageBox.about(self, "rhino2sw",
                          f"<b>rhino2sw {__version__}</b><br>Pulizia dei file STEP di Rhino per SolidWorks.<br><br>"
                          f"Riconosce le facce piane, cilindriche e coniche e le riscrive come geometria esatta, "
                          f"senza spostarla. Se un controllo fallisce il file non viene scritto.<br><br>"
                          f"<a href='{REPO_URL}'>{REPO_URL}</a><br>Licenza MIT. "
                          f"Motore geometrico: Open CASCADE Technology (LGPL).")

    def closeEvent(self, e):
        if self.pagina_conversione.in_corso:
            if QMessageBox.question(self, "rhino2sw", "Conversione in corso. Interromperla e uscire?") \
                    != QMessageBox.Yes:
                e.ignore()
                return
            self.pagina_conversione.ferma()
        if self._thread_agg is not None and self._thread_agg.isRunning():
            self._thread_agg.wait(6000)
        e.accept()


def _icona():
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    for p in (os.path.join(base, "rhino2sw.ico"), os.path.join(base, "assets", "rhino2sw.ico"),
              os.path.join(os.path.dirname(base), "assets", "rhino2sw.ico")):
        if os.path.exists(p):
            return QIcon(p)
    return QIcon()


def avvia(argv):
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("rhino2sw")
    app.setStyle("Fusion")
    app.setWindowIcon(_icona())
    w = Finestra([a for a in argv if not a.startswith("--")])
    w.show()
    if os.environ.get("RHINO2SW_AUTOTEST"):
        QTimer.singleShot(200, w.pagina_conversione.avvia)
        QTimer.singleShot(20 * 60 * 1000, app.quit)
    return app.exec()
