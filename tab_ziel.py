import os
import re
import subprocess
import threading

import tkinter as tk
from tkinter import filedialog

from constants import ACCENT, BTN, BG, BG2, ENTRY, FG


class ZielTabMixin:
    """Tab 'Ziel': NAS-Verbindung, SSH-Authentifizierung, Verbindungstest."""

    def _tab_ziel(self, nb) -> None:
        tab = self._new_tab(nb, "  Ziel  ")
        tab.columnconfigure(1, weight=1)

        base_rows = [
            ("NAS-Host:",           self.nas_host),
            ("NAS-Benutzer:",       self.nas_user),
            ("SSH-Port:",           self.nas_ssh_port),
            ("Pfad im rsync-Modul:", self.nas_base),
            ("Log-Datei:",          self.log_file),
            ("Service-Name:",       self.service_name),
        ]
        for i, (lbl, var) in enumerate(base_rows):
            tk.Label(tab, text=lbl, bg=BG, fg=FG, font=("Sans", 12),
                     anchor="w").grid(row=i, column=0, sticky="w",
                                      padx=(0, 10), pady=4)
            cell = tk.Frame(tab, bg=BG)
            cell.grid(row=i, column=1, sticky="ew", pady=4)
            cell.columnconfigure(0, weight=1)
            tk.Entry(cell, textvariable=var, bg=ENTRY, fg=FG,
                     insertbackground=FG, relief="flat",
                     font=("Mono", 12)).grid(row=0, column=0, sticky="ew")
            if lbl == "Pfad im rsync-Modul:":
                tk.Button(cell, text="⛶", command=self._browse_nas_base,
                          bg=BTN, fg=FG, relief="flat", padx=8, pady=2,
                          cursor="hand2", font=("Sans", 11)
                          ).grid(row=0, column=1, padx=(4, 0))
                tk.Button(cell, text="Pfad prüfen", command=self._test_nas_path,
                          bg=BTN, fg=FG, relief="flat", padx=14, pady=2,
                          cursor="hand2", font=("Sans", 11)
                          ).grid(row=0, column=2, padx=(4, 0))
                tk.Label(cell,
                         text="Absoluter Pfad auf dem NAS  —  z. B.  /volume1/backup/Linux"
                              "  (wird via SSH als  user@host:/pfad/…  angesprochen)",
                         bg=BG, fg="#777", font=("Sans", 10)
                         ).grid(row=1, column=0, columnspan=3, sticky="w", pady=(2, 0))
                self._path_status_lbl = tk.Label(cell, text="",
                                                  bg=BG, fg=FG,
                                                  font=("Sans", 11, "bold"),
                                                  anchor="w", padx=10, pady=4)
                self._path_status_lbl.grid(row=2, column=0, columnspan=3,
                                            sticky="w", pady=(4, 0))

        r = len(base_rows)

        # Authentifizierung
        tk.Label(tab, text="Authentifizierung:", bg=BG, fg=FG,
                 font=("Sans", 12), anchor="w").grid(
                 row=r, column=0, sticky="nw", padx=(0, 10), pady=(10, 4))

        auth_frame = tk.Frame(tab, bg=BG)
        auth_frame.grid(row=r, column=1, sticky="w", pady=(10, 4))
        self._auth_btns: dict[str, tk.Label] = {}
        for val, lbl in [
            ("key",          "  SSH-Key  "),
            ("password",     "  Passwort  "),
            ("key_fallback", "  SSH-Key + Passwort-Fallback  "),
        ]:
            btn = tk.Label(auth_frame, text=lbl, font=("Sans", 12),
                           bg=BTN, fg=FG, pady=6, cursor="hand2",
                           width=34, anchor="center")
            btn.pack(anchor="w", pady=2)
            self._auth_btns[val] = btn
            btn.bind("<Button-1>", lambda e, v=val: self._select_auth(v))

        # SSH-Key-Zeile
        self._key_lbl = tk.Label(tab, text="SSH-Key (NAS):", bg=BG, fg=FG,
                                  font=("Sans", 12), anchor="w")
        self._key_lbl.grid(row=r + 1, column=0, sticky="w", padx=(0, 10), pady=4)
        self._key_cell = tk.Frame(tab, bg=BG)
        self._key_cell.grid(row=r + 1, column=1, sticky="ew", pady=4)
        self._key_cell.columnconfigure(0, weight=1)
        tk.Entry(self._key_cell, textvariable=self.ssh_key, bg=ENTRY, fg=FG,
                 insertbackground=FG, relief="flat",
                 font=("Mono", 12)).grid(row=0, column=0, sticky="ew")
        btn_bar = tk.Frame(self._key_cell, bg=BG)
        btn_bar.grid(row=1, column=0, columnspan=2, sticky="w", pady=(4, 0))
        tk.Button(btn_bar, text="SSH-Key importieren", bg=BTN, fg=FG,
                  relief="flat", padx=14, pady=6, font=("Sans", 12),
                  command=self._import_ssh_key).grid(row=0, column=0)
        tk.Button(btn_bar, text="?  Einrichtung", bg=BTN, fg=ACCENT,
                  relief="flat", padx=14, pady=6, font=("Sans", 12),
                  command=self._show_ssh_help).grid(row=0, column=1, padx=(8, 0))

        # Passwort-Zeile
        self._pw_lbl = tk.Label(tab, text="Passwort:", bg=BG, fg=FG,
                                 font=("Sans", 12), anchor="w")
        self._pw_lbl.grid(row=r + 2, column=0, sticky="w", padx=(0, 10), pady=4)
        self._pw_cell = tk.Frame(tab, bg=BG)
        self._pw_cell.grid(row=r + 2, column=1, sticky="ew", pady=4)
        self._pw_cell.columnconfigure(0, weight=1)
        self._pw_entry = tk.Entry(self._pw_cell, textvariable=self.nas_password,
                                   show="•", bg=ENTRY, fg=FG,
                                   insertbackground=FG, relief="flat",
                                   font=("Mono", 12))
        self._pw_entry.grid(row=0, column=0, sticky="ew")
        self._pw_show = tk.BooleanVar(value=False)
        tk.Checkbutton(self._pw_cell, text="Anzeigen", variable=self._pw_show,
                       bg=BG, fg="#777", selectcolor=ACCENT, activebackground=BG,
                       font=("Sans", 11),
                       command=lambda: self._pw_entry.config(
                           show="" if self._pw_show.get() else "•")
                       ).grid(row=0, column=1, padx=(8, 0))

        # Passwort-Datei-Zeile
        self._pf_lbl = tk.Label(tab, text="Passwort-Datei:", bg=BG, fg=FG,
                                 font=("Sans", 12), anchor="w")
        self._pf_lbl.grid(row=r + 3, column=0, sticky="w", padx=(0, 10), pady=4)
        self._pf_cell = tk.Frame(tab, bg=BG)
        self._pf_cell.grid(row=r + 3, column=1, sticky="ew", pady=4)
        self._pf_cell.columnconfigure(0, weight=1)
        tk.Entry(self._pf_cell, textvariable=self.pass_file, bg=ENTRY, fg=FG,
                 insertbackground=FG, relief="flat",
                 font=("Mono", 12)).grid(row=0, column=0, sticky="ew")
        tk.Label(self._pf_cell,
                 text="  (chmod 600, nur root lesbar – wird von install.sh angelegt)",
                 bg=BG, fg="#666", font=("Sans", 11)
                 ).grid(row=0, column=1, sticky="w")

        self._select_auth("key")

        info = ("rsync-Flags:  -aAXz --delete  (Archiv, ACLs, xattr, komprimiert)\n"
                "Passwort-Modus benötigt sshpass  →  sudo apt install sshpass")
        tk.Label(tab, text=info, bg=BG2, fg="#888",
                 font=("Mono", 11), justify="left", padx=10, pady=8
                 ).grid(row=r + 4, column=0, columnspan=2, sticky="ew", pady=(12, 0))

        tk.Button(tab, text="Verbindung testen", command=self._test_connection,
                  bg=BTN, fg=FG, relief="flat", padx=14, pady=6,
                  font=("Sans", 12), cursor="hand2"
                  ).grid(row=r + 5, column=0, columnspan=2,
                         sticky="w", pady=(10, 2))

        self._conn_status = tk.Label(tab, text="",
                                     bg=BG, fg=FG,
                                     font=("Sans", 12, "bold"), anchor="w",
                                     padx=10, pady=5)
        self._conn_status.grid(row=r + 6, column=0, columnspan=2,
                               sticky="w", pady=(6, 2))

        detail_frame = tk.Frame(tab, bg=BG2)
        detail_frame.grid(row=r + 7, column=0, columnspan=2,
                          sticky="ew", pady=(0, 4))
        detail_frame.columnconfigure(0, weight=1)
        self._conn_detail = tk.Text(
            detail_frame, height=4, width=1, bg=BG2, fg="#aaa",
            font=("Mono", 11), relief="flat", state="disabled",
            padx=10, pady=6, wrap="word", insertbackground=FG)
        self._conn_detail.grid(row=0, column=0, sticky="ew")
        sb = tk.Scrollbar(detail_frame, command=self._conn_detail.yview,
                          bg=BG2, troughcolor=BG, width=10)
        sb.grid(row=0, column=1, sticky="ns")
        self._conn_detail.configure(yscrollcommand=sb.set)

        self._update_auth_fields()

    def _test_connection(self) -> None:
        host = self.nas_host.get().strip()
        user = self.nas_user.get().strip()
        port = self.nas_ssh_port.get().strip() or "22"
        key  = self.ssh_key.get().strip()
        mode = self.auth_mode.get()
        pw   = self.nas_password.get()

        if not host or not user:
            self._zdlg("error", "Fehler", "NAS-Host und Benutzer sind erforderlich.")
            return

        self._conn_status.config(text="Verbinde …", fg="#aaa")
        self._conn_detail.config(state="normal")
        self._conn_detail.delete("1.0", "end")
        self._conn_detail.config(state="disabled")
        self.root.update()

        def run() -> None:
            if mode in ("key", "key_fallback"):
                key_path = os.path.expanduser(key)
                if not os.path.isfile(key_path):
                    def _show_no_key(k=key):
                        self._conn_status.config(
                            text=f"FEHLER  –  Key-Datei nicht gefunden: {k}",
                            fg="#f44336")
                        self._conn_detail.config(state="normal")
                        self._conn_detail.delete("1.0", "end")
                        self._conn_detail.insert("end",
                            f"Key-Datei nicht gefunden: {k}\n\n"
                            "ASUSTOR ADM → Dienste → Terminal → SSH-Schlüssel\n"
                            f"→ Download → speichern als: {k}\n"
                            f"Dann: chmod 600 \"{k}\"")
                        self._conn_detail.config(state="disabled")
                        self.root.update()
                    self.root.after(0, _show_no_key)
                    return

            env = os.environ.copy()
            env.pop("SSH_ASKPASS", None)
            env.pop("SSH_ASKPASS_REQUIRE", None)
            env["SSH_ASKPASS_REQUIRE"] = "never"

            cmd = ["ssh", "-p", port,
                   "-o", "ConnectTimeout=8",
                   "-o", "StrictHostKeyChecking=accept-new"]

            # Passwort-Check zentral – betrifft password UND key_fallback
            if mode in ("password", "key_fallback") and not pw:
                def _show_no_pw():
                    self._conn_status.config(
                        text="FEHLER  –  Kein Passwort eingegeben", fg="#f44336")
                    self._conn_detail.config(state="normal")
                    self._conn_detail.delete("1.0", "end")
                    self._conn_detail.insert("end", "Passwort-Feld ist leer.")
                    self._conn_detail.config(state="disabled")
                    self.root.update()
                self.root.after(0, _show_no_pw)
                return

            if mode == "key":
                cmd += ["-o", "BatchMode=yes",
                        "-i", key_path,
                        "-o", "PreferredAuthentications=publickey",
                        "-o", "IdentitiesOnly=yes"]
            elif mode == "password":
                cmd += ["-o", "PreferredAuthentications=password"]
                env["SSHPASS"] = pw
                cmd = ["sshpass", "-e"] + cmd
            else:  # key_fallback
                cmd += ["-i", key_path,
                        "-o", "PreferredAuthentications=publickey,password",
                        "-o", "IdentitiesOnly=yes"]
                env["SSHPASS"] = pw
                cmd = ["sshpass", "-e"] + cmd

            cmd += [f"{user}@{host}", "echo", "OK"]

            def set_detail(text: str) -> None:
                self._conn_detail.config(state="normal")
                self._conn_detail.delete("1.0", "end")
                self._conn_detail.insert("end", text)
                self._conn_detail.config(state="disabled")

            try:
                result = subprocess.run(cmd, capture_output=True, text=True,
                                        timeout=12, env=env)
                ok     = result.returncode == 0
                stdout = result.stdout.strip()
                stderr = result.stderr.strip()
                detail = "\n".join(filter(None, [
                    f"Befehl: {' '.join(cmd)}",
                    f"Exit-Code: {result.returncode}",
                    f"stdout: {stdout}" if stdout else "",
                    f"stderr: {stderr}" if stderr else "",
                ]))
                if ok:
                    def _show_ok(d=detail):
                        self._conn_status.config(
                            text="OK  –  Verbindung erfolgreich",
                            fg="#4caf50")
                        set_detail(d)
                        self.root.update()
                    self.root.after(0, _show_ok)
                else:
                    err = "\n".join(filter(None, [stderr, stdout])) or "Unbekannter Fehler"
                    if "Not allowed at this time" in err or "Connection reset" in err:
                        msg = "FEHLER  –  NAS hat Verbindung abgebrochen, zu viele Versuche? Kurz warten."
                    elif "Permission denied" in err:
                        msg = "FEHLER  –  Zugriff verweigert (Key abgelehnt oder falscher Benutzer)"
                    elif "Connection refused" in err:
                        msg = "FEHLER  –  Verbindung abgelehnt (SSH-Dienst aktiv? Port korrekt?)"
                    elif "No route to host" in err or "Network" in err:
                        msg = "FEHLER  –  NAS nicht erreichbar (IP/Netzwerk prüfen)"
                    else:
                        msg = (f"FEHLER  –  {err.splitlines()[-1]}" if err
                               else "FEHLER  –  Verbindung fehlgeschlagen (kein Fehlertext)")
                    def _show_err(m=msg, d=detail):
                        self._conn_status.config(text=m, fg="#f44336")
                        set_detail(d)
                        self.root.update()
                    self.root.after(0, _show_err)
            except FileNotFoundError as e:
                prog = str(e).split("'")[1] if "'" in str(e) else "ssh"
                def _show_fnf(p=prog):
                    self._conn_status.config(
                        text=f"FEHLER  –  '{p}' nicht gefunden (installieren?)",
                        fg="#f44336")
                    set_detail(f"'{p}' wurde nicht gefunden.\nInstallieren: sudo apt install {p}")
                    self.root.update()
                self.root.after(0, _show_fnf)
            except subprocess.TimeoutExpired:
                def _show_timeout():
                    self._conn_status.config(
                        text="FEHLER  –  Timeout (NAS nicht erreichbar)", fg="#f44336")
                    set_detail(f"Befehl: {' '.join(cmd)}\n\nKeine Antwort nach 12 Sekunden.")
                    self.root.update()
                self.root.after(0, _show_timeout)
            except Exception as e:
                def _show_exc(m=str(e)):
                    self._conn_status.config(
                        text=f"FEHLER  –  {m}", fg="#f44336")
                    set_detail(m)
                    self.root.update()
                self.root.after(0, _show_exc)

        threading.Thread(target=run, daemon=True).start()

    def _browse_nas_base(self) -> None:
        host  = self.nas_host.get().strip()
        uid   = os.getuid()
        gvfs  = f"/run/user/{uid}/gvfs"
        start = None

        if os.path.isdir(gvfs):
            for entry in os.listdir(gvfs):
                if f"server={host}" in entry:
                    start = os.path.join(gvfs, entry)
                    break

        if start is None:
            subprocess.Popen(["xdg-open", f"smb://{host}/"])
            self._zdlg("info", "NAS-Browser",
                f"Das NAS wird im Dateimanager geöffnet (smb://{host}/).\n\n"
                "Nach dem Mounten erneut auf ⛶ klicken —\n"
                "dann kann der Ordner direkt ausgewählt werden.")
            return

        from tkinter import filedialog
        path = (self._native_select_dir("Backup-Zielordner auf NAS wählen", start)
                or filedialog.askdirectory(
                    title="Backup-Zielordner auf NAS wählen", initialdir=start))
        if not path:
            return

        m = re.match(rf'^{re.escape(gvfs)}/smb-share:[^/]*,share=([^/]+)(.*)', path)
        if m:
            share, subpath = m.group(1), m.group(2)
            self.nas_base.set(f"/volume3/{share}{subpath}")
        else:
            self.nas_base.set(path)

    def _select_auth(self, val: str) -> None:
        self.auth_mode.set(val)
        for v, btn in self._auth_btns.items():
            if v == val:
                btn.config(bg=ACCENT, fg="#ffffff", font=("Sans", 12, "bold"))
            else:
                btn.config(bg=BTN, fg=FG, font=("Sans", 12))
        self._update_auth_fields()

    def _update_auth_fields(self) -> None:
        mode      = self.auth_mode.get()
        show_key  = mode in ("key", "key_fallback")
        show_pass = mode in ("password", "key_fallback")
        for w in (self._key_lbl, self._key_cell):
            w.grid() if show_key else w.grid_remove()
        for w in (self._pw_lbl, self._pw_cell, self._pf_lbl, self._pf_cell):
            w.grid() if show_pass else w.grid_remove()

    def _import_ssh_key(self) -> None:
        import shutil
        src = self._native_open_file(
            "SSH-Key auswählen",
            os.path.expanduser("~/Downloads"),
            "*.key *.pem *.ppk",
        ) or filedialog.askopenfilename(
            title="SSH-Key auswählen",
            initialdir=os.path.expanduser("~/Downloads"),
            filetypes=[("Key-Dateien", "*.key *.pem *.ppk id_*"),
                       ("Alle Dateien", "*")],
        )
        if not src:
            return

        basename = os.path.basename(src)
        if not any(basename.endswith(e) for e in (".key", ".pem", ".ppk")):
            basename += ".key"
        dest = os.path.join(os.path.expanduser("~/.ssh"), basename)

        if os.path.exists(dest):
            if not self._zdlg("question", "Datei existiert",
                    f"{dest}\nexistiert bereits.\n\nÜberschreiben?"):
                return

        try:
            os.makedirs(os.path.expanduser("~/.ssh"), exist_ok=True)
            shutil.copy2(src, dest)
            os.chmod(dest, 0o600)
        except OSError as e:
            self._zdlg("error", "Fehler", f"Import fehlgeschlagen:\n{e}")
            return

        self.ssh_key.set(dest)
        self._zdlg("info", "SSH-Key importiert",
            f"Key gespeichert unter:\n{dest}\n\n"
            "Berechtigungen: 600 (nur für dich lesbar)\n\n"
            "Verbindung testen um die Verbindung zu prüfen.")

    def _show_ssh_help(self) -> None:
        key_path = self.ssh_key.get().strip() or "~/.ssh/nas_backup.key"
        user = self.nas_user.get().strip() or "<NAS-Benutzer>"
        host = self.nas_host.get().strip() or "<NAS-IP>"
        port = self.nas_ssh_port.get().strip() or "22"

        win = tk.Toplevel(self.root)
        win.title("SSH-Schlüssel einrichten (ASUSTOR)")
        win.configure(bg=BG)
        win.geometry("600x480")
        win.resizable(True, True)

        tk.Label(win, text="SSH-Key einrichten auf ASUSTOR",
                 font=("Sans", 13, "bold"), bg=BG, fg=ACCENT
                 ).pack(anchor="w", padx=20, pady=(16, 8))

        steps = (
            "Das ASUSTOR-NAS generiert das Schlüsselpaar — du lädst den\n"
            "privaten Key herunter und legst ihn auf diesem PC ab.\n\n"
            "── Schritt 1: SSH-Dienst aktivieren ──────────────────────────\n"
            "  ADM → Dienste → Terminal → SSH aktivieren\n\n"
            "── Schritt 2: SSH-Schlüssel generieren ───────────────────────\n"
            f"  ADM → Dienste → Terminal → SSH-Schlüssel → Hinzufügen\n"
            f"  Benutzer: {user}   Format: .key\n"
            f"  → Privaten Key herunterladen und sicher aufbewahren!\n\n"
            "── Schritt 3: Key auf diesem PC ablegen ──────────────────────\n"
            f"  Heruntergeladene Datei verschieben nach:\n"
            f"    {key_path}\n\n"
            "  Berechtigungen setzen:\n"
            f"    chmod 600 \"{key_path}\"\n\n"
            "── Schritt 4: Verbindung testen ──────────────────────────────\n"
            f"  ssh -i \"{key_path}\" -p {port} {user}@{host}\n\n"
            "── Schritt 5: Passwort-Auth deaktivieren (optional) ──────────\n"
            "  ADM → Dienste → Terminal → SSH-Schlüssel\n"
            "  Haken bei \"Passwort-Authentifizierung\" entfernen\n"
            "  (erst nach erfolgreichem Test!)"
        )

        txt = tk.Text(win, bg=BG2, fg=FG, font=("Mono", 9), relief="flat",
                      padx=16, pady=12, wrap="word", state="normal")
        txt.pack(fill="both", expand=True, padx=16, pady=(0, 12))
        txt.insert("end", steps)
        txt.config(state="disabled")

        tk.Button(win, text="Schließen", command=win.destroy,
                  bg=BTN, fg=FG, relief="flat", padx=16, pady=6
                  ).pack(side="right", padx=16, pady=(0, 12))

    def _test_nas_path(self) -> None:
        host = self.nas_host.get().strip()
        user = self.nas_user.get().strip()
        port = self.nas_ssh_port.get().strip() or "22"
        key  = self.ssh_key.get().strip()
        path = self.nas_base.get().strip()
        mode = self.auth_mode.get()
        pw   = self.nas_password.get()

        if not host or not user:
            self._path_status_lbl.config(
                text="FEHLER  –  NAS-Host und Benutzer eintragen.", fg="#f44336")
            return
        if not path:
            self._path_status_lbl.config(
                text="FEHLER  –  Kein Pfad angegeben.", fg="#f44336")
            return

        self._path_status_lbl.config(text="Prüfe …", fg="#aaa")
        self.root.update()

        def run() -> None:
            env = os.environ.copy()
            env.pop("SSH_ASKPASS", None)
            env["SSH_ASKPASS_REQUIRE"] = "never"

            cmd = ["ssh", "-p", port,
                   "-o", "ConnectTimeout=8",
                   "-o", "StrictHostKeyChecking=accept-new"]

            if mode == "key":
                key_path = os.path.expanduser(key)
                cmd += ["-o", "BatchMode=yes", "-i", key_path,
                        "-o", "PreferredAuthentications=publickey",
                        "-o", "IdentitiesOnly=yes"]
            elif mode == "password":
                cmd += ["-o", "PreferredAuthentications=password"]
                env["SSHPASS"] = pw
                cmd = ["sshpass", "-e"] + cmd
            else:  # key_fallback
                key_path = os.path.expanduser(key)
                cmd += ["-i", key_path,
                        "-o", "PreferredAuthentications=publickey,password",
                        "-o", "IdentitiesOnly=yes"]
                env["SSHPASS"] = pw
                cmd = ["sshpass", "-e"] + cmd

            cmd += [f"{user}@{host}", f"test -d {path!r}"]

            try:
                result = subprocess.run(cmd, capture_output=True, text=True,
                                        timeout=12, env=env)
                rc = result.returncode
                if rc == 0:
                    def _ok(p=path):
                        self._path_status_lbl.config(
                            text=f"OK  –  Verzeichnis vorhanden: {p}",
                            fg="#4caf50")
                        self.root.update()
                    self.root.after(0, _ok)
                elif rc == 1:
                    def _missing(p=path):
                        self._path_status_lbl.config(
                            text=f"HINWEIS  –  Verzeichnis nicht gefunden: {p}"
                                 "  (wird beim ersten Backup angelegt)",
                            fg="#ff9800")
                        self.root.update()
                    self.root.after(0, _missing)
                else:
                    err = result.stderr.strip() or f"Exit-Code {rc}"
                    def _err(m=err):
                        self._path_status_lbl.config(
                            text=f"FEHLER  –  {m}", fg="#f44336")
                        self.root.update()
                    self.root.after(0, _err)
            except FileNotFoundError as e:
                prog = str(e).split("'")[1] if "'" in str(e) else "ssh"
                def _fnf(p=prog):
                    self._path_status_lbl.config(
                        text=f"FEHLER  –  '{p}' nicht gefunden", fg="#f44336")
                    self.root.update()
                self.root.after(0, _fnf)
            except subprocess.TimeoutExpired:
                def _timeout():
                    self._path_status_lbl.config(
                        text="FEHLER  –  Timeout (NAS nicht erreichbar)",
                        fg="#f44336")
                    self.root.update()
                self.root.after(0, _timeout)
            except Exception as e:
                def _exc(m=str(e)):
                    self._path_status_lbl.config(
                        text=f"FEHLER  –  {m}", fg="#f44336")
                    self.root.update()
                self.root.after(0, _exc)

        threading.Thread(target=run, daemon=True).start()
