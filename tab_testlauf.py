import os
import shutil
import subprocess
import threading

import tkinter as tk
from tkinter import ttk

from constants import ACCENT, BG, BG2, BTN, FG


class TestLaufTabMixin:
    """Tab 'Test-Lauf': Backup einmal direkt ausführen mit Live-Log."""

    def _tab_testlauf(self, nb) -> None:
        tab = self._new_tab(nb, "  Test-Lauf  ")
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(3, weight=1)

        info = ("Generiert die Skripte und startet das Backup einmalig im "
                "Vordergrund (per pkexec/sudo). Es wird KEIN systemd-Timer "
                "installiert — ideal zum Testen der Konfiguration.")
        tk.Label(tab, text=info, bg=BG, fg="#aaa", font=("Sans", 11),
                 justify="left", anchor="w", wraplength=1100
                 ).grid(row=0, column=0, sticky="ew", pady=(0, 12))

        # ── Action-Leiste ──────────────────────────────────────────────
        bar = tk.Frame(tab, bg=BG)
        bar.grid(row=1, column=0, sticky="ew")

        self._tl_run_btn = tk.Button(
            bar, text="Backup jetzt einmal ausführen",
            command=self._tl_run_once,
            bg=ACCENT, fg="#fff", font=("Sans", 12, "bold"),
            relief="flat", padx=18, pady=8, cursor="hand2",
            activebackground="#3a8eef")
        self._tl_run_btn.pack(side="left")

        self._tl_clear_btn = tk.Button(
            bar, text="Log leeren", command=self._tl_clear,
            bg=BTN, fg=FG, font=("Sans", 11),
            relief="flat", padx=14, pady=8, cursor="hand2")
        self._tl_clear_btn.pack(side="left", padx=(10, 0))

        self._tl_status_lbl = tk.Label(
            bar, text="Bereit", bg=BG, fg="#aaa",
            font=("Sans", 12, "bold"), padx=12)
        self._tl_status_lbl.pack(side="left", padx=(16, 0))

        # ── Progressbar ────────────────────────────────────────────────
        style = ttk.Style()
        style.configure("Backup.Horizontal.TProgressbar",
                        troughcolor=BG2, background=ACCENT,
                        bordercolor=BG2, lightcolor=ACCENT, darkcolor=ACCENT)
        self._tl_pb = ttk.Progressbar(
            tab, mode="determinate", maximum=100, value=0,
            style="Backup.Horizontal.TProgressbar")
        self._tl_pb.grid(row=2, column=0, sticky="ew", pady=(12, 8))

        # ── Log-Widget ─────────────────────────────────────────────────
        log_frame = tk.Frame(tab, bg=BG2)
        log_frame.grid(row=3, column=0, sticky="nsew")
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        self._tl_log = tk.Text(
            log_frame, bg=BG2, fg="#ddd", font=("Mono", 10),
            relief="flat", padx=10, pady=8, wrap="word", state="disabled")
        self._tl_log.grid(row=0, column=0, sticky="nsew")
        sb = tk.Scrollbar(log_frame, command=self._tl_log.yview,
                          bg=BG2, troughcolor=BG, width=12)
        sb.grid(row=0, column=1, sticky="ns")
        self._tl_log.config(yscrollcommand=sb.set)

        # Farb-Tags
        self._tl_log.tag_configure("ok",   foreground="#4caf50")
        self._tl_log.tag_configure("err",  foreground="#f44336")
        self._tl_log.tag_configure("warn", foreground="#ff9800")
        self._tl_log.tag_configure("hdr",  foreground=ACCENT,
                                   font=("Mono", 10, "bold"))
        self._tl_log.tag_configure("dim",  foreground="#888")

        self._tl_proc = None  # laufender subprocess.Popen

    # ── Helpers ────────────────────────────────────────────────────────

    def _tl_append(self, text: str, tag: str = "") -> None:
        """Hängt Text ans Log-Widget (thread-safe via after)."""
        def _do(t=text, g=tag):
            self._tl_log.config(state="normal")
            if g:
                self._tl_log.insert("end", t, g)
            else:
                self._tl_log.insert("end", t)
            self._tl_log.see("end")
            self._tl_log.config(state="disabled")
        self.root.after(0, _do)

    def _tl_clear(self) -> None:
        self._tl_log.config(state="normal")
        self._tl_log.delete("1.0", "end")
        self._tl_log.config(state="disabled")
        self._tl_pb.config(value=0)
        self._tl_status_lbl.config(text="Bereit", fg="#aaa")

    def _tl_run_once(self) -> None:
        """Generiert die Skripte und startet das Backup einmalig."""
        # 1. Skripte generieren (Validierung inklusive)
        result = self._do_generate()
        if result is None:
            return
        svc, outdir, _count = result

        # 2. Runner finden — pkexec bevorzugt (grafischer Auth-Prompt)
        pkexec = shutil.which("pkexec")
        sudo   = shutil.which("sudo")
        if not (pkexec or sudo):
            self._zdlg("error", "Fehler",
                "Weder pkexec noch sudo gefunden.\n\n"
                f"Bitte manuell ausführen:\nsudo bash {outdir}/{svc}.sh")
            return

        script = os.path.join(outdir, f"{svc}.sh")

        # 3. Fortschritts-Anzeige vorbereiten
        # Schritte = mkdir + N Quellen + dpkg? + restore-Spiegel + retention + symlink
        total = (1 + len(self._sources)
                 + (1 if self.dpkg_backup.get() else 0)
                 + 1   # restore.sh-Spiegel
                 + 1   # Aufräumen
                 + 1)  # Symlink
        self._tl_pb.config(maximum=total, value=0)
        self._tl_status_lbl.config(text="Läuft …", fg="#ff9800")
        self._tl_run_btn.config(state="disabled")
        self._tl_clear()
        self._tl_append(f"=== Test-Lauf gestartet ===\n", "hdr")
        self._tl_append(f"Skript: {script}\n", "dim")
        self._tl_append(f"Runner: {pkexec or sudo}\n\n", "dim")

        # 4. Subprocess starten
        if pkexec:
            cmd = [pkexec, "env", "NAS_BACKUP_LIVE_LOG=1",
                   "bash", script]
        else:  # sudo
            cmd = [sudo, "-E", "env", "NAS_BACKUP_LIVE_LOG=1",
                   "bash", script]

        env = os.environ.copy()
        env["NAS_BACKUP_LIVE_LOG"] = "1"

        def runner():
            try:
                self._tl_proc = subprocess.Popen(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, bufsize=1, env=env)
                assert self._tl_proc.stdout is not None
                for line in self._tl_proc.stdout:
                    self._tl_handle_line(line)
                rc = self._tl_proc.wait()
                self._tl_proc = None
                self.root.after(0, lambda: self._tl_finish(rc))
            except Exception as e:
                msg = str(e)
                self._tl_proc = None
                self.root.after(0,
                    lambda m=msg: self._tl_handle_error(m))

        threading.Thread(target=runner, daemon=True).start()

    def _tl_handle_line(self, line: str) -> None:
        """Klassifiziert eine Output-Zeile und aktualisiert UI."""
        stripped = line.rstrip("\n")
        if "[OK]" in stripped:
            self._tl_append(line, "ok")
            self.root.after(0, lambda: self._tl_pb.step(1))
        elif "[FEHLER]" in stripped:
            self._tl_append(line, "err")
            self.root.after(0, lambda: self._tl_pb.step(1))
        elif "[WARNUNG]" in stripped:
            self._tl_append(line, "warn")
        elif stripped.startswith("==="):
            self._tl_append(line, "hdr")
        else:
            self._tl_append(line)

    def _tl_finish(self, rc: int) -> None:
        if rc == 0:
            self._tl_status_lbl.config(
                text=f"Erfolgreich (Code 0)", fg="#4caf50")
            self._tl_pb.config(value=self._tl_pb.cget("maximum"))
            self._tl_append(f"\n=== Test-Lauf erfolgreich beendet ===\n", "hdr")
        else:
            self._tl_status_lbl.config(
                text=f"Fehlgeschlagen (Code {rc})", fg="#f44336")
            self._tl_append(
                f"\n=== Test-Lauf mit Code {rc} beendet ===\n", "err")
        self._tl_run_btn.config(state="normal")

    def _tl_handle_error(self, msg: str) -> None:
        self._tl_append(f"\nFEHLER beim Starten: {msg}\n", "err")
        self._tl_status_lbl.config(text="Fehler", fg="#f44336")
        self._tl_run_btn.config(state="normal")
