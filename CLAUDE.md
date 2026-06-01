# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Projektzweck

`nas-backup.sh` sichert `/home` und `/etc` eines Debian/Ubuntu-Systems inkrementell auf ein **Asustor NAS (AS5402T, ADM-OS)** via rsync über SSH. Jede Ausführung legt einen datierten Snapshot an (`YYYY-MM-DD/`) und nutzt Hardlinks auf den vorherigen `latest`-Snapshot, um Speicherplatz zu sparen. Außerdem wird die Paketliste (`dpkg --get-selections`) gesichert.

## Abhängigkeiten

- `bash`, `rsync`, `openssh-client` (Standardpakete)
- `dpkg` (Debian/Ubuntu)
- SSH-Key unter `/home/hero/.ssh/id_ed25519` muss auf dem NAS autorisiert sein
- Asustor AS5402T (`192.168.178.52`) mit aktiviertem rsync-Modul (`hero_lw3`) und SSH-Zugang auf **Port 29**, User `Hero` (SMB-Pfad zur Referenz: `smb://192.168.178.52/backup_lw3/Linux`)
- Volume auf dem NAS sollte **Btrfs oder ext4** sein, damit Hardlinks (`--link-dest`) funktionieren

## Konfiguration (Variablen am Skriptanfang)

| Variable | Bedeutung |
|---|---|
| `NAS_USER` / `NAS_HOST` | SSH-Zugangsdaten zum NAS |
| `NAS_MODULE` | rsync-Modulname auf dem NAS |
| `SSH_KEY` | Pfad zum privaten SSH-Schlüssel |
| `LOG` | Log-Datei (erfordert Schreibrecht, z. B. via sudo) |

## Ausführen

```bash
# Syntax-Check (kein NAS nötig)
bash -n nas-backup.sh

# Backup starten (NAS muss erreichbar sein)
sudo bash nas-backup.sh

# Log verfolgen
sudo tail -f /var/log/nas-backup.log
```

## NAS-Verzeichnisstruktur

Auf dem Asustor liegt das Backup unter **`/volume3/Backup_LW3`** (das relevante Volume ist Volume 3, nicht der ADM-Standard Volume 1):

```
/volume3/Backup_LW3/Linux/
├── 2025-04-01/
│   ├── home/
│   ├── etc/
│   └── packages.txt
├── 2025-04-02/
│   └── ...
└── latest -> 2025-04-02   (Symlink)
```

## Automation

**systemd-Timer** (empfohlen):
```
/etc/systemd/system/nas-backup.service
/etc/systemd/system/nas-backup.timer
```

**cron** (alternativ):
```cron
0 3 * * * root /bin/bash /pfad/zu/nas-backup.sh
```

## Dry-Run

Um das Skript ohne tatsächliche Übertragung zu testen, `--dry-run` zu den rsync-Aufrufen hinzufügen:
```bash
rsync -aAXz --dry-run --delete ...
```
