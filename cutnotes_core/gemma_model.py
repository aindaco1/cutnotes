"""Pinned, resumable installation of the on-device formatter. No inference uploads."""
from __future__ import annotations

from contextlib import contextmanager
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import shutil
import ssl
import subprocess
import urllib.request

from .contracts import CutNotesError, EXIT_DEPENDENCY, ProgressReporter
from .filesystem import write_json

MANIFEST = json.loads((Path(__file__).parent / "data/gemma-model.json").read_text())
RECEIPT = ".cutnotes-verified.json"


def model_directory() -> Path:
    return Path(os.environ.get("CUTNOTES_GEMMA_MODEL", str(Path.home() / "Library/Application Support/CutNotes/Models" / MANIFEST["id"]))).expanduser()


def failure(message, code="gemma_model_invalid"):
    return CutNotesError(message, EXIT_DEPENDENCY, code=code,
        recovery="Open CutNotes setup to download Gemma, or run `cutnotes model download --kind formatting --accept-license`.")


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def safe_path(root, name):
    path = root / name
    if root.is_symlink() or path.is_symlink() or path.parent != root:
        raise failure("The model folder must contain ordinary files, not symbolic links.")
    return path


def fingerprint(root):
    return {item["name"]: [p.stat().st_size, p.stat().st_mtime_ns, p.stat().st_ino]
            for item in MANIFEST["files"] for p in [safe_path(root, item["name"]) ]}


def validate_model(root=None, *, full=True):
    root = root or model_directory()
    if not root.is_dir():
        raise failure("Download the Gemma formatting model to continue.", "gemma_model_missing")
    try:
        current = fingerprint(root)
        if not full:
            receipt_path = safe_path(root, RECEIPT)
            receipt = json.loads(receipt_path.read_text())
            if receipt == {"revision": MANIFEST["revision"], "files": current}:
                return root
        for item in MANIFEST["files"]:
            path = safe_path(root, item["name"])
            if not path.is_file() or path.stat().st_size != item["bytes"] or digest(path) != item["sha256"]:
                raise failure("The Gemma model failed verification: " + item["name"])
    except (OSError, ValueError) as error:
        if not full:
            return validate_model(root, full=True)
        raise failure("The Gemma model is incomplete or unreadable.") from error
    write_json(root / RECEIPT, {"revision": MANIFEST["revision"], "files": current})
    return root


def runtime_issue():
    if platform.system() != "Darwin" or platform.machine() != "arm64":
        return "Gemma requires a Mac with Apple silicon."
    memory = int(subprocess.check_output(["/usr/sbin/sysctl", "-n", "hw.memsize"], text=True).strip())
    if memory < MANIFEST["minimum_memory_bytes"]:
        return "Gemma requires at least 16 GB of unified memory; 24 GB or more is recommended."
    if any(importlib.util.find_spec(name) is None for name in ("mlx", "mlx_lm", "transformers")):
        return "The Gemma runtime is missing. Install the current CutNotes app."
    return None


def require_ready():
    issue = runtime_issue()
    if issue:
        raise failure(issue, "gemma_runtime_unavailable")
    return validate_model()


def model_status():
    root = model_directory()
    state, detail = "missing", "Download Gemma once to format notes on this Mac."
    try:
        validate_model(root, full=False)
        state, detail = "ready", "Gemma is installed. Formatting stays on this Mac."
    except CutNotesError as error:
        if root.exists():
            state, detail = "invalid", str(error)
    staging = root.with_name("." + root.name + ".download")
    downloaded = sum(min(p.stat().st_size, item["bytes"]) for item in MANIFEST["files"]
                     for p in [staging / item["name"]] if p.is_file() and not p.is_symlink()) if not staging.is_symlink() else 0
    if state == "missing" and downloaded:
        state, detail = "partial", "The download is paused. Resume to finish setup."
    issue = runtime_issue()
    if issue:
        state, detail = "unavailable", issue
    return {"id": MANIFEST["id"], "state": state, "detail": detail, "path": str(root),
            "bytes": MANIFEST["bytes"], "source": MANIFEST["repo"], "revision": MANIFEST["revision"],
            "license": MANIFEST["license"], "license_url": MANIFEST["license_url"],
            "downloaded_bytes": downloaded, "minimum_memory_bytes": MANIFEST["minimum_memory_bytes"]}


@contextmanager
def installation():
    root = model_directory()
    root.parent.mkdir(parents=True, exist_ok=True)
    lock_path = root.with_name("." + root.name + ".lock")
    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise failure("Another Gemma installation is running.", "gemma_model_busy") from error
        staging = root.with_name("." + root.name + ".download")
        if staging.is_symlink() or root.is_symlink():
            raise failure("The Gemma model directory cannot be a symbolic link.")
        staging.mkdir(mode=0o700, exist_ok=True)
        yield root, staging


def install_staging(root, staging):
    validate_model(staging)
    backup = root.with_name("." + root.name + ".previous")
    if backup.exists():
        raise failure("A previous model installation needs recovery before installing again.")
    if root.exists():
        root.rename(backup)
    try:
        staging.rename(root)
    except BaseException:
        if backup.exists():
            backup.rename(root)
        raise
    if backup.exists():
        shutil.rmtree(backup)


def download_model(*, accept_license, reporter=None):
    if not accept_license:
        raise failure("Review the Gemma Apache 2.0 license and accept it to download.", "model_license_required")
    reporter = reporter or ProgressReporter(None)
    if model_directory().is_dir():
        try:
            validate_model()
            return model_status()
        except CutNotesError:
            pass
    try:
        with installation() as (root, staging):
            remaining = sum(max(0, item["bytes"] - (p.stat().st_size if p.is_file() else 0))
                            for item in MANIFEST["files"] for p in [safe_path(staging, item["name"])])
            if shutil.disk_usage(staging).free < remaining + 1_000_000_000:
                raise failure("Not enough free disk space for Gemma. Free at least 11 GB and try again.", "model_disk_space")
            completed = 0
            try:
                import certifi
                context = ssl.create_default_context(cafile=certifi.where())
            except ImportError:
                context = ssl.create_default_context()
            for item in MANIFEST["files"]:
                path = safe_path(staging, item["name"])
                offset = path.stat().st_size if path.exists() else 0
                if offset == item["bytes"] and digest(path) == item["sha256"]:
                    completed += offset
                    continue
                if offset >= item["bytes"]:
                    path.unlink()
                    offset = 0
                url = f'https://huggingface.co/{MANIFEST["repo"]}/resolve/{MANIFEST["revision"]}/{item["name"]}'
                request = urllib.request.Request(url, headers={"Range": f"bytes={offset}-", "User-Agent": "CutNotes-Model-Setup"})
                reporter.stage("model_download", "Downloading Gemma — progress is saved if interrupted")
                with urllib.request.urlopen(request, timeout=60, context=context) as response:
                    if response.status == 206:
                        expected = f'bytes {offset}-{item["bytes"] - 1}/{item["bytes"]}'
                        if response.headers.get("Content-Range") != expected:
                            raise failure("The download server returned an invalid byte range.")
                    elif response.status == 200:
                        offset = 0
                    else:
                        raise failure("The model download server returned an unexpected response.")
                    with path.open("ab" if offset else "wb") as output:
                        while chunk := response.read(4 * 1024 * 1024):
                            if offset + len(chunk) > item["bytes"]:
                                raise failure("The model download exceeded its expected size.")
                            output.write(chunk)
                            offset += len(chunk)
                            reporter.progress("model_download", (completed + offset) / MANIFEST["bytes"],
                                              f"Gemma: {(completed + offset)/1e9:.2f} of {MANIFEST['bytes']/1e9:.2f} GB")
                reporter.stage("model_verification", "Verifying the downloaded model")
                if offset != item["bytes"] or digest(path) != item["sha256"]:
                    if offset == item["bytes"]:
                        path.unlink()
                    raise failure("The model download failed verification. Resume the download to retry.")
                completed += offset
            install_staging(root, staging)
    except (OSError, ValueError) as error:
        raise failure("The Gemma download was interrupted. Resume setup to continue.", "model_download_failed") from error
    return model_status()


def import_model(source, reporter=None):
    source = source.expanduser()
    # Validate without modifying a user-supplied folder.
    for item in MANIFEST["files"]:
        path = safe_path(source, item["name"])
        if not path.is_file() or path.stat().st_size != item["bytes"] or digest(path) != item["sha256"]:
            raise failure("The selected folder does not contain the pinned Gemma model.")
    with installation() as (root, staging):
        if shutil.disk_usage(staging).free < MANIFEST["bytes"] + 1_000_000_000:
            raise failure("Free at least 11 GB before importing Gemma.", "model_disk_space")
        for item in MANIFEST["files"]:
            shutil.copyfile(safe_path(source, item["name"]), safe_path(staging, item["name"]))
        install_staging(root, staging)
    return model_status()
