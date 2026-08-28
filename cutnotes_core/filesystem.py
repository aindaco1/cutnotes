"""Safe, collision-resistant CutNotes output paths."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
import re
import unicodedata


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_value).strip("-").lower()
    return slug or "cut-notes"


def project_folder_name(value: str) -> str:
    safe_name = re.sub(r"[/\x00-\x1f:]+", " - ", value.strip())
    safe_name = re.sub(r"\s+", " ", safe_name).strip(" .-")
    return safe_name or "Cut Notes"


def project_directory(root: Path, title: str) -> Path:
    resolved_root = root.expanduser().resolve()
    directory = (resolved_root / project_folder_name(title)).resolve()
    if directory.parent != resolved_root:
        raise ValueError("project directory escaped its configured root")
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def allocate_session_paths(
    directory: Path,
    title: str,
    audio_suffix: str,
    include_markdown: bool,
) -> dict[str, Path | None]:
    normalized_audio_suffix = audio_suffix if audio_suffix.startswith(".") else f".{audio_suffix}"
    document_slug = slugify(title)

    def paths_for(suffix: str) -> dict[str, Path | None]:
        return {
            "audio": directory / f"voice-notes{suffix}{normalized_audio_suffix}",
            "transcript": directory / f"transcript{suffix}.txt",
            "markdown": directory / f"{document_slug}{suffix}.md" if include_markdown else None,
            "metadata": directory / f"session{suffix}.json",
        }

    primary = paths_for("")
    if not any(path.exists() for path in primary.values() if path is not None):
        return primary

    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    candidate = paths_for(f"-{stamp}")
    counter = 2
    while any(path.exists() for path in candidate.values() if path is not None):
        candidate = paths_for(f"-{stamp}-{counter}")
        counter += 1
    return candidate


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)
