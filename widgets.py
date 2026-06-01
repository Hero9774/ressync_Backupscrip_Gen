import tkinter as tk
from tkinter import ttk

from constants import ACCENT, BTN, BG, BG2, ENTRY, FG


class WidgetMixin:
    """Wiederverwendbare Tkinter-Widget-Hilfsmethoden."""

    def _new_tab(self, nb: ttk.Notebook, title: str) -> tk.Frame:
        f = tk.Frame(nb, bg=BG, padx=20, pady=16)
        nb.add(f, text=title)
        return f

    def _make_listbox(self, parent: tk.Frame) -> tuple[tk.Listbox, tk.Frame]:
        frame = tk.Frame(parent, bg=BG)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)
        lb = tk.Listbox(frame, bg=ENTRY, fg=FG, selectbackground=ACCENT,
                        relief="flat", font=("Mono", 12), height=5,
                        activestyle="none")
        sb = tk.Scrollbar(frame, orient="vertical", command=lb.yview,
                          bg=BG2, troughcolor=BG2, relief="flat")
        lb.config(yscrollcommand=sb.set)
        lb.grid(row=0, column=0, sticky="nsew")
        sb.grid(row=0, column=1, sticky="ns")
        return lb, frame

    def _list_controls(self, parent: tk.Frame, row: int,
                       var: tk.StringVar, add_cmd, del_cmd) -> None:
        f = tk.Frame(parent, bg=BG)
        f.grid(row=row, column=0, sticky="w", pady=(0, 4))
        tk.Entry(f, textvariable=var, bg=ENTRY, fg=FG,
                 insertbackground=FG, relief="flat",
                 font=("Mono", 12), width=32).grid(row=0, column=0, padx=(0, 8))
        tk.Button(f, text="+ Hinzufügen", bg=BTN, fg=FG, relief="flat",
                  padx=14, pady=6, font=("Sans", 12),
                  command=add_cmd).grid(row=0, column=1, padx=(0, 6))
        tk.Button(f, text="− Entfernen", bg=BTN, fg=FG, relief="flat",
                  padx=14, pady=6, font=("Sans", 12),
                  command=del_cmd).grid(row=0, column=2)

    # ── Pill-Buttons (klar erkennbarer aktiver Zustand) ─────────────────
    #
    # tk.Radiobutton / tk.Checkbutton zeigen im Dark-Theme nur einen
    # winzigen Indikator-Punkt → kaum erkennbar. Stattdessen Labels mit
    # vollflächigem Akzent-Hintergrund für den aktiven Zustand.

    def _pill_radios(self, parent: tk.Frame, var, options: list,
                     orient: str = "horizontal", command=None) -> tk.Frame:
        """Reihe von Pill-Buttons als visuelle Radio-Gruppe.

        options: Liste von (value, label)-Tupeln
        var:     tk.StringVar oder tk.IntVar
        orient:  "horizontal" (nebeneinander) oder "vertical" (übereinander)
        command: optionaler Callback nach jeder Auswahl (kein Argument)
        """
        frame = tk.Frame(parent, bg=BG)
        btns: dict = {}

        # Schrift dauerhaft fett, sonst springt das Layout beim Wechseln
        # zwischen normal/bold (bold ist breiter).
        def _render(val):
            for v, btn in btns.items():
                if v == val:
                    btn.config(bg=ACCENT, fg="#ffffff")
                else:
                    btn.config(bg=BTN, fg=FG)

        def _select(val):
            var.set(val)
            _render(val)
            if command is not None:
                command()

        # Bei vertikaler Anordnung alle Pills gleich breit (längster Label):
        max_w = max(len(str(l)) for _, l in options) + 4 if orient == "vertical" else 0

        for val, label in options:
            btn = tk.Label(frame, text=f"  {label}  ",
                           font=("Sans", 12, "bold"), bg=BTN, fg=FG,
                           padx=8, pady=6, cursor="hand2",
                           anchor="center")
            if orient == "horizontal":
                btn.pack(side="left", padx=(0, 6))
            else:
                btn.config(width=max_w)
                btn.pack(anchor="w", pady=2)
            btns[val] = btn
            btn.bind("<Button-1>", lambda e, v=val: _select(v))

        # Auch auf externe var.set(…) reagieren (idempotent bei eigener Wahl)
        var.trace_add("write", lambda *_: _render(var.get()))
        _render(var.get())  # nur visuelle Initialisierung, command nicht feuern
        return frame

    def _pill_check(self, parent: tk.Frame, var, label: str,
                    hint: str = "") -> tk.Frame:
        """Toggle-Pill für tk.BooleanVar mit optionalem Hint-Text rechts."""
        frame = tk.Frame(parent, bg=BG)
        # ASCII-Präfix [X]/[ ] statt Unicode-Boxen, damit der Text auch
        # in Bold zuverlässig rendert.
        pill = tk.Label(frame, text=f"  [ ]  {label}  ",
                        font=("Sans", 12, "bold"),
                        bg=BTN, fg=FG, padx=10, pady=6, cursor="hand2")
        pill.grid(row=0, column=0, sticky="w")

        def _render():
            if var.get():
                pill.config(text=f"  [X]  {label}  ", bg=ACCENT, fg="#ffffff")
            else:
                pill.config(text=f"  [ ]  {label}  ", bg=BTN, fg=FG)

        def _toggle(_e=None):
            var.set(not var.get())
            _render()

        pill.bind("<Button-1>", _toggle)
        # Auch externe var.set(…) abdecken
        var.trace_add("write", lambda *_: _render())
        _render()

        if hint:
            tk.Label(frame, text=hint, bg=BG, fg="#777",
                     font=("Sans", 11)).grid(row=0, column=1, sticky="w", padx=(8, 0))
        return frame
