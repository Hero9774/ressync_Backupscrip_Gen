import tkinter as tk

from constants import BG, FG


class QuellenTabMixin:
    """Tab 'Quellen + Filter': Quellverzeichnisse und Ausschluss-Muster."""

    def _tab_quellen(self, nb) -> None:
        tab = self._new_tab(nb, "  Quellen + Filter  ")
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(1, weight=1)
        tab.rowconfigure(4, weight=1)

        tk.Label(tab, text="Quell-Verzeichnisse:", bg=BG, fg=FG,
                 font=("Sans", 12, "bold")).grid(row=0, column=0, sticky="w")

        self._src_lb, src_frame = self._make_listbox(tab)
        src_frame.grid(row=1, column=0, sticky="nsew", pady=(4, 6))
        for d in self._sources:
            self._src_lb.insert("end", d)

        self._new_src = tk.StringVar(value="/home")
        self._list_controls(tab, row=2,
                            var=self._new_src,
                            add_cmd=self._add_source,
                            del_cmd=lambda: self._remove_item(
                                self._src_lb, self._sources))

        tk.Label(tab, text="Ausschluss-Muster (--exclude):", bg=BG, fg=FG,
                 font=("Sans", 12, "bold")).grid(row=3, column=0,
                                                  sticky="w", pady=(10, 0))

        self._exc_lb, exc_frame = self._make_listbox(tab)
        exc_frame.grid(row=4, column=0, sticky="nsew", pady=(4, 6))
        for e in self._excludes:
            self._exc_lb.insert("end", e)

        self._new_exc = tk.StringVar(value="*.tmp")
        self._list_controls(tab, row=5,
                            var=self._new_exc,
                            add_cmd=self._add_exclude,
                            del_cmd=lambda: self._remove_item(
                                self._exc_lb, self._excludes))

    def _add_source(self) -> None:
        val = self._new_src.get().strip()
        if val and val not in self._sources:
            self._sources.append(val)
            self._src_lb.insert("end", val)

    def _add_exclude(self) -> None:
        val = self._new_exc.get().strip()
        if val and val not in self._excludes:
            self._excludes.append(val)
            self._exc_lb.insert("end", val)

    def _remove_item(self, lb: tk.Listbox, lst: list) -> None:
        """Löscht alle ausgewählten Listbox-Einträge und synchronisiert lst.

        Robust gegen Mehrfachauswahl und potenzielle Listbox-Sortierung:
        wir bauen lst nach dem Löschen aus dem Listbox-Inhalt neu auf,
        statt per Index in beide Strukturen zu greifen.
        """
        sel = lb.curselection()
        if not sel:
            return
        # Von hinten löschen, damit verbleibende Indizes stabil bleiben
        for idx in reversed(sel):
            lb.delete(idx)
        lst[:] = list(lb.get(0, "end"))
