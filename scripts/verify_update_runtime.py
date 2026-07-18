from __future__ import annotations

import sys
import tempfile
import zipfile
from collections.abc import Callable
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from freefire_kill_sender import (
    APP_EXE_NAME,
    is_newer_version,
    resolve_downloaded_exe,
    update_asset_from_manifest,
    version_tuple,
)


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def expect_error(callback: Callable[[], object], message: str) -> None:
    try:
        callback()
    except Exception:
        return
    raise AssertionError(message)


def verify_manifest_validation() -> None:
    asset = update_asset_from_manifest(
        {
            "version": "2.6.267",
            "windows": {
                "portable_url": "https://example.com/AizenStreamControl.exe",
                "sha256": "a" * 64,
            },
        }
    )
    check(asset["version"] == "2.6.267", "manifesto deve preservar versao")
    check(asset["url"].startswith("https://"), "manifesto deve preservar URL HTTPS")
    check(asset["sha256"] == "a" * 64, "manifesto deve preservar SHA256")
    expect_error(
        lambda: update_asset_from_manifest({"version": "2.6.267", "windows": {"portable_url": "ftp://example.com/app.exe"}}),
        "manifesto deve rejeitar URL nao HTTP",
    )
    expect_error(
        lambda: update_asset_from_manifest({"version": "2.6.267", "windows": {"portable_url": "https://example.com/app.exe", "sha256": "abc"}}),
        "manifesto deve rejeitar SHA invalido",
    )


def verify_version_comparison() -> None:
    check(version_tuple("v2.6.267") == (2, 6, 267), "versao com prefixo v deve ser lida")
    check(is_newer_version("2.6.10", "2.6.9"), "2.6.10 deve ser maior que 2.6.9")
    check(not is_newer_version("2.6.9", "2.6.10"), "2.6.9 nao deve ser maior que 2.6.10")


def verify_zip_resolution() -> None:
    with tempfile.TemporaryDirectory(prefix="aizen_update_verify_") as tmp:
        base = Path(tmp)
        safe_zip = base / "safe.zip"
        with zipfile.ZipFile(safe_zip, "w") as archive:
            archive.writestr(f"release/{APP_EXE_NAME}", b"MZ")
        resolved = resolve_downloaded_exe(safe_zip)
        check(resolved.name == APP_EXE_NAME and resolved.exists(), "ZIP seguro deve extrair executavel esperado")

    with tempfile.TemporaryDirectory(prefix="aizen_update_verify_") as tmp:
        bad_zip = Path(tmp) / "bad.zip"
        with zipfile.ZipFile(bad_zip, "w") as archive:
            archive.writestr("../evil.exe", b"MZ")
        expect_error(lambda: resolve_downloaded_exe(bad_zip), "ZIP com caminho ../ deve ser bloqueado")


def main() -> int:
    verify_manifest_validation()
    verify_version_comparison()
    verify_zip_resolution()
    print("Runtime update OK: manifesto, versoes e ZIP de atualizacao validados.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
