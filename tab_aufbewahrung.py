import tkinter as tk

from constants import ACCENT, BG, BG2, ENTRY, FG


class AufbewahrungTabMixin:
    """Tab 'Aufbewahrung': Anzahl gespeicherter Backups, dpkg-Paketliste."""

    def _tab_aufbewahrung(self, nb) -> None:
        tab = self._new_tab(nb, "  Aufbewahrung  ")
        tab.columnconfigure(1, weight=1)

        # Backups behalten
        tk.Label(tab, text="Backups behalten:", bg=BG, fg=FG,
                 font=("Sans", 12)).grid(row=0, column=0, sticky="nw", pady=6)
        rf = self._pill_radios(
            tab, var=self.max_snapshots,
            options=[(1,  "1   –  Spiegel (keine Historie)"),
                     (2,  "2   –  aktuellstes + Vorgänger"),
                     (7,  "7   –  eine Woche Historie"),
                     (30, "30  –  ein Monat Historie")],
            orient="vertical")
        rf.grid(row=0, column=1, sticky="w", pady=6)

        # dpkg-Paketliste
        tk.Label(tab, text="Paketliste sichern:", bg=BG, fg=FG,
                 font=("Sans", 12)).grid(row=1, column=0, sticky="w", pady=6)
        pf = self._pill_check(
            tab, var=self.dpkg_backup,
            label="dpkg-Paketliste",
            hint="dpkg --get-selections → packages.txt  (Debian/Ubuntu)")
        pf.grid(row=1, column=1, sticky="w", pady=6)

        # ── Speicher-Schätzung ─────────────────────────────────────────
        est = tk.LabelFrame(tab, text="  Schätzung NAS-Belegung  ",
                            bg=BG, fg=ACCENT, font=("Sans", 12, "bold"),
                            padx=14, pady=10, bd=1, relief="groove",
                            labelanchor="nw")
        est.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(20, 0))
        est.columnconfigure(3, weight=1)

        tk.Label(est, text="Aktuelle Snapshot-Größe:", bg=BG, fg=FG,
                 font=("Sans", 11)).grid(row=0, column=0, sticky="w",
                                          padx=(0, 8), pady=4)
        tk.Entry(est, textvariable=self.calc_base_gb, width=8,
                 bg=ENTRY, fg=FG, relief="flat", font=("Mono", 11),
                 insertbackground=FG, justify="right"
                 ).grid(row=0, column=1, sticky="w", pady=4)
        tk.Label(est, text="GB", bg=BG, fg="#888",
                 font=("Sans", 11)).grid(row=0, column=2, sticky="w",
                                          padx=(4, 24), pady=4)

        tk.Label(est, text="Tägliche Änderungsrate:", bg=BG, fg=FG,
                 font=("Sans", 11)).grid(row=1, column=0, sticky="w",
                                          padx=(0, 8), pady=4)
        tk.Entry(est, textvariable=self.calc_change_pct, width=8,
                 bg=ENTRY, fg=FG, relief="flat", font=("Mono", 11),
                 insertbackground=FG, justify="right"
                 ).grid(row=1, column=1, sticky="w", pady=4)
        tk.Label(est, text="%", bg=BG, fg="#888",
                 font=("Sans", 11)).grid(row=1, column=2, sticky="w",
                                          padx=(4, 24), pady=4)

        self._calc_result_lbl = tk.Label(
            est, text="", bg=BG, fg="#4caf50",
            font=("Sans", 13, "bold"), anchor="w", justify="left")
        self._calc_result_lbl.grid(row=2, column=0, columnspan=4,
                                    sticky="w", pady=(12, 2))

        self._calc_detail_lbl = tk.Label(
            est, text="", bg=BG, fg="#888",
            font=("Mono", 10), anchor="w", justify="left")
        self._calc_detail_lbl.grid(row=3, column=0, columnspan=4,
                                    sticky="w", pady=(0, 2))

        # Live-Update bei jeder Eingabeänderung
        for v in (self.calc_base_gb, self.calc_change_pct, self.max_snapshots):
            v.trace_add("write", lambda *_: self._update_size_estimate())
        self._update_size_estimate()

        # Info-Box
        info = tk.Text(tab, bg=BG2, fg="#888", font=("Mono", 11),
                       height=6, width=1,
                       relief="flat", padx=12, pady=8, state="normal", wrap="word")
        info.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(20, 0))
        info.insert("end",
            "Aufbewahrungslogik im generierten Backup-Skript:\n\n"
            "  • Nach jedem Backup werden alle datierten Verzeichnisse "
            "(YYYY-MM-DD) auf dem NAS via SSH gezählt.\n"
            "  • Übersteigt die Anzahl das Maximum, werden die ältesten "
            "Snapshots gelöscht.\n"
            "  • Hardlinks (--link-dest) sorgen dafür, dass unveränderte "
            "Dateien zwischen Snapshots nur EIN MAL physisch existieren.")
        info.config(state="disabled")

    def _update_size_estimate(self) -> None:
        """Berechnet die geschätzte NAS-Belegung anhand der Eingaben."""
        try:
            base = float(self.calc_base_gb.get())
            pct  = float(self.calc_change_pct.get())
            n    = int(self.max_snapshots.get())
        except (ValueError, tk.TclError):
            self._calc_result_lbl.config(text="—  ungültige Eingabe")
            self._calc_detail_lbl.config(text="")
            return
        if base <= 0 or pct < 0 or n < 1:
            self._calc_result_lbl.config(text="—")
            self._calc_detail_lbl.config(text="")
            return

        # Bei N Snapshots gibt es N-1 inkrementelle Änderungs-Sätze
        # (jeweils pct% des Bases als zusätzlicher Platz).
        change_per_snap = base * pct / 100.0
        extra = change_per_snap * (n - 1)
        total = base + extra

        self._calc_result_lbl.config(
            text=f"➜  Geschätzte Gesamtbelegung: {total:.1f} GB")
        self._calc_detail_lbl.config(
            text=(
                f"   Basis {base:.0f} GB  +  ({n}-1) × {change_per_snap:.1f} GB Änderung  "
                f"=  {total:.1f} GB\n"
                f"   bei {n} Snapshots und {pct:g}% Tagesänderung"
            ))
