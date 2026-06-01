#!/usr/bin/env python3
"""
NAS-Backup-Generator
Tkinter-GUI zur Generierung von rsync-Backup-Skripten
mit systemd-Integration für NAS via SSH (ASUSTOR / Synology)
"""

import os
import tkinter as tk
from tkinter import ttk

from constants import ACCENT, BG, BG2, ENTRY, FG
from dialogs import DialogMixin
from widgets import WidgetMixin
from generators import GeneratorMixin
from tab_ziel import ZielTabMixin
from tab_quellen import QuellenTabMixin
from tab_zeitplan import ZeitplanTabMixin
from tab_aufbewahrung import AufbewahrungTabMixin
from tab_testlauf import TestLaufTabMixin
import settings as settings_io


class App(
    ZielTabMixin,
    QuellenTabMixin,
    ZeitplanTabMixin,
    AufbewahrungTabMixin,
    TestLaufTabMixin,
    GeneratorMixin,
    WidgetMixin,
    DialogMixin,
):
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        root.title("NAS-Backup-Generator")
        root.minsize(700, 500)
        root.configure(bg=BG)
        root.resizable(True, True)

        # ── Ziel-Variablen ──────────────────────────────────────────────
        self.nas_host     = tk.StringVar(value="")
        self.nas_user     = tk.StringVar(value="")
        self.nas_ssh_port = tk.StringVar(value="22")
        self.ssh_key      = tk.StringVar(
            value=os.path.expanduser("~/.ssh/id_ed25519"))
        self.nas_base     = tk.StringVar(value="/volume1/backup/Linux")
        self.log_file     = tk.StringVar(value="/var/log/nas-backup.log")
        self.service_name = tk.StringVar(value="nas-backup")
        # "key" | "password" | "key_fallback"
        self.auth_mode    = tk.StringVar(value="key")
        self.nas_password = tk.StringVar(value="")
        self.pass_file    = tk.StringVar(value="/etc/backup/.nas_pass")

        # ── Zeitplan-Variablen ──────────────────────────────────────────
        self.sched_hour      = tk.StringVar(value="03")
        self.sched_min       = tk.StringVar(value="00")
        self.sched_sec       = tk.StringVar(value="00")
        self.sched_freq      = tk.StringVar(value="daily")
        self.sched_wd_single = tk.StringVar(value="Montag")
        self.sched_dom       = tk.StringVar(value="01")
        self.persistent      = tk.BooleanVar(value=True)

        # ── Aufbewahrung-Variablen ──────────────────────────────────────
        self.max_snapshots = tk.IntVar(value=7)
        self.dpkg_backup   = tk.BooleanVar(value=True)
        # Schätzung NAS-Belegung
        self.calc_base_gb     = tk.StringVar(value="200")
        self.calc_change_pct  = tk.StringVar(value="2.0")

        # ── Ausgabe-Pfad ────────────────────────────────────────────────
        self.output_dir = tk.StringVar(
            value=os.path.expanduser("~/nas-backup-scripts"))

        # ── Listen (Quellen / Ausschlüsse) ──────────────────────────────
        # Defaults für ein vollständiges Linux-Backup. Im Quellen-Tab
        # können einzelne Pfade entfernt werden, falls nicht relevant.
        # Hinweis: /var/lib enthält ggf. Datenbanken (Postgres/MySQL) –
        # für konsistente DB-Sicherung VOR dem rsync einen Dump in
        # /var/backups/ schreiben (mysqldump / pg_dumpall).
        self._sources:  list[str] = [
            "/home",        # Benutzer-Daten + Dotfiles
            "/etc",         # System-Konfiguration
            "/root",        # Home-Verzeichnis von root
            "/var/spool",   # Crontabs, Mail-Queue, Druckerwarteschlange
            "/var/lib",     # Service-Daten (DB, Docker-Volumes, libvirt …)
            "/opt",         # manuell installierte Drittsoftware
            "/usr/local",   # selbstkompilierte Programme (make install)
            "/boot",        # Kernel + initramfs + GRUB-Config
        ]
        self._excludes: list[str] = [
            # Virtuelle / temporäre Systemverzeichnisse
            "/dev/*",
            "/proc/*",
            "/sys/*",
            "/tmp/*",
            "/run/*",
            "/mnt/*",
            "/media/*",
            "lost+found",
            # ALLE versteckten Ordner ausschließen (Firefox-Profile, Caches …)
            # Hinweis: Trailing-/ → matched nur Verzeichnisse, nicht .bashrc & Co.
            # ACHTUNG: schließt auch .ssh, .config, .gnupg aus – ggf. anpassen!
            ".*/",
            # /home – Caches & temporäre Daten (redundant zu .*/ aber explizit)
            ".cache",
            ".thumbnails",
            ".local/share/Trash",
            "*.tmp",
            "node_modules",
            "__pycache__",
            ".steam",
            "snap",
            # /etc – nicht ohne Root lesbar
            "credstore",
            "credstore.encrypted",
            "ssl/private",
            "lvm/archive",
            "lvm/backup",
            "polkit-1/rules.d",
            "cups/ssl",
            # /var/lib – riesig & regenerierbar oder besser separat dumpen
            "docker",         # Docker-Layer (separat: docker save / Volumes)
            "containers",     # Podman-Layer
            "snapd",          # Snap-Daten (regenerierbar via snap install)
            "flatpak",        # Flatpak-Apps (regenerierbar)
            "apt/lists",      # apt-Repositorien-Cache
            "dpkg/lock*",     # dpkg-Locks
            # /var/spool – aktive Postfix-Queue (in Bewegung, inkonsistent)
            "postfix/active",
            "postfix/incoming",
            # /boot – ESP ist separates FAT32-Filesystem, FAT mag rsync-Perms nicht
            "/efi",
            # Generelle Caches (greifen u.a. unter /var/lib und /opt)
            "Cache",
            "GPUCache",
        ]

        # Letzte gespeicherte Einstellungen laden (überschreibt Defaults)
        settings_io.apply_to(self, settings_io.load())

        self._build_ui()

        # Beim Fenster-Schließen automatisch speichern
        root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _on_close(self) -> None:
        settings_io.save(self)
        self.root.destroy()

    def _save_settings(self) -> None:
        """Wird vom Generieren/Test-Lauf aufgerufen."""
        settings_io.save(self)

    # ──────────────────────────────────────────────────────────────────────
    # UI-Aufbau
    # ──────────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        tk.Label(self.root, text="NAS-Backup-Generator",
                 font=("Sans", 18, "bold"), bg=BG, fg=ACCENT
                 ).pack(anchor="w", padx=20, pady=(14, 4))

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TNotebook",         background=BG, borderwidth=0)
        style.configure("TNotebook.Tab",     background=BG2, foreground=FG,
                                             padding=[16, 8], font=("Sans", 12),
                                             borderwidth=0)
        style.map("TNotebook.Tab",
                  background=[("selected", ACCENT)],
                  foreground=[("selected", "#fff")],
                  padding=[("selected", [16, 8])],
                  expand=[("selected", [0, 0, 0, 0])])
        style.configure("TSpinbox",  fieldbackground=ENTRY, background=ENTRY,
                                     foreground=FG, arrowcolor=FG)
        style.configure("TCombobox", fieldbackground=ENTRY, background=ENTRY,
                                     foreground=FG, arrowcolor=FG,
                                     selectbackground=ENTRY, selectforeground=FG)
        style.map("TCombobox", fieldbackground=[("readonly", ENTRY)])

        # Untere Leiste zuerst packen → immer sichtbar
        bar = tk.Frame(self.root, bg=BG)
        bar.pack(fill="x", padx=20, pady=10, side="bottom")

        tk.Button(bar, text="Generieren …", command=self._generieren,
                  bg=ACCENT, fg="#fff", font=("Sans", 13, "bold"),
                  relief="flat", padx=20, pady=9,
                  activebackground="#3a8eef", cursor="hand2"
                  ).pack(side="right", padx=(12, 0))

        tk.Label(bar, text="Ausgabe-Pfad:", bg=BG, fg=FG,
                 font=("Sans", 12)).pack(side="left")
        tk.Button(bar, text="⛶", command=self._browse_output_dir,
                  bg=ENTRY, fg=FG, relief="flat", padx=10, pady=4,
                  font=("Sans", 11), cursor="hand2"
                  ).pack(side="right", padx=(6, 0))
        tk.Entry(bar, textvariable=self.output_dir, bg=ENTRY, fg=FG,
                 insertbackground=FG, relief="flat",
                 font=("Mono", 12)).pack(side="left", fill="x",
                                          expand=True, padx=(8, 0))

        nb = ttk.Notebook(self.root)
        nb.pack(fill="both", expand=True, padx=20, pady=4)

        self._tab_ziel(nb)
        self._tab_quellen(nb)
        self._tab_zeitplan(nb)
        self._tab_aufbewahrung(nb)
        self._tab_testlauf(nb)

    def _browse_output_dir(self) -> None:
        from tkinter import filedialog
        start = self.output_dir.get() or os.path.expanduser("~")
        if not os.path.isdir(start):
            start = os.path.expanduser("~")
        path = (self._native_select_dir("Ausgabeverzeichnis wählen", start)
                or filedialog.askdirectory(
                    title="Ausgabeverzeichnis wählen", initialdir=start))
        if path:
            self.output_dir.set(path)


def main() -> None:
    root = tk.Tk()
    # Geometrie ZUERST setzen – verhindert, dass Tk das Fenster vorher
    # auf die natürliche Mindestgröße der Widgets aufbläht.
    w, h = 1260, 960
    sw = root.winfo_screenwidth()
    sh = root.winfo_screenheight()
    x  = (sw - w) // 2
    y  = (sh - h) // 2
    root.geometry(f"{w}x{h}+{x}+{y}")
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
