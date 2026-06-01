import os
import re
import stat


# systemd-Unit-Namen: Buchstaben, Ziffern, '.' '_' '-' '@' ':' (keine Leerzeichen)
_SVC_NAME_RE = re.compile(r"[A-Za-z0-9._@:-]+")


class GeneratorMixin:
    """Generierung der Backup-, Service-, Timer- und Install-Skripte."""

    def _generieren(self) -> None:
        result = self._do_generate()
        if result is None:
            return
        svc, outdir, count = result
        self._zdlg("info", "Fertig",
            f"{count} Dateien generiert in:\n{outdir}\n\n"
            f"• {svc}.sh\n• {svc}.service\n• {svc}.timer\n"
            f"• install.sh\n• restore.sh\n• INSTALLATION.txt\n\n"
            f"Vollständige Anleitung:\n{outdir}/INSTALLATION.txt\n\n"
            f"Installation (als root):\nsudo bash {outdir}/install.sh")

    def _do_generate(self):
        """Validiert Konfiguration und schreibt alle Skript-Dateien.

        Returns:
            (svc, outdir, count) bei Erfolg, sonst None
            (Fehlermeldungen werden direkt via _zdlg angezeigt).
        """
        outdir = self.output_dir.get().strip()
        if not outdir:
            self._zdlg("error", "Fehler",
                "Kein Ausgabe-Pfad angegeben.\n\n"
                "Bitte unten ein Verzeichnis auswählen.")
            return None
        outdir = os.path.expanduser(outdir)
        try:
            os.makedirs(outdir, exist_ok=True)
        except OSError as e:
            self._zdlg("error", "Fehler",
                f"Ausgabe-Pfad konnte nicht angelegt werden:\n{outdir}\n\n{e}")
            return None

        svc  = self.service_name.get().strip() or "nas-backup"
        host = self.nas_host.get().strip()
        user = self.nas_user.get().strip()
        port = self.nas_ssh_port.get().strip() or "22"
        key  = self.ssh_key.get().strip()
        base = self.nas_base.get().strip()
        log  = self.log_file.get().strip()
        mode = self.auth_mode.get()

        if not host or not user:
            self._zdlg("error", "Fehler", "NAS-Host und Benutzer sind erforderlich.")
            return None
        if mode in ("key", "key_fallback") and not key:
            self._zdlg("error", "Fehler", "Kein SSH-Key angegeben.")
            return None
        if mode in ("password", "key_fallback") and not self.nas_password.get():
            self._zdlg("error", "Fehler", "Kein Passwort eingegeben.")
            return None
        if not self._sources:
            self._zdlg("error", "Fehler",
                "Mindestens ein Quell-Verzeichnis ist erforderlich.")
            return None
        if not _SVC_NAME_RE.fullmatch(svc):
            self._zdlg("error", "Fehler",
                f"Service-Name '{svc}' enthält ungültige Zeichen.\n"
                "Erlaubt: Buchstaben, Ziffern und  . _ - @ :")
            return None
        if not base.startswith("/"):
            self._zdlg("error", "Fehler",
                "Basis-Pfad auf NAS muss mit '/' beginnen "
                "(z.B. /volume1/backup/Linux).")
            return None

        files = {
            f"{svc}.sh":         self._gen_backup_sh(svc, host, user, port,
                                                      key, base, log, mode),
            f"{svc}.service":    self._gen_service(svc),
            f"{svc}.timer":      self._gen_timer(svc),
            "install.sh":        self._gen_install(svc, mode),
            "restore.sh":        self._gen_restore_sh(host, user, port,
                                                       key, base, mode),
            "INSTALLATION.txt":  self._gen_installation_txt(
                                     svc, host, user, port, base, log, mode, outdir),
        }
        for fname, content in files.items():
            path = os.path.join(outdir, fname)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(content)
            if fname.endswith(".sh"):
                os.chmod(path, os.stat(path).st_mode
                         | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

        # Letzte Einstellungen persistieren
        try:
            self._save_settings()
        except Exception:
            pass

        return svc, outdir, len(files)

    def _gen_backup_sh(self, svc: str, host: str, user: str, port: str,
                       key: str, base: str, log: str, mode: str) -> str:
        pf       = self.pass_file.get().strip()
        max_snap = self.max_snapshots.get()

        # ssh_opts  → wird *innerhalb* von rsync -e "…" verwendet, deshalb
        #             müssen alle inneren Quotes mit \" escaped sein, sonst
        #             schließen sie das äußere "…" und Variablen wie
        #             $SSH_KEY / $PASS_FILE landen unquoted in rsyncs Wortliste.
        # ssh_direct → wird direkt in der Shell ausgeführt; normale "…"-Quotes.
        if mode == "key":
            ssh_opts   = ('ssh -i \\"$SSH_KEY\\" -p $NAS_PORT'
                          ' -o StrictHostKeyChecking=accept-new -o IdentitiesOnly=yes')
            ssh_direct = ('ssh -i "$SSH_KEY" -p "$NAS_PORT"'
                          ' -o StrictHostKeyChecking=accept-new'
                          ' -o IdentitiesOnly=yes')
        elif mode == "password":
            ssh_opts   = ('sshpass -f \\"$PASS_FILE\\" ssh -p $NAS_PORT'
                          ' -o StrictHostKeyChecking=accept-new'
                          ' -o PreferredAuthentications=password')
            ssh_direct = ('sshpass -f "$PASS_FILE" ssh -p "$NAS_PORT"'
                          ' -o StrictHostKeyChecking=accept-new'
                          ' -o PreferredAuthentications=password')
        else:  # key_fallback
            ssh_opts   = ('sshpass -f \\"$PASS_FILE\\" ssh -i \\"$SSH_KEY\\" -p $NAS_PORT'
                          ' -o StrictHostKeyChecking=accept-new'
                          ' -o IdentitiesOnly=yes'
                          ' -o PreferredAuthentications=publickey,password')
            ssh_direct = ('sshpass -f "$PASS_FILE" ssh -i "$SSH_KEY"'
                          ' -p "$NAS_PORT"'
                          ' -o StrictHostKeyChecking=accept-new'
                          ' -o IdentitiesOnly=yes')

        excl = ""
        if self._excludes:
            excl = " \\\n  " + " \\\n  ".join(
                f'--exclude="{e}"' for e in self._excludes)

        blocks: list[str] = []
        for src in self._sources:
            name = src.strip("/").replace("/", "_")
            # ${LINK_BASE:+...} expandiert nur, wenn $LINK_BASE gesetzt ist;
            # beim Erstlauf (ohne vorherigen Snapshot) entfällt --link-dest
            # komplett und rsync gibt keine Warnung mehr aus.
            #
            # run_rsync() unten behandelt Exit-Code 24 (vanished files) als
            # Erfolg, da das nur eine Warnung ist (z.B. Logs/Caches, die
            # während des Backups gelöscht wurden).
            blocks.append(
                f'# {src}\n'
                f'run_rsync "{src}" -aHz --numeric-ids --no-specials --no-devices --delete{excl} \\\n'
                f'  --rsync-path="rsync --fake-super" \\\n'
                f'  ${{LINK_BASE:+--link-dest="$LINK_BASE/{name}"}} \\\n'
                f'  -e "{ssh_opts}" \\\n'
                f'  {src}/ \\\n'
                f'  "${{NAS_USER}}@${{NAS_HOST}}:${{NAS_BASE}}/${{DATE}}/{name}/"'
            )

        dpkg_export = ""
        dpkg_rsync  = ""
        if self.dpkg_backup.get():
            dpkg_export = (
                '\n# Paketliste\n'
                'dpkg --get-selections > /tmp/nas-backup-packages.txt\n'
            )
            dpkg_rsync = (
                '\n\n# Paketliste übertragen\n'
                'run_rsync "packages.txt" -az \\\n'
                f'  -e "{ssh_opts}" \\\n'
                '  /tmp/nas-backup-packages.txt \\\n'
                '  "${NAS_USER}@${NAS_HOST}:${NAS_BASE}/${DATE}/packages.txt"'
            )

        # Restore-Skript bei jedem Backup-Lauf neben den Snapshots
        # spiegeln, damit es im Disaster-Fall (komplett wiederherstellen
        # auf neuer Hardware) per scp vom NAS gezogen werden kann.
        restore_to_nas = (
            '\n\n# Restore-Skript auf NAS spiegeln (Disaster-Recovery)\n'
            'if [ -f /etc/backup/restore.sh ]; then\n'
            '  run_rsync "restore.sh" -az \\\n'
            f'    -e "{ssh_opts}" \\\n'
            '    /etc/backup/restore.sh \\\n'
            '    "${NAS_USER}@${NAS_HOST}:${NAS_BASE}/restore.sh"\n'
            'else\n'
            '  echo "[WARNUNG] /etc/backup/restore.sh nicht gefunden – '
            'übersprungen"\n'
            'fi'
        )

        ssh_cmd = f'{ssh_direct} "${{NAS_USER}}@${{NAS_HOST}}"'

        dirs_to_create = " ".join(
            f'${{NAS_BASE}}/${{DATE}}/{src.strip("/").replace("/", "_")}'
            for src in self._sources
        )
        mkdir_block = (
            '\n# Zielverzeichnisse auf NAS anlegen (NAS_BASE + Snapshot-Subdirs)\n'
            f'{ssh_cmd} \\\n'
            f'  "mkdir -p ${{NAS_BASE}} {dirs_to_create}" \\\n'
            '  && echo "[OK] Verzeichnisse angelegt" \\\n'
            '  || { echo "[FEHLER] mkdir auf NAS"; exit 1; }\n'
            '\n'
            '# Vorherigen Snapshot ermitteln (für --link-dest = Hardlinks).\n'
            '# Sucht nach echten YYYY-MM-DD-Verzeichnissen ungleich heute,\n'
            '# nicht auf den \'latest\'-Symlink vertrauend (der könnte\n'
            '# verwaist sein, wenn das Ziel gelöscht wurde).\n'
            'LINK_BASE=""\n'
            f'PREV_SNAP=$({ssh_cmd} \\\n'
            '  "find \\"${NAS_BASE}\\" -maxdepth 1 -type d '
            '-name \\"[0-9]*-[0-9]*-[0-9]*\\" '
            '! -name \\"${DATE}\\" 2>/dev/null | sort | tail -n1")\n'
            'if [ -n "$PREV_SNAP" ] && [ -n "$(echo \"$PREV_SNAP\" | tr -d \'[:space:]\')" ]; then\n'
            '  LINK_BASE="$PREV_SNAP"\n'
            '  echo "[INFO] vorheriger Snapshot: $PREV_SNAP → Hardlinks aktiv"\n'
            'else\n'
            '  echo "[INFO] kein vorheriger Snapshot → erstes Vollbackup"\n'
            'fi'
        )
        retention = (
            f'\n\n# Alte Snapshots aufräumen (max. {max_snap})\n'
            f'SNAP_COUNT=$({ssh_cmd} \\\n'
            f'  "ls -1d ${{NAS_BASE}}/*-*-* 2>/dev/null | wc -l")\n'
            f'if [ "$SNAP_COUNT" -gt {max_snap} ]; then\n'
            f'  DEL=$(( SNAP_COUNT - {max_snap} ))\n'
            f'  {ssh_cmd} \\\n'
            f'    "ls -1d ${{NAS_BASE}}/*-*-* 2>/dev/null | sort | head -n $DEL | xargs -r rm -rf"\n'
            f'  echo "[OK] $DEL alte(n) Snapshot(s) gelöscht"\n'
            f'fi'
        )
        symlink = (
            f'\n\n# latest-Symlink aktualisieren\n'
            f'{ssh_cmd} \\\n'
            f'  "cd ${{NAS_BASE}} && ln -sfn ${{DATE}} latest" \\\n'
            '  && echo "[OK] Symlink latest -> ${DATE}" \\\n'
            '  || echo "[WARNUNG] Symlink konnte nicht aktualisiert werden"'
        )

        auth_comment = {
            "key":          "# Authentifizierung: SSH-Key",
            "password":     "# Authentifizierung: Passwort (sshpass)",
            "key_fallback": "# Authentifizierung: SSH-Key mit Passwort-Fallback",
        }[mode]

        key_line = f'SSH_KEY="{key}"\n' if mode in ("key", "key_fallback") else ""
        pf_line  = f'PASS_FILE="{pf}"\n' if mode in ("password", "key_fallback") else ""

        # /tmp/nas-backup-packages.txt nur, wenn dpkg_backup aktiv ist
        cleanup_trap = ('trap \'rm -f /tmp/nas-backup-packages.txt\' EXIT\n'
                        if self.dpkg_backup.get() else "")

        return (
            '#!/bin/bash\n'
            f'# Generiert von NAS-Backup-Generator\n'
            f'{auth_comment}\n\n'
            'set -uo pipefail\n\n'
            f'NAS_USER="{user}"\n'
            f'NAS_HOST="{host}"\n'
            f'NAS_PORT="{port}"\n'
            f'NAS_BASE="{base}"\n'
            f'LOG="{log}"\n'
            f'DATE=$(date +%Y-%m-%d)\n'
            f'{key_line}'
            f'{pf_line}\n'
            'ERRORS=0\n'
            f'{cleanup_trap}'
            '\n'
            '# Im interaktiven Test-Lauf (NAS_BACKUP_LIVE_LOG=1) Output NICHT\n'
            '# in die Logdatei umleiten, sondern auf stdout für Live-Anzeige.\n'
            'if [ "${NAS_BACKUP_LIVE_LOG:-0}" != "1" ]; then\n'
            '  mkdir -p "$(dirname "$LOG")"\n'
            '  exec >> "$LOG" 2>&1\n'
            'fi\n'
            '\n'
            '# Helper: rsync starten und Exit-Code 24 (vanished files) als\n'
            '# Erfolg behandeln. Dateien, die WÄHREND des Backups gelöscht\n'
            '# werden (Logs, gvfs-Metadata, Browser-Caches), produzieren\n'
            '# eine harmlose Warnung — der Rest wird trotzdem korrekt\n'
            '# kopiert. Nur "echte" Fehler erhöhen ERRORS.\n'
            'run_rsync() {\n'
            '  local label="$1"; shift\n'
            '  rsync "$@"\n'
            '  local rc=$?\n'
            '  if [ "$rc" -eq 0 ]; then\n'
            '    echo "[OK] $label"\n'
            '  elif [ "$rc" -eq 24 ]; then\n'
            '    echo "[OK] $label (einige Dateien während des Backups '
            'verschwunden – harmlos)"\n'
            '  else\n'
            '    echo "[FEHLER] $label (rsync Exit-Code $rc)"\n'
            '    ERRORS=$((ERRORS+1))\n'
            '  fi\n'
            '}\n'
            '\n'
            'echo ""\n'
            'echo "=== Backup gestartet: $(date) ==="\n'
            f'{dpkg_export}'
            f'{mkdir_block}\n\n'
            + "\n\n".join(blocks)
            + f'{dpkg_rsync}'
            + f'{restore_to_nas}'
            + f'{retention}'
            + f'{symlink}\n\n'
            'if [ "$ERRORS" -gt 0 ]; then\n'
            '  echo "=== Backup mit $ERRORS Fehler(n) abgeschlossen: $(date) ==="\n'
            '  exit 1\n'
            'fi\n'
            'echo "=== Backup erfolgreich abgeschlossen: $(date) ==="\n'
        )

    def _gen_service(self, svc: str) -> str:
        return (
            '[Unit]\n'
            f'Description=NAS Backup – {svc}\n'
            'After=network-online.target\n'
            'Wants=network-online.target\n\n'
            '[Service]\n'
            'Type=oneshot\n'
            f'ExecStart=/bin/bash /etc/backup/{svc}.sh\n'
            'User=root\n'
            'TimeoutStartSec=6h\n'
            'StandardOutput=journal\n'
            'StandardError=journal\n'
        )

    def _gen_timer(self, svc: str) -> str:
        lines = [
            '[Unit]',
            f'Description=NAS Backup Timer – {svc}',
            '',
            '[Timer]',
            f'OnCalendar={self._on_calendar()}',
        ]
        if self.persistent.get():
            lines.append('Persistent=true')
        lines += ['', '[Install]', 'WantedBy=timers.target', '']
        return "\n".join(lines)

    def _gen_install(self, svc: str, mode: str) -> str:
        log = self.log_file.get().strip()
        pf  = self.pass_file.get().strip()

        passfile_block = ""
        if mode in ("password", "key_fallback"):
            pw     = self.nas_password.get()
            pf_dir = os.path.dirname(pf)
            # Apostrophe im Passwort für single-quoted Bash-String escapen:
            # 'foo' bricht den Quote, '\\'' (close-escape-open) hängt einen
            # echten Apostroph an, dann wird wieder geöffnet.
            pw_q = pw.replace("'", "'\\''")
            passfile_block = (
                '\n# Passwort-Datei anlegen (nur root lesbar)\n'
                f'mkdir -p "{pf_dir}"\n'
                f"printf '%s' '{pw_q}' > \"{pf}\"\n"
                f'chmod 600 "{pf}"\n'
                f'chown root:root "{pf}"\n'
            )

        return (
            '#!/bin/bash\n'
            f'# Installationsskript für {svc}\n'
            'set -e\n\n'
            '# Root-Check\n'
            'if [ "$(id -u)" -ne 0 ]; then\n'
            '  echo "Bitte als root ausführen:  sudo bash $0"\n'
            '  exit 1\n'
            'fi\n\n'
            'SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"\n\n'
            '# Backup-Skript nach /etc/backup/ kopieren\n'
            'mkdir -p /etc/backup\n'
            f'cp "$SCRIPT_DIR/{svc}.sh" /etc/backup/{svc}.sh\n'
            f'chmod 700 /etc/backup/{svc}.sh\n\n'
            '# Restore-Skript ebenfalls nach /etc/backup/\n'
            'cp "$SCRIPT_DIR/restore.sh" /etc/backup/restore.sh\n'
            'chmod 700 /etc/backup/restore.sh\n\n'
            '# Log-Datei anlegen\n'
            f'touch "{log}"\n'
            f'chmod 600 "{log}"\n'
            f'{passfile_block}\n'
            '# systemd-Units installieren\n'
            f'cp "$SCRIPT_DIR/{svc}.service" /etc/systemd/system/\n'
            f'cp "$SCRIPT_DIR/{svc}.timer"   /etc/systemd/system/\n\n'
            'systemctl daemon-reload\n'
            f'systemctl enable --now {svc}.timer\n\n'
            'echo ""\n'
            'echo "✔ Installation abgeschlossen"\n'
            f'systemctl status {svc}.timer --no-pager\n'
        )

    def _gen_restore_sh(self, host: str, user: str, port: str,
                        key: str, base: str, mode: str) -> str:
        """Generiert ein interaktives Restore-Skript.

        Holt einen Snapshot vom NAS zurück (Standard: 'latest') und stellt
        Quell-Verzeichnisse + dpkg-Paketliste wieder her. Dieselben SSH-
        Optionen wie im Backup-Skript, gleiche Auth-Modi.
        """
        pf = self.pass_file.get().strip()

        # SSH-Optionen je Modus – genau spiegelbildlich zum Backup-Skript.
        # ssh_direct → Shell-Aufruf für ls/[ -e ] auf dem NAS (normale Quotes)
        # rsync_e    → Wert für rsync -e "…" — alle inneren Quotes escapt,
        #              sonst schließen sie das äußere "…" und Pfade mit
        #              Leerzeichen werden zerwortet.
        if mode == "key":
            ssh_direct = ('ssh -i "$SSH_KEY" -p "$NAS_PORT"'
                          ' -o IdentitiesOnly=yes'
                          ' -o StrictHostKeyChecking=accept-new')
            rsync_e    = ('ssh -i \\"$SSH_KEY\\" -p $NAS_PORT'
                          ' -o IdentitiesOnly=yes'
                          ' -o StrictHostKeyChecking=accept-new')
        elif mode == "password":
            ssh_direct = ('sshpass -f "$PASS_FILE" ssh -p "$NAS_PORT"'
                          ' -o StrictHostKeyChecking=accept-new'
                          ' -o PreferredAuthentications=password')
            rsync_e    = ('sshpass -f \\"$PASS_FILE\\" ssh -p $NAS_PORT'
                          ' -o StrictHostKeyChecking=accept-new'
                          ' -o PreferredAuthentications=password')
        else:  # key_fallback
            ssh_direct = ('sshpass -f "$PASS_FILE" ssh -i "$SSH_KEY"'
                          ' -p "$NAS_PORT" -o IdentitiesOnly=yes'
                          ' -o StrictHostKeyChecking=accept-new')
            rsync_e    = ('sshpass -f \\"$PASS_FILE\\" ssh -i \\"$SSH_KEY\\"'
                          ' -p $NAS_PORT -o IdentitiesOnly=yes'
                          ' -o StrictHostKeyChecking=accept-new')

        # Pro Quelle ein rsync-Block (NAS → lokal).
        src_blocks: list[str] = []
        for src in self._sources:
            name = src.strip("/").replace("/", "_")
            src_blocks.append(
                f'echo ""\n'
                f'echo "──→ {src} aus Snapshot wiederherstellen…"\n'
                f'rsync -aH --numeric-ids $DRY_RUN $DELETE \\\n'
                f'  --rsync-path="rsync --fake-super" \\\n'
                f'  --info=progress2 \\\n'
                f'  -e "{rsync_e}" \\\n'
                f'  "${{NAS_USER}}@${{NAS_HOST}}:${{NAS_BASE}}/${{SNAPSHOT}}/{name}/" \\\n'
                f'  {src}/ \\\n'
                f'  && echo "[OK] {src}" \\\n'
                f'  || {{ echo "[FEHLER] {src}"; ERRORS=$((ERRORS+1)); }}'
            )

        key_line = f'SSH_KEY="{key}"\n' if mode in ("key", "key_fallback") else ""
        pf_line  = f'PASS_FILE="{pf}"\n' if mode in ("password", "key_fallback") else ""

        # Bestätigungs-Liste der Quellen für die "ACHTUNG"-Box
        src_echo = "\n".join(f'  echo "    {src}"' for src in self._sources)

        # Pakete-Block nur wenn dpkg-Paketliste auch gesichert wird
        if self.dpkg_backup.get():
            packages_block = (
                '\n# ── Paketliste ─────────────────────────────────────\n'
                'if [ "$INSTALL_PACKAGES" != "no" ]; then\n'
                '  echo ""\n'
                '  echo "──→ Paketliste laden…"\n'
                f'  rsync -az $DRY_RUN \\\n'
                f'    -e "{rsync_e}" \\\n'
                '    "${NAS_USER}@${NAS_HOST}:${NAS_BASE}/${SNAPSHOT}/packages.txt" \\\n'
                '    /tmp/restore-packages.txt 2>/dev/null \\\n'
                '    || echo "Hinweis: keine packages.txt im Snapshot."\n'
                '  if [ -f /tmp/restore-packages.txt ] && [ -z "$DRY_RUN" ]; then\n'
                '    if [ "$INSTALL_PACKAGES" = "ask" ]; then\n'
                '      echo ""\n'
                '      echo "Differenz Paketliste (Backup) ↔ aktuell installiert:"\n'
                '      diff <(dpkg --get-selections | sort) \\\n'
                '           <(sort /tmp/restore-packages.txt) | head -30 || true\n'
                '      echo ""\n'
                '      read -r -p "Pakete laut Backup installieren? [j/N] " ans\n'
                '      case "$ans" in\n'
                '        [jJyY]*) INSTALL_PACKAGES="yes" ;;\n'
                '        *)       INSTALL_PACKAGES="no"  ;;\n'
                '      esac\n'
                '    fi\n'
                '    if [ "$INSTALL_PACKAGES" = "yes" ]; then\n'
                '      echo "──→ apt update…"\n'
                '      apt-get update\n'
                '      echo "──→ dpkg --set-selections…"\n'
                '      dpkg --set-selections < /tmp/restore-packages.txt\n'
                '      echo "──→ apt-get dselect-upgrade…"\n'
                '      DEBIAN_FRONTEND=noninteractive \\\n'
                '        apt-get dselect-upgrade -y\n'
                '    fi\n'
                '  fi\n'
                'fi\n'
            )
        else:
            packages_block = ""

        return (
            '#!/bin/bash\n'
            '#\n'
            '# Restore-Skript – holt Snapshots vom NAS zurück und stellt\n'
            '# Quell-Verzeichnisse + dpkg-Paketliste wieder her.\n'
            '#\n'
            'set -uo pipefail\n\n'
            '# ── Konfiguration (aus Backup übernommen) ──────────────\n'
            f'NAS_USER="{user}"\n'
            f'NAS_HOST="{host}"\n'
            f'NAS_PORT="{port}"\n'
            f'NAS_BASE="{base}"\n'
            f'{key_line}{pf_line}'
            '\n'
            'SNAPSHOT="latest"\n'
            'DRY_RUN=""\n'
            'DELETE=""\n'
            'INSTALL_PACKAGES="ask"   # ask / yes / no\n'
            'LIST_ONLY=0\n'
            'ERRORS=0\n\n'
            'show_help() {\n'
            "  cat <<'HELP'\n"
            'Restore-Skript für nas-backup\n'
            '\n'
            'Aufruf:\n'
            '  sudo bash restore.sh                  neuester Snapshot\n'
            '  sudo bash restore.sh 2026-05-08       bestimmter Snapshot\n'
            '  sudo bash restore.sh --list           verfügbare Snapshots\n'
            '  sudo bash restore.sh --dry-run        Vorschau, kein Schreiben\n'
            '  sudo bash restore.sh --purge          mit --delete (lokale Extras löschen)\n'
            '  sudo bash restore.sh --no-packages    Paketliste überspringen\n'
            '  sudo bash restore.sh --yes-packages   Pakete ohne Nachfrage installieren\n'
            '  sudo bash restore.sh -h | --help      diese Hilfe\n'
            'HELP\n'
            '}\n\n'
            '# ── Argumente ──────────────────────────────────────────\n'
            'while [ $# -gt 0 ]; do\n'
            '  case "$1" in\n'
            '    -h|--help)      show_help; exit 0 ;;\n'
            '    --list)         LIST_ONLY=1 ;;\n'
            '    --dry-run)      DRY_RUN="--dry-run" ;;\n'
            '    --purge)        DELETE="--delete" ;;\n'
            '    --no-packages)  INSTALL_PACKAGES="no" ;;\n'
            '    --yes-packages) INSTALL_PACKAGES="yes" ;;\n'
            '    -*) echo "Unbekannte Option: $1"; show_help; exit 1 ;;\n'
            '    *)  SNAPSHOT="$1" ;;\n'
            '  esac\n'
            '  shift\n'
            'done\n\n'
            '# ── root-Check ─────────────────────────────────────────\n'
            'if [ "$(id -u)" -ne 0 ]; then\n'
            '  echo "Bitte als root ausführen: sudo bash $0"\n'
            '  exit 1\n'
            'fi\n\n'
            f'SSH=({ssh_direct})\n\n'
            '# ── Snapshots auf NAS auflisten ─────────────────────────\n'
            'echo "Verfügbare Snapshots auf NAS:"\n'
            '"${SSH[@]}" "${NAS_USER}@${NAS_HOST}" \\\n'
            '  "ls -1d ${NAS_BASE}/*-*-* 2>/dev/null | xargs -n1 basename" \\\n'
            '  || { echo "Fehler: SSH-Verbindung zum NAS fehlgeschlagen."; exit 2; }\n\n'
            'if [ "$LIST_ONLY" -eq 1 ]; then exit 0; fi\n\n'
            'echo ""\n'
            'echo "Snapshot zum Wiederherstellen: ${SNAPSHOT}"\n\n'
            '# ── Snapshot existiert? ────────────────────────────────\n'
            'if ! "${SSH[@]}" "${NAS_USER}@${NAS_HOST}" \\\n'
            '     "[ -e ${NAS_BASE}/${SNAPSHOT} ]" 2>/dev/null; then\n'
            '  echo "Fehler: Snapshot \\"${SNAPSHOT}\\" nicht gefunden auf NAS."\n'
            '  exit 3\n'
            'fi\n\n'
            '# ── Bestätigung ────────────────────────────────────────\n'
            'if [ -z "$DRY_RUN" ]; then\n'
            '  echo ""\n'
            '  echo "ACHTUNG: Folgende Verzeichnisse werden vom NAS überschrieben:"\n'
            f'{src_echo}\n'
            '  if [ -n "$DELETE" ]; then\n'
            '    echo ""\n'
            '    echo "  --purge gesetzt: lokale Extra-Dateien werden GELÖSCHT."\n'
            '  fi\n'
            '  echo ""\n'
            '  read -r -p "Wirklich fortfahren? [j/N] " ans\n'
            '  case "$ans" in [jJyY]*) ;; *) echo "Abbruch."; exit 0 ;; esac\n'
            'fi\n\n'
            '# ── Quellen wiederherstellen ───────────────────────────\n'
            + "\n\n".join(src_blocks) + '\n'
            f'{packages_block}'
            '\necho ""\n'
            'if [ "$ERRORS" -gt 0 ]; then\n'
            '  echo "✘ Wiederherstellung mit $ERRORS Fehler(n) abgeschlossen."\n'
            '  exit 1\n'
            'fi\n'
            'echo "✔ Wiederherstellung abgeschlossen."\n'
        )

    def _gen_installation_txt(self, svc: str, host: str, user: str,
                               port: str, base: str, log: str,
                               mode: str, outdir: str) -> str:
        """Erzeugt eine vollständige deutsche Installationsanleitung als .txt."""
        oncal = self._on_calendar()
        persistent = "ja" if self.persistent.get() else "nein"
        dpkg_active = self.dpkg_backup.get()
        max_snap = self.max_snapshots.get()
        pf = self.pass_file.get().strip()

        auth_text = {
            "key":          "SSH-Key-Authentifizierung",
            "password":     "Passwort-Authentifizierung (via sshpass)",
            "key_fallback": "SSH-Key mit Passwort-Fallback (via sshpass)",
        }[mode]

        sshpass_line = (
            "  • sshpass        (sudo apt install sshpass)\n"
            if mode in ("password", "key_fallback") else ""
        )

        pf_line = (
            f"    • Legt die Passwort-Datei {pf} an (chmod 600, root:root)\n"
            if mode in ("password", "key_fallback") else ""
        )

        quellen_block = "\n".join(f"  • {s}" for s in self._sources)
        excludes_block = ("\n".join(f"  • {e}" for e in self._excludes)
                          if self._excludes else "  (keine)")

        dpkg_block = (
            "  • Sichert zusätzlich die Paketliste:\n"
            "      dpkg --get-selections  →  packages.txt\n\n"
            if dpkg_active else ""
        )

        return (
            "═══════════════════════════════════════════════════════════════════════\n"
            f"  NAS-Backup ({svc}) – Installationsanleitung\n"
            "═══════════════════════════════════════════════════════════════════════\n"
            "\n"
            "Generiert vom NAS-Backup-Generator.\n"
            "\n"
            "GENERIERTE DATEIEN\n"
            "──────────────────\n"
            f"  • {svc}.sh           Das Backup-Skript (wird via systemd ausgeführt)\n"
            f"  • {svc}.service      systemd-Service-Unit\n"
            f"  • {svc}.timer        systemd-Timer (Zeitplan)\n"
            "  • install.sh         Installations-Skript\n"
            "  • restore.sh         Wiederherstellungs-Skript\n"
            "  • INSTALLATION.txt   diese Anleitung\n"
            "\n"
            "ZIEL (NAS)\n"
            "──────────\n"
            f"  • Host:         {host}\n"
            f"  • Benutzer:     {user}\n"
            f"  • SSH-Port:     {port}\n"
            f"  • Backup-Pfad:  {base}\n"
            f"  • Auth-Modus:   {auth_text}\n"
            "\n"
            "ZEITPLAN\n"
            "────────\n"
            f"  • OnCalendar:   {oncal}\n"
            f"  • Persistent:   {persistent}  (verpassten Lauf nachholen)\n"
            "\n"
            "QUELL-VERZEICHNISSE\n"
            "───────────────────\n"
            f"{quellen_block}\n"
            "\n"
            "AUSSCHLUSS-MUSTER\n"
            "─────────────────\n"
            f"{excludes_block}\n"
            "\n"
            "AUFBEWAHRUNG\n"
            "────────────\n"
            f"  • Max. Snapshots auf NAS: {max_snap}\n"
            f"{dpkg_block}"
            "\n"
            "VORAUSSETZUNGEN\n"
            "───────────────\n"
            "  • Debian/Ubuntu-Linux mit systemd\n"
            "  • rsync, openssh-client (Standardpakete)\n"
            f"{sshpass_line}"
            f"  • SSH-Zugang zum NAS muss eingerichtet sein\n"
            "\n"
            "INSTALLATION\n"
            "────────────\n"
            "  1. In das Verzeichnis mit den generierten Dateien wechseln:\n"
            f"     cd \"{outdir}\"\n"
            "\n"
            "  2. Installation als root starten:\n"
            "     sudo bash install.sh\n"
            "\n"
            "  Was install.sh macht:\n"
            f"    • Kopiert {svc}.sh und restore.sh nach /etc/backup/\n"
            f"    • Legt die Log-Datei {log} an\n"
            "    • Installiert die systemd-Units nach /etc/systemd/system/\n"
            f"{pf_line}"
            f"    • Aktiviert und startet {svc}.timer\n"
            "\n"
            "TIMER-STATUS PRÜFEN\n"
            "───────────────────\n"
            f"  systemctl status {svc}.timer\n"
            f"  systemctl list-timers {svc}.timer\n"
            "\n"
            "LOG ANSEHEN\n"
            "───────────\n"
            f"  sudo tail -f {log}\n"
            f"  journalctl -u {svc}.service -f\n"
            "\n"
            "MANUELLES BACKUP STARTEN\n"
            "────────────────────────\n"
            f"  sudo systemctl start {svc}.service\n"
            "\n"
            "WIEDERHERSTELLUNG\n"
            "─────────────────\n"
            "  sudo bash /etc/backup/restore.sh                  # neuester Snapshot\n"
            "  sudo bash /etc/backup/restore.sh 2026-05-08       # bestimmter Snapshot\n"
            "  sudo bash /etc/backup/restore.sh --list           # verfügbare Snapshots\n"
            "  sudo bash /etc/backup/restore.sh --dry-run        # Vorschau, kein Schreiben\n"
            "  sudo bash /etc/backup/restore.sh --purge          # mit --delete\n"
            "  sudo bash /etc/backup/restore.sh --help           # alle Optionen\n"
            "\n"
            "DISASTER-RECOVERY\n"
            "─────────────────\n"
            "Bei jedem Backup wird restore.sh zusätzlich auf das NAS gespiegelt\n"
            f"(nach {base}/restore.sh). Bei Total-Verlust\n"
            "kann es so wieder geholt werden:\n"
            "\n"
            f"  scp -P {port} {user}@{host}:{base}/restore.sh ./restore.sh\n"
            "  sudo bash ./restore.sh --list\n"
            "  sudo bash ./restore.sh <snapshot-datum>\n"
            "\n"
            "Hinweis: Auf der frisch installierten Maschine muss rsync, ssh und\n"
            "ggf. sshpass vorhanden sein und der SSH-Key (bzw. Passwort) zum NAS.\n"
            "\n"
            "DEAKTIVIEREN / ENTFERNEN\n"
            "────────────────────────\n"
            f"  sudo systemctl disable --now {svc}.timer\n"
            f"  sudo rm /etc/systemd/system/{svc}.service\n"
            f"  sudo rm /etc/systemd/system/{svc}.timer\n"
            f"  sudo rm -rf /etc/backup/\n"
            "  sudo systemctl daemon-reload\n"
            "\n"
            "NAS-VERZEICHNISSTRUKTUR\n"
            "───────────────────────\n"
            f"  {base}/\n"
            "  ├── YYYY-MM-DD/      ← datierter Snapshot\n"
            "  │   ├── home/\n"
            "  │   ├── etc/\n"
            f"  │   └── packages.txt   {'(dpkg-Paketliste)' if dpkg_active else '(nicht aktiv)'}\n"
            "  └── latest -> YYYY-MM-DD  (Symlink auf neuesten Snapshot)\n"
            "\n"
            "rsync-FLAGS\n"
            "───────────\n"
            "  -a   Archiv-Modus (rekursiv, Rechte, Timestamps, Symlinks, Owner …)\n"
            "  -H   Hardlinks innerhalb der Quelle erhalten\n"
            "  -z   komprimierte Übertragung\n"
            "  --no-specials --no-devices\n"
            "                 Sockets/FIFOs/Geräte-Dateien überspringen. Auf solchen\n"
            "                 Spezialdateien lassen sich keine xattrs setzen, was sonst\n"
            "                 mit --fake-super zu Exit-Code 23 führt. In einem Backup\n"
            "                 sind sie ohnehin wertlos (reine Laufzeit-Endpunkte).\n"
            "  --numeric-ids  uid/gid numerisch übertragen (kein Namensmapping)\n"
            "  --rsync-path=\"rsync --fake-super\"\n"
            "                 Da rsync auf dem NAS als normaler Benutzer (nicht root)\n"
            "                 läuft, kann es Original-Owner/-Rechte nicht real setzen.\n"
            "                 --fake-super speichert sie stattdessen in erweiterten\n"
            "                 Attributen (xattr). Zwei Effekte:\n"
            "                   1) Owner/Rechte bleiben fürs Restore erhalten\n"
            "                   2) Attribute passen bei jedem Lauf zur Quelle, sodass\n"
            "                      --link-dest unveränderte Dateien als Hardlink\n"
            "                      erkennt (sonst Vollkopie bei jedem Lauf!)\n"
            "  --delete       Dateien, die auf der Quelle fehlen, auch auf NAS löschen\n"
            "  --link-dest    Unveränderte Dateien als Hardlink zum vorherigen\n"
            "                 Snapshot — extrem platzsparend\n"
            "\n"
            "═══════════════════════════════════════════════════════════════════════\n"
        )
