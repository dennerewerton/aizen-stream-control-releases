from __future__ import annotations

import os
import sys
import tempfile
import time
import zipfile
from collections.abc import Callable
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import freefire_kill_sender as app_runtime

from freefire_kill_sender import (
    APP_EXE_NAME,
    cleanup_stale_update_dirs,
    create_update_download_dir,
    is_newer_version,
    resolve_downloaded_exe,
    safe_extract_update_zip,
    update_asset_from_manifest,
    update_workspace_fallback_dir,
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

    with tempfile.TemporaryDirectory(prefix="aizen_update_verify_") as tmp:
        base = Path(tmp)
        large_zip = base / "large.zip"
        with zipfile.ZipFile(large_zip, "w") as archive:
            archive.writestr("release/AizenStreamControl.exe", b"MZ")
            archive.writestr("release/payload.bin", b"12345")
        previous_limit = app_runtime.UPDATE_MAX_EXTRACTED_BYTES
        app_runtime.UPDATE_MAX_EXTRACTED_BYTES = 4
        try:
            expect_error(
                lambda: safe_extract_update_zip(large_zip, base / "too_large"),
                "ZIP com tamanho extraido acima do limite deve ser bloqueado",
            )
        finally:
            app_runtime.UPDATE_MAX_EXTRACTED_BYTES = previous_limit


def verify_build_scripts_include_runtime_assets() -> None:
    build_exe = (ROOT / "build_exe.ps1").read_text(encoding="utf-8-sig")
    build_manifest = (ROOT / "build_update_manifest.ps1").read_text(encoding="utf-8-sig")
    check(
        "scripts/windows_ocr.ps1;scripts" in build_exe.replace("\\", "/"),
        "build_exe.ps1 deve empacotar scripts/windows_ocr.ps1 para OCR no executavel",
    )
    check(
        "scripts\\windows_ocr.ps1" in build_manifest or "scripts/windows_ocr.ps1" in build_manifest,
        "build_update_manifest.ps1 deve reconstruir quando o OCR auxiliar mudar",
    )


def verify_stale_update_cleanup() -> None:
    with tempfile.TemporaryDirectory(prefix="aizen_update_cleanup_") as tmp:
        base = Path(tmp)
        old_update = base / "aizen_update_1000_deadbeef"
        fresh_update = base / "aizen_update_1001_cafebabe"
        similar_name = base / "aizen_update_manual"
        for path in (old_update, fresh_update, similar_name):
            path.mkdir()
        old_time = time.time() - (48 * 60 * 60)
        os.utime(old_update, (old_time, old_time))
        os.utime(similar_name, (old_time, old_time))
        removed = cleanup_stale_update_dirs(base, min_age_seconds=24 * 60 * 60, max_dirs=4)
        check(removed == 1, "limpeza de updates deveria remover somente uma pasta antiga valida")
        check(not old_update.exists(), "limpeza de updates nao removeu pasta antiga valida")
        check(fresh_update.exists(), "limpeza de updates removeu pasta recente")
        check(similar_name.exists(), "limpeza de updates removeu pasta com nome fora do padrao")


def verify_default_update_cleanup_includes_fallback() -> None:
    original_app_dir = app_runtime.APP_DIR
    original_tempdir = tempfile.tempdir
    try:
        with tempfile.TemporaryDirectory(prefix="aizen_update_cleanup_default_") as tmp:
            root = Path(tmp)
            app_runtime.APP_DIR = root / "appdata"
            tempfile.tempdir = str(root / "temp")
            default_update = app_runtime.APP_DIR / "updates" / "aizen_update_1000_deadbeef"
            fallback_update = update_workspace_fallback_dir() / "aizen_update_1001_cafebabe"
            recent_fallback = update_workspace_fallback_dir() / "aizen_update_1002_faded123"
            for path in (default_update, fallback_update, recent_fallback):
                path.mkdir(parents=True)
            old_time = time.time() - (48 * 60 * 60)
            os.utime(default_update, (old_time, old_time))
            os.utime(fallback_update, (old_time, old_time))
            removed = cleanup_stale_update_dirs(min_age_seconds=24 * 60 * 60, max_dirs=4)
            check(removed == 2, "limpeza padrao deveria remover updates antigos do padrao e fallback")
            check(not default_update.exists(), "limpeza padrao nao removeu update antigo do AppData")
            check(not fallback_update.exists(), "limpeza padrao nao removeu update antigo do fallback temporario")
            check(recent_fallback.exists(), "limpeza padrao removeu update recente do fallback")
    finally:
        app_runtime.APP_DIR = original_app_dir
        tempfile.tempdir = original_tempdir


def verify_update_download_dir_fallback() -> None:
    original_update_workspace_dir = app_runtime.update_workspace_dir
    original_write_update_log = app_runtime.write_update_log
    original_tempdir = tempfile.tempdir

    def broken_workspace() -> Path:
        raise OSError("sem permissao")

    with tempfile.TemporaryDirectory(prefix="aizen_update_fallback_") as tmp:
        app_runtime.update_workspace_dir = broken_workspace
        app_runtime.write_update_log = lambda _message: None
        tempfile.tempdir = tmp
        try:
            target = create_update_download_dir()
        finally:
            app_runtime.update_workspace_dir = original_update_workspace_dir
            app_runtime.write_update_log = original_write_update_log
            tempfile.tempdir = original_tempdir
        expected_parent = Path(tmp) / app_runtime.APP_NAME / "updates"
        check(target.exists() and target.is_dir(), "fallback temporario do update nao criou pasta")
        check(target.parent == expected_parent, "fallback temporario do update usou pasta inesperada")


def main() -> int:
    verify_manifest_validation()
    verify_version_comparison()
    verify_zip_resolution()
    verify_build_scripts_include_runtime_assets()
    verify_stale_update_cleanup()
    verify_default_update_cleanup_includes_fallback()
    verify_update_download_dir_fallback()
    print("Runtime update OK: manifesto, versoes e ZIP de atualizacao validados.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
