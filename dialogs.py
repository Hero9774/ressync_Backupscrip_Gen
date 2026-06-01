import os
import subprocess


class DialogMixin:
    """Zenity-/kdialog-Dialoge und native Datei-/Ordner-Auswahl."""

    @staticmethod
    def _zdlg(kind: str, title: str, text: str) -> bool:
        """kind = info|error|warning|question. Gibt True zurück wenn OK/Ja."""
        try:
            r = subprocess.run(
                ["zenity", f"--{kind}", f"--title={title}",
                 f"--text={text}", "--width=420"],
                capture_output=True)
            return r.returncode == 0
        except FileNotFoundError:
            pass
        from tkinter import messagebox as _mb
        if kind == "error":
            _mb.showerror(title, text)
        elif kind == "warning":
            _mb.showwarning(title, text)
        elif kind == "question":
            return _mb.askyesno(title, text)
        else:
            _mb.showinfo(title, text)
        return True

    @staticmethod
    def _native_open_file(title: str, initialdir: str, filters: str) -> str:
        for cmd in (
            ["kdialog", "--title", title, "--getopenfilename", initialdir, filters],
            ["zenity", "--file-selection", f"--title={title}",
             f"--filename={initialdir}/", "--file-filter=" + filters],
        ):
            try:
                r = subprocess.run(cmd, capture_output=True, text=True)
                if r.returncode == 0:
                    return r.stdout.strip()
            except FileNotFoundError:
                continue
        return ""

    @staticmethod
    def _native_select_dir(title: str, initialdir: str = "") -> str:
        start = initialdir or os.path.expanduser("~")
        for cmd in (
            ["kdialog", "--title", title, "--getexistingdirectory", start],
            ["zenity", "--file-selection", "--directory",
             f"--title={title}", f"--filename={start}/"],
        ):
            try:
                r = subprocess.run(cmd, capture_output=True, text=True)
                if r.returncode == 0:
                    return r.stdout.strip()
            except FileNotFoundError:
                continue
        return ""
