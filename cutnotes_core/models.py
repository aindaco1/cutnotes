"""Pinned, hash-verified local Parakeet v3 model management."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import shutil
import tempfile
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import uuid

from .contracts import CutNotesError, EXIT_DEPENDENCY, ProgressReporter


MODEL_ID = "parakeet-tdt-0.6b-v3"
MODEL_REPOSITORY = "FluidInference/parakeet-tdt-0.6b-v3-coreml"
MODEL_REVISION = "aed02740059203c4a87495924f685de3722ae9ce"
MODEL_LICENSE = "CC-BY-4.0"
MODEL_LICENSE_URL = "https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3"
MODEL_NOTICE_NAME = "CUTNOTES_MODEL_LICENSE.txt"


@dataclass(frozen=True)
class ModelFile:
    path: str
    size: int
    sha256: str


MODEL_FILES = (
    ModelFile("Preprocessor.mlmodelc/coremldata.bin", 486, "dbde3f2300842c1fd51ef3ff948a0bcffe65ffd2dca10707f2509f32c1d65b1d"),
    ModelFile("Preprocessor.mlmodelc/metadata.json", 2_841, "2a98699e22d279dd37fa1d238aeb1c6db1df0d6fad687775324157689d8f3acf"),
    ModelFile("Preprocessor.mlmodelc/model.mil", 28_181, "4b8518a956450fec57f06c2a21bdffc26973f7f1fa6842fb38fe917f896b6b93"),
    ModelFile("Preprocessor.mlmodelc/weights/weight.bin", 491_072, "129b76e3aeafa8afa3ea76d995b964b145fe83700d579f6ff42c4c38fa0968ea"),
    ModelFile("Encoder.mlmodelc/coremldata.bin", 485, "d48034a167a82e88fc3df64f60af963ab3983538271175b8319e7d5720a0fb86"),
    ModelFile("Encoder.mlmodelc/metadata.json", 2_921, "da24da9cca943fb29d7fa8e376d57fca7cb3aa08ca51b956b0b0e56813f087e9"),
    ModelFile("Encoder.mlmodelc/model.mil", 959_769, "ed7b19156ca29fa7dfd6891deb9fda4b0e8893f68597c985d135736546a43808"),
    ModelFile("Encoder.mlmodelc/weights/weight.bin", 445_187_200, "e2020f323703477a5b21d7c2d282c403e371afb5962e79877e3033e73ba6f421"),
    ModelFile("Decoder.mlmodelc/coremldata.bin", 554, "18647af085d87bd8f3121c8a9b4d4564c1ede038dab63d295b4e745cf2d7fb99"),
    ModelFile("Decoder.mlmodelc/metadata.json", 3_427, "a39e93cd8371b8ded92635c7804fcd0590f0d1dd9415c6d19a0484be073077d9"),
    ModelFile("Decoder.mlmodelc/model.mil", 13_110, "ef2a0a281695398a62fde86ac269c68f73d5b578d7ed3b31f2ba91a2d1ea1f35"),
    ModelFile("Decoder.mlmodelc/weights/weight.bin", 23_604_992, "48adf0f0d47c406c8253d4f7fef967436a39da14f5a65e66d5a4b407be355d41"),
    ModelFile("JointDecisionv3.mlmodelc/coremldata.bin", 521, "f5fc08b741400f0088492c9e839418b1e18522f19cba28d361dd030c5f398342"),
    ModelFile("JointDecisionv3.mlmodelc/metadata.json", 3_453, "d9307211b9a37e0f0ac260c7660b1571a3de25841035cfdf9b58fd40425f890f"),
    ModelFile("JointDecisionv3.mlmodelc/model.mil", 11_775, "be60732943389a047175111a83f8839f3eb39d4803adafa828a0871b2f39818d"),
    ModelFile("JointDecisionv3.mlmodelc/weights/weight.bin", 12_642_764, "4e0e63d840032f7f07ddb1d64446051166281e5491bf22da8a945c41f6eedb3e"),
    ModelFile("parakeet_vocab.json", 151_122, "7ec60e05f1b24480736ec0eed40900f4626bce1fa9a60fd700ec7e2a59198735"),
)
MODEL_BYTES = sum(file.size for file in MODEL_FILES)


def default_model_directory() -> Path:
    override = os.environ.get("CUTNOTES_PARAKEET_MODEL")
    if override:
        return Path(override).expanduser().resolve()
    return (
        Path.home()
        / "Library"
        / "Application Support"
        / "CutNotes"
        / "Models"
        / MODEL_ID
    )


def _safe_file(root: Path, relative: str) -> Path:
    candidate = root / relative
    if candidate.is_symlink():
        raise CutNotesError(
            f"The model contains an unsafe symbolic link: {relative}",
            EXIT_DEPENDENCY,
            code="model_unsafe_file",
            recovery="Remove the model and download or import it again.",
        )
    try:
        candidate.resolve().relative_to(root.resolve())
    except ValueError as error:
        raise CutNotesError(
            f"The model file escapes its model directory: {relative}",
            EXIT_DEPENDENCY,
            code="model_unsafe_file",
            recovery="Choose an unmodified Parakeet v3 model folder.",
        ) from error
    return candidate


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1_048_576):
            digest.update(chunk)
    return digest.hexdigest()


def _write_model_notice(root: Path) -> None:
    notice = f"""NVIDIA Parakeet-TDT-0.6B-v3

Original model: {MODEL_LICENSE_URL}
CutNotes Core ML source: https://huggingface.co/{MODEL_REPOSITORY}
Pinned revision: {MODEL_REVISION}
License: Creative Commons Attribution 4.0 International
License text: https://creativecommons.org/licenses/by/4.0/legalcode

CutNotes downloads this model only after explicit license acceptance. Model
weights remain on this Mac and are used for local transcription.
"""
    (root / MODEL_NOTICE_NAME).write_text(notice, encoding="utf-8")


def validate_model(root: Path) -> None:
    for spec in MODEL_FILES:
        candidate = _safe_file(root, spec.path)
        if not candidate.is_file():
            raise CutNotesError(
                f"The Parakeet model is incomplete; {spec.path} is missing.",
                EXIT_DEPENDENCY,
                code="model_incomplete",
                recovery="Download or import the pinned Parakeet v3 model again.",
            )
        actual_size = candidate.stat().st_size
        if actual_size != spec.size:
            raise CutNotesError(
                f"The Parakeet model file {spec.path} has an unexpected size.",
                EXIT_DEPENDENCY,
                code="model_size_mismatch",
                recovery="Download or import the pinned Parakeet v3 model again.",
            )
        if _sha256(candidate) != spec.sha256:
            raise CutNotesError(
                f"The Parakeet model file {spec.path} failed SHA-256 verification.",
                EXIT_DEPENDENCY,
                code="model_checksum_mismatch",
                recovery="Delete the untrusted copy and download or import it again.",
            )


def model_status(root: Path | None = None) -> dict:
    directory = (root or default_model_directory()).expanduser().resolve()
    try:
        validate_model(directory)
        state = "ready"
        detail = None
    except CutNotesError as error:
        state = "missing" if not directory.exists() else "invalid"
        detail = str(error)
    return {
        "id": MODEL_ID,
        "state": state,
        "detail": detail,
        "path": str(directory),
        "bytes": MODEL_BYTES,
        "source": MODEL_REPOSITORY,
        "revision": MODEL_REVISION,
        "license": MODEL_LICENSE,
        "license_url": MODEL_LICENSE_URL,
    }


def _install_staging(staging: Path, destination: Path) -> None:
    validate_model(staging)
    destination.parent.mkdir(parents=True, exist_ok=True)
    backup = destination.parent / f".{destination.name}-backup-{uuid.uuid4().hex}"
    had_destination = destination.exists()
    if had_destination:
        destination.replace(backup)
    try:
        staging.replace(destination)
    except Exception:
        if had_destination and not destination.exists():
            backup.replace(destination)
        raise
    if backup.exists():
        shutil.rmtree(backup)


def import_model(source: Path, destination: Path | None = None) -> dict:
    selected = source.expanduser().resolve()
    candidates = (selected, selected / MODEL_ID, selected / "parakeet-tdt-0.6b-v3")
    model_root = next(
        (candidate for candidate in candidates if (candidate / MODEL_FILES[0].path).is_file()),
        None,
    )
    if model_root is None:
        raise CutNotesError(
            "The selected folder does not contain the pinned Parakeet v3 model.",
            EXIT_INPUT,
            code="model_not_found",
            recovery="Choose the folder containing Encoder.mlmodelc and parakeet_vocab.json.",
        )
    validate_model(model_root)
    target = (destination or default_model_directory()).expanduser().resolve()
    if target.exists():
        try:
            validate_model(target)
            _write_model_notice(target)
            return model_status(target)
        except CutNotesError:
            pass
    target.parent.mkdir(parents=True, exist_ok=True)
    available = shutil.disk_usage(target.parent).free
    if available < MODEL_BYTES:
        raise CutNotesError(
            "There is not enough disk space to install the Parakeet model.",
            EXIT_DEPENDENCY,
            code="model_disk_space",
            recovery=f"Free at least {MODEL_BYTES} bytes and try again.",
        )
    staging = Path(tempfile.mkdtemp(prefix=".cutnotes-model-", dir=target.parent))
    try:
        for spec in MODEL_FILES:
            output = staging / spec.path
            output.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(_safe_file(model_root, spec.path), output, follow_symlinks=False)
        _write_model_notice(staging)
        _install_staging(staging, target)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return model_status(target)


def download_model(
    *,
    accept_license: bool,
    destination: Path | None = None,
    reporter: ProgressReporter | None = None,
) -> dict:
    if not accept_license:
        raise CutNotesError(
            "Downloading Parakeet requires explicit acceptance of its CC BY 4.0 license.",
            EXIT_INPUT,
            code="model_license_not_accepted",
            recovery=f"Review {MODEL_LICENSE_URL}, then retry with --accept-license.",
        )
    target = (destination or default_model_directory()).expanduser().resolve()
    if target.exists():
        try:
            validate_model(target)
            _write_model_notice(target)
            return model_status(target)
        except CutNotesError:
            pass
    target.parent.mkdir(parents=True, exist_ok=True)
    available = shutil.disk_usage(target.parent).free
    if available < MODEL_BYTES:
        raise CutNotesError(
            "There is not enough disk space to download the Parakeet model.",
            EXIT_DEPENDENCY,
            code="model_disk_space",
            recovery=f"Free at least {MODEL_BYTES} bytes and try again.",
        )

    progress = reporter or ProgressReporter(None)
    progress.stage("model-download", "Downloading the pinned Parakeet v3 model")
    staging = Path(tempfile.mkdtemp(prefix=".cutnotes-model-", dir=target.parent))
    downloaded = 0
    try:
        for spec in MODEL_FILES:
            output = staging / spec.path
            output.parent.mkdir(parents=True, exist_ok=True)
            url = (
                f"https://huggingface.co/{MODEL_REPOSITORY}/resolve/"
                f"{MODEL_REVISION}/{spec.path}?download=true"
            )
            request = Request(url, headers={"User-Agent": "CutNotes/1.0"})
            digest = hashlib.sha256()
            size = 0
            try:
                with urlopen(request, timeout=60) as response, output.open("xb") as handle:
                    while chunk := response.read(1_048_576):
                        handle.write(chunk)
                        digest.update(chunk)
                        size += len(chunk)
                        downloaded += len(chunk)
                        progress.progress(
                            "model-download",
                            downloaded / MODEL_BYTES,
                            "Downloading local transcription model",
                        )
            except (HTTPError, URLError, TimeoutError, OSError) as error:
                raise CutNotesError(
                    "The Parakeet model download did not complete.",
                    EXIT_DEPENDENCY,
                    code="model_download_failed",
                    recovery="Check the internet connection and retry; partial files were removed.",
                ) from error
            if size != spec.size or digest.hexdigest() != spec.sha256:
                raise CutNotesError(
                    f"The downloaded Parakeet model file {spec.path} failed verification.",
                    EXIT_DEPENDENCY,
                    code="model_download_untrusted",
                    recovery="Retry later; the untrusted partial model was removed.",
                )
        _write_model_notice(staging)
        _install_staging(staging, target)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    progress.progress("model-download", 1.0, "Local transcription model is ready")
    return model_status(target)
