import tkinter as tk
from tkinter import ttk

from constants import ACCENT, BG, BG2, FG, _WD_MAP


class ZeitplanTabMixin:
    """Tab 'Zeitplan': Häufigkeit, Wochentag/Tag-im-Monat, Uhrzeit, Persistent."""

    def _tab_zeitplan(self, nb) -> None:
        tab = self._new_tab(nb, "  Zeitplan  ")
        tab.columnconfigure(1, weight=1)

        # Häufigkeit
        tk.Label(tab, text="Häufigkeit:", bg=BG, fg=FG,
                 font=("Sans", 12)).grid(row=0, column=0, sticky="w", pady=6)
        ff = self._pill_radios(
            tab, var=self.sched_freq,
            options=[("daily", "Täglich"),
                     ("weekly", "Wöchentlich"),
                     ("monthly", "Monatlich")],
            command=self._update_freq_fields)
        ff.grid(row=0, column=1, sticky="w", pady=6)

        # Wochentag (nur weekly)
        self._wd_lbl = tk.Label(tab, text="Wochentag:", bg=BG, fg=FG, font=("Sans", 12))
        self._wd_lbl.grid(row=1, column=0, sticky="w", pady=6)
        self._wd_cell = tk.Frame(tab, bg=BG)
        self._wd_cell.grid(row=1, column=1, sticky="w", pady=6)
        ttk.Combobox(self._wd_cell, textvariable=self.sched_wd_single,
                     values=list(_WD_MAP.keys()), width=12, state="readonly"
                     ).pack(side="left")

        # Tag im Monat (nur monthly)
        self._dom_lbl = tk.Label(tab, text="Tag im Monat:", bg=BG, fg=FG, font=("Sans", 12))
        self._dom_lbl.grid(row=2, column=0, sticky="w", pady=6)
        self._dom_cell = tk.Frame(tab, bg=BG)
        self._dom_cell.grid(row=2, column=1, sticky="w", pady=6)
        ttk.Combobox(self._dom_cell, textvariable=self.sched_dom,
                     values=[f"{d:02d}" for d in range(1, 29)],
                     width=5, state="readonly").pack(side="left")
        tk.Label(self._dom_cell, text="  (1–28, jeden Monat)",
                 bg=BG, fg="#777", font=("Sans", 11)).pack(side="left")

        # Uhrzeit HH:MM:SS
        tk.Label(tab, text="Uhrzeit:", bg=BG, fg=FG,
                 font=("Sans", 12)).grid(row=3, column=0, sticky="w", pady=6)
        tf = tk.Frame(tab, bg=BG)
        tf.grid(row=3, column=1, sticky="w", pady=6)
        secs = [f"{s:02d}" for s in range(60)]
        ttk.Combobox(tf, textvariable=self.sched_hour,
                     values=[f"{h:02d}" for h in range(24)],
                     width=4, state="readonly").grid(row=0, column=0)
        tk.Label(tf, text=":", bg=BG, fg=FG, font=("Sans", 12)).grid(row=0, column=1, padx=2)
        ttk.Combobox(tf, textvariable=self.sched_min,
                     values=[f"{m:02d}" for m in range(60)],
                     width=4, state="readonly").grid(row=0, column=2)
        tk.Label(tf, text=":", bg=BG, fg=FG, font=("Sans", 12)).grid(row=0, column=3, padx=2)
        ttk.Combobox(tf, textvariable=self.sched_sec, values=secs,
                     width=4, state="readonly").grid(row=0, column=4)

        # Persistent
        tk.Label(tab, text="Persistent:", bg=BG, fg=FG,
                 font=("Sans", 12)).grid(row=4, column=0, sticky="w", pady=6)
        pf = self._pill_check(
            tab, var=self.persistent,
            label="Verpassten Lauf nachholen",
            hint="(wenn Gerät zur geplanten Zeit aus war)")
        pf.grid(row=4, column=1, sticky="w", pady=6)

        # OnCalendar-Vorschau
        tk.Label(tab, text="Vorschau:", bg=BG, fg=FG,
                 font=("Sans", 12)).grid(row=5, column=0, sticky="w", pady=(18, 6))
        self._cal_lbl = tk.Label(tab, text="", bg=BG2, fg=ACCENT,
                                  font=("Mono", 13), padx=12, pady=8)
        self._cal_lbl.grid(row=5, column=1, sticky="w", pady=(18, 6))

        for v in (self.sched_hour, self.sched_min, self.sched_sec,
                  self.sched_freq, self.sched_wd_single, self.sched_dom):
            v.trace_add("write", lambda *_: self._update_cal_preview())

        self._update_freq_fields()
        self._update_cal_preview()

    def _on_calendar(self) -> str:
        h    = self.sched_hour.get()
        m    = self.sched_min.get()
        s    = self.sched_sec.get()
        freq = self.sched_freq.get()
        time_str = f"{h}:{m}:{s}"
        if freq == "weekly":
            wd = _WD_MAP.get(self.sched_wd_single.get(), "Mon")
            return f"{wd} *-*-* {time_str}"
        if freq == "monthly":
            dom = self.sched_dom.get().zfill(2)
            return f"*-*-{dom} {time_str}"
        return f"*-*-* {time_str}"  # daily

    def _update_cal_preview(self) -> None:
        self._cal_lbl.config(text=f"OnCalendar={self._on_calendar()}")

    def _update_freq_fields(self) -> None:
        freq = self.sched_freq.get()
        if freq == "weekly":
            self._wd_lbl.grid()
            self._wd_cell.grid()
            self._dom_lbl.grid_remove()
            self._dom_cell.grid_remove()
        elif freq == "monthly":
            self._dom_lbl.grid()
            self._dom_cell.grid()
            self._wd_lbl.grid_remove()
            self._wd_cell.grid_remove()
        else:  # daily
            self._wd_lbl.grid_remove()
            self._wd_cell.grid_remove()
            self._dom_lbl.grid_remove()
            self._dom_cell.grid_remove()
        self._update_cal_preview()
