from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import tkinter as tk
from tkinter import messagebox


APP_NAME = "Aizen Stream Control"
APP_EXE_NAME = "AizenStreamControl.exe"
PUBLISHER = "Aizen"
BUNDLE_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
SOURCE_EXE = BUNDLE_DIR / APP_EXE_NAME
SOURCE_LOGO = BUNDLE_DIR / "assets" / "app_logo.png"
INSTALL_DIR = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "Programs" / APP_NAME
TARGET_EXE = INSTALL_DIR / APP_EXE_NAME
START_MENU_DIR = Path(os.environ.get("APPDATA", str(Path.home()))) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / APP_NAME
DESKTOP_DIR = Path(os.environ.get("USERPROFILE", str(Path.home()))) / "Desktop"


def ps_quote(value: Path | str) -> str:
    text = str(value)
    return "'" + text.replace("'", "''") + "'"


def create_shortcut(shortcut_path: Path, target_path: Path, working_dir: Path, description: str) -> None:
    shortcut_path.parent.mkdir(parents=True, exist_ok=True)
    script = "; ".join(
        [
            "$shell = New-Object -ComObject WScript.Shell",
            f"$shortcut = $shell.CreateShortcut({ps_quote(shortcut_path)})",
            f"$shortcut.TargetPath = {ps_quote(target_path)}",
            f"$shortcut.WorkingDirectory = {ps_quote(working_dir)}",
            f"$shortcut.IconLocation = {ps_quote(str(target_path) + ',0')}",
            f"$shortcut.Description = {ps_quote(description)}",
            "$shortcut.Save()",
        ]
    )
    subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
        check=True,
        creationflags=0x08000000,
    )


def stop_running_app() -> None:
    subprocess.run(
        ["taskkill", "/IM", APP_EXE_NAME, "/F"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
        creationflags=0x08000000,
    )
    time.sleep(0.8)


def copy_app_executable() -> None:
    last_error: Exception | None = None
    for _attempt in range(6):
        try:
            shutil.copy2(SOURCE_EXE, TARGET_EXE)
            return
        except PermissionError as exc:
            last_error = exc
            stop_running_app()
            time.sleep(0.5)
    if last_error is not None:
        raise RuntimeError(
            "Nao foi possivel substituir o executavel instalado. Feche o Aizen Stream Control e tente novamente."
        ) from last_error


def write_uninstaller() -> None:
    uninstall_path = INSTALL_DIR / "Desinstalar Aizen Stream Control.cmd"
    desktop_shortcut = DESKTOP_DIR / f"{APP_NAME}.lnk"
    start_shortcut = START_MENU_DIR / f"{APP_NAME}.lnk"
    uninstall_shortcut = START_MENU_DIR / "Desinstalar.lnk"
    script = "\n".join(
        [
            "@echo off",
            "setlocal",
            f'taskkill /IM "{APP_EXE_NAME}" /F >nul 2>nul',
            "timeout /t 1 /nobreak >nul",
            f'del /F /Q "{desktop_shortcut}" >nul 2>nul',
            f'del /F /Q "{start_shortcut}" >nul 2>nul',
            f'del /F /Q "{uninstall_shortcut}" >nul 2>nul',
            f'rmdir /S /Q "{START_MENU_DIR}" >nul 2>nul',
            f'cd /d "{Path(os.environ.get("TEMP", str(Path.home())))}"',
            f'rmdir /S /Q "{INSTALL_DIR}" >nul 2>nul',
            "echo Aizen Stream Control removido.",
            "timeout /t 2 /nobreak >nul",
            "",
        ]
    )
    uninstall_path.write_text(script, encoding="utf-8")
    create_shortcut(uninstall_shortcut, uninstall_path, INSTALL_DIR, f"Desinstalar {APP_NAME}")


def install(create_desktop_shortcut: bool = True, launch_after: bool = True) -> None:
    if not SOURCE_EXE.exists():
        raise FileNotFoundError(f"Executavel do app nao encontrado no instalador: {SOURCE_EXE}")

    stop_running_app()
    INSTALL_DIR.mkdir(parents=True, exist_ok=True)
    START_MENU_DIR.mkdir(parents=True, exist_ok=True)
    copy_app_executable()

    create_shortcut(START_MENU_DIR / f"{APP_NAME}.lnk", TARGET_EXE, INSTALL_DIR, APP_NAME)
    if create_desktop_shortcut:
        create_shortcut(DESKTOP_DIR / f"{APP_NAME}.lnk", TARGET_EXE, INSTALL_DIR, APP_NAME)
    write_uninstaller()

    if launch_after:
        subprocess.Popen([str(TARGET_EXE)], cwd=str(INSTALL_DIR), creationflags=0x08000000)


def run_ui() -> int:
    root = tk.Tk()
    root.title(f"Instalar {APP_NAME}")
    root.geometry("620x440")
    root.minsize(560, 400)
    root.configure(bg="#050506")
    try:
        root.iconbitmap(str(BUNDLE_DIR / "assets" / "app_icon.ico"))
    except tk.TclError:
        pass

    create_desktop_var = tk.BooleanVar(value=True)
    launch_var = tk.BooleanVar(value=True)
    status_var = tk.StringVar(value=f"Destino: {INSTALL_DIR}")

    shell = tk.Frame(root, bg="#050506")
    shell.pack(fill=tk.BOTH, expand=True, padx=24, pady=24)

    header = tk.Frame(shell, bg="#050506")
    header.pack(fill=tk.X)
    logo_loaded = False
    if SOURCE_LOGO.exists():
        try:
            logo = tk.PhotoImage(file=str(SOURCE_LOGO))
            logo = logo.subsample(max(1, logo.width() // 82), max(1, logo.height() // 82))
            logo_label = tk.Label(header, image=logo, bg="#120809", bd=0)
            logo_label.image = logo
            logo_label.pack(side=tk.LEFT, padx=(0, 18))
            logo_loaded = True
        except tk.TclError:
            logo_loaded = False
    if not logo_loaded:
        tk.Label(header, text="A", fg="#ff1717", bg="#120809", font=("Segoe UI Semibold", 34), width=3).pack(
            side=tk.LEFT, padx=(0, 18)
        )

    title_box = tk.Frame(header, bg="#050506")
    title_box.pack(side=tk.LEFT, fill=tk.X, expand=True)
    tk.Label(
        title_box,
        text=APP_NAME,
        fg="#f8f2f1",
        bg="#050506",
        font=("Segoe UI Semibold", 24),
    ).pack(anchor="w")
    tk.Label(
        title_box,
        text="Instalador profissional para o painel de lives",
        fg="#b8a6a5",
        bg="#050506",
        font=("Segoe UI", 11),
    ).pack(anchor="w", pady=(4, 0))

    card = tk.Frame(shell, bg="#111116", highlightbackground="#3a1518", highlightthickness=1)
    card.pack(fill=tk.BOTH, expand=True, pady=(24, 0))
    tk.Label(
        card,
        text="Instalacao por usuario",
        fg="#f8f2f1",
        bg="#111116",
        font=("Segoe UI Semibold", 15),
    ).pack(anchor="w", padx=20, pady=(20, 4))
    tk.Label(
        card,
        text="O app sera instalado sem pedir administrador e podera se atualizar automaticamente ao abrir.",
        fg="#b8a6a5",
        bg="#111116",
        font=("Segoe UI", 10),
        wraplength=520,
        justify="left",
    ).pack(anchor="w", padx=20, pady=(0, 16))

    for text, variable in (
        ("Criar atalho na Area de Trabalho", create_desktop_var),
        ("Abrir o programa depois de instalar", launch_var),
    ):
        tk.Checkbutton(
            card,
            text=text,
            variable=variable,
            fg="#f8f2f1",
            bg="#111116",
            activeforeground="#f8f2f1",
            activebackground="#111116",
            selectcolor="#210f12",
            font=("Segoe UI", 10),
        ).pack(anchor="w", padx=20, pady=4)

    tk.Label(
        card,
        textvariable=status_var,
        fg="#ff4d4d",
        bg="#111116",
        font=("Segoe UI", 9),
        wraplength=520,
        justify="left",
    ).pack(anchor="w", padx=20, pady=(16, 0))

    actions = tk.Frame(card, bg="#111116")
    actions.pack(side=tk.BOTTOM, fill=tk.X, padx=20, pady=20)

    def on_install() -> None:
        try:
            status_var.set("Instalando...")
            root.update_idletasks()
            install(create_desktop_var.get(), launch_var.get())
            messagebox.showinfo(APP_NAME, "Instalacao concluida.")
            root.destroy()
        except Exception as exc:
            status_var.set(f"Erro: {exc}")
            messagebox.showerror(APP_NAME, str(exc))

    tk.Button(
        actions,
        text="Instalar",
        command=on_install,
        bg="#ff1717",
        fg="#fff7f7",
        activebackground="#ff3b32",
        activeforeground="#fff7f7",
        relief=tk.FLAT,
        font=("Segoe UI Semibold", 11),
        padx=24,
        pady=8,
    ).pack(side=tk.LEFT)
    tk.Button(
        actions,
        text="Cancelar",
        command=root.destroy,
        bg="#21191d",
        fg="#f8f2f1",
        activebackground="#2f2025",
        activeforeground="#f8f2f1",
        relief=tk.FLAT,
        font=("Segoe UI Semibold", 11),
        padx=20,
        pady=8,
    ).pack(side=tk.LEFT, padx=(10, 0))

    root.mainloop()
    return 0


def main() -> int:
    if "--silent" in sys.argv:
        install(create_desktop_shortcut=True, launch_after=False)
        return 0
    return run_ui()


if __name__ == "__main__":
    raise SystemExit(main())
