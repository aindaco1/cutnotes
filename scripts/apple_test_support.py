"""Shared Markdown parsing for development-only Apple content checks."""

import re


def parse_notes(markdown):
    general, _, timed = markdown.partition("## Timestamped feedback")
    if "## Overall feedback" in general:
        body = general.partition("## Overall feedback")[2].strip()
        notes = [{"location": "general", "text": paragraph.strip()}
                 for paragraph in re.split(r"\n\s*\n", body) if paragraph.strip()]
    else:
        notes = [{"location": "general", "text": line[2:].strip()}
                 for line in general.splitlines() if line.startswith("- ")]
    for line in timed.splitlines():
        cells = re.split(r"(?<!\\)\|", line.strip())
        if len(cells) == 4:
            label, body = cells[1].strip(" *"), cells[2].strip()
            if label.lower() == "video time" or re.fullmatch(r"[-: ]+", label):
                continue
            notes.append({"location": label, "text": body})
    return notes


def scoped_notes(notes, scope):
    if scope == "document":
        return notes
    return [note for note in notes if (note["location"] == "general" if scope == "general"
                                      else re.search(scope, note["location"]))]
