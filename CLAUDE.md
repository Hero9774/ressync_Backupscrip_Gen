# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Projektzweck

Dieses Repo ist ein **Tkinter-GUI-Generator** (Dark-Theme, mehrere Tabs), der
fertige Skripte für inkrementelle **rsync-über-SSH-Backups auf ein NAS** erzeugt.
Erzeugt werden: das Backup-Skript, ein Restore-Skript, systemd-`.service`/`.timer`,
ein `install.sh` und eine `INSTALLATION.txt`.

Die generierten Backups legen pro Lauf einen datierten Snapshot (`YYYY-MM-DD/`) an
und verlinken unveränderte Dateien per Hardlink (`--link-dest`) auf den vorherigen
Snapshot, um Speicherplatz zu sparen. Optional wird die Paketliste
(`dpkg --get-selections`) mitgesichert.

## Aufbau

Reine Python-Standardbibliothek (`tkinter`), keine externen Abhängigkeiten.

| Datei | Inhalt |
|---|---|
| `nas_backup_generator.py` | App-Einstieg, definiert alle GUI-Variablen/Defaults |
| `tab_ziel.py` | Tab „Ziel" (NAS-Host/User/Key, Verbindungstest, SSH-Hilfe) |
| `tab_quellen.py` | Tab „Quellen" (zu sichernde Verzeichnisse, Excludes) |
| `tab_zeitplan.py` | Tab „Zeitplan" (OnCalendar für den systemd-Timer) |
| `tab_aufbewahrung.py` | Tab „Aufbewahrung" (max. Snapshots, dpkg, Größenkalkulation) |
| `tab_testlauf.py` | Tab „Testlauf" (Live-Ausführung mit `NAS_BACKUP_LIVE_LOG=1`) |
| `generators.py` | `GeneratorMixin`: erzeugt alle Skript-Dateien als Strings |
| `settings.py` | Persistenz der GUI-Eingaben (`~/.config/nas-backup-generator/settings.json`) |
| `widgets.py`, `dialogs.py`, `constants.py` | UI-Bausteine, Dialoge, Theme-Konstanten |

## Starten

```bash
python3 nas_backup_generator.py        # erfordert grafische Umgebung (X11/Wayland)
```

## Syntax-Check / Linting

```bash
python3 -m py_compile <datei.py>
python3 -m pyflakes <datei.py>
```

## Generierte Backups – Voraussetzungen

- Quell-System mit `bash`, `rsync`, `openssh-client`, systemd (Debian/Ubuntu für `dpkg`)
- Ein NAS mit SSH-Zugang; der gewählte SSH-Key muss dort autorisiert sein
- NAS-Volume sollte **Btrfs oder ext4** sein, damit Hardlinks (`--link-dest`) greifen

### Wichtig: rsync läuft auf dem NAS oft als non-root

Viele NAS-Systeme erzwingen Owner/Rechte (z. B. alles als der Login-Benutzer mit
`777`). Damit `--link-dest` trotzdem Hardlinks erzeugt (statt bei jedem Lauf ein
Vollbackup), nutzen die generierten Skripte:

- `--rsync-path="rsync --fake-super"` – speichert Owner/Group/Perms in xattrs
  (setzt user-xattr-fähiges Dateisystem voraus, z. B. Btrfs/ext4)
- `--numeric-ids` – numerische uid/gid statt Namensmapping
- `--no-specials --no-devices` – Sockets/FIFOs/Geräte überspringen (auf ihnen
  lassen sich keine xattrs setzen → sonst rsync-Exit-Code 23)

## NAS-Verzeichnisstruktur (Beispiel)

```
<NAS-Basis-Pfad>/
├── 2025-04-01/
│   ├── home/
│   ├── etc/
│   └── packages.txt
├── 2025-04-02/
│   └── ...
└── latest -> 2025-04-02   (Symlink)
```

## Dry-Run

`--dry-run` zu den rsync-Aufrufen im generierten Skript hinzufügen, um ohne
tatsächliche Übertragung zu testen.
