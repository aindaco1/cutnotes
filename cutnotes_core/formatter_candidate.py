"""Source-preserving editorial formatter shared by Apple and development experiments.

Apple supplies bounded decisions; the core owns source text, time evidence,
grouping, revision checks, and Markdown rendering. The audit supports local review;
its checks do not prove semantic correctness.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Callable

from .formatting import (
    BRACKETED_TIMECODE, DraftNote, SourceUnit, _NUMBER_PHRASE, _number_phrase,
    canonicalize_timecodes, render_editorial_draft, source_timecodes,
)


Question = Callable[[str, str], bool]
RANGE = re.compile(
    rf"\b(?:at|so|around)\s+(?P<start>{_NUMBER_PHRASE})\s+"
    rf"(?:through|to)\s+(?P<end>{_NUMBER_PHRASE})\s+seconds?\b", re.I)
RETROSPECTIVE = re.compile(
    rf"\b(?:that(?:'s| is| would be)|this was|I mean)\s+"
    rf"(?:(?:like|at|around|I don['’]t know)[,\s]*)*(?P<value>{_NUMBER_PHRASE})\s+seconds?\b", re.I)
CORRECTION = re.compile(
    rf"^(?P<value>{_NUMBER_PHRASE})\s+seconds?\s+(?:I guess|I think)[.!?]*$", re.I)
GENERAL = re.compile(r"\b(?:overall|in general|general (?:note|feedback)|the rest is|one (?:other|more) thing)\b", re.I)
ENDING = re.compile(r"\b(?:at the end|last frame|final (?:image|frame)|outro|end scene)\b", re.I)
BEGINNING = re.compile(r"\b(?:opening shot|at the beginning)\b", re.I)
CONTINUATION = re.compile(r"^(?:it\b|this\b|that\b|they\b|he\b|she\b|maybe\b|perhaps\b|I don['’]t\b|I mean\b|if\b)", re.I)
PREFACE = re.compile(r"^(?:this is (?:a )?)?(?:bonus|final) (?:thing|thought|note)[.!?]*$", re.I)
INTRO = re.compile(r"^(?:(?:okay|ok|um|uh|so|again|just|right|at)[,\s]+)+", re.I)
TIMING_FILLER = re.compile(
    r"^(?:(?:okay|ok|um|uh|so|again|just|right|at|for|with|a|the|beginning|to|that|"
    r"opening|shot|it['’]s|like|I|guess|think|don['’]t|know|would|be|great|that['’]d)[,\s]*)*$", re.I)

# A deliberately narrow copyediting contract, not a semantic correctness test.
# Content-word substitutions and added modal/negative claims require human review.
GRAMMAR_WORDS = frozenset("a an the is are am was were be been being it its that this these those i we you they he she them their there of to in on with and but as at for from by just um uh".split())


def copyedit_issues(source: str, candidate: str) -> list[str]:
    def words(text):
        text = text.casefold().replace("’", "'")
        for short, long in (("don't", "do not"), ("doesn't", "does not"), ("didn't", "did not"),
                            ("isn't", "is not"), ("aren't", "are not"), ("can't", "cannot"),
                            ("it's", "it is"), ("that's", "that is"), ("there's", "there is"),
                            ("that'd", "that would"), ("they're", "they are"), ("we're", "we are")):
            text = text.replace(short, long)
        return set(re.findall(r"[a-z]+|\d+", text)) - GRAMMAR_WORDS
    before, after = words(source), words(candidate)
    # "Be nice if..." -> "It would be nice if..." supplies grammar to an existing condition.
    if "if" in before and "if" in after:
        before.add("would")
        after.add("would")
    issues = []
    if added := after - before:
        issues.append("Added content words: " + ", ".join(sorted(added)))
    if missing := before - after:
        issues.append("Removed content words: " + ", ".join(sorted(missing)))
    return issues


def clean_disfluencies(text: str) -> str:
    """Only mechanical deletions; never infer a desired edit or repair a name."""
    text = re.sub(r"\b(?:um|uh)\b[,\s]*", "", text, flags=re.I)
    text = re.sub(r"\b(\w+)(?:\s+\1\b)+", r"\1", text, flags=re.I)
    # A repeated lead-in with an abandoned partial word: "with the d with the drawing".
    text = re.sub(r"\b((?:with|on|in|to|for) the) ([a-z]{1,2}) \1 (\2[a-z]{2,})\b",
                  r"\1 \3", text, flags=re.I)
    return " ".join(text.split()).strip(" ,")


def normalize_review_times(text: str) -> str:
    """Additional explicit spoken CUT cues; durations remain ordinary text."""
    def range_replacement(match):
        start = _number_phrase(match['start'], maximum=59)
        end = _number_phrase(match['end'], maximum=59)
        if start is None or end is None or not start < end:
            return match.group()
        return f"[00:{start:02d}–00:{end:02d}]"
    text = RANGE.sub(range_replacement, text)
    def seconds_replacement(match):
        seconds = _number_phrase(match['value'], maximum=59)
        return f"[00:{seconds:02d}]" if seconds is not None else match.group()
    text = RETROSPECTIVE.sub(seconds_replacement, text)
    # Restrict the one-zero shorthand to the beginning of a sentence. A count such
    # as "zero missing frames" is not a time cue.
    text = re.sub(rf"(?im)(^|(?<=[.!?])\s+)(?:zero|oh)\s+(?P<value>{_NUMBER_PHRASE})(?=[,.!?]|\s+seconds?\b)",
                  lambda m: m[1] + seconds_replacement(m), text)
    return canonicalize_timecodes(text)


@dataclass
class Passage:
    source_ids: list[str] = field(default_factory=list)
    texts: list[str] = field(default_factory=list)
    times: tuple[str, ...] = ()
    location: str = "general"
    approximate: bool = False


def format_candidate(*, transcript: str, title: str, review_date: str,
                     ask: Question, edit: Callable[[str], str] | None = None,
                     revise: Callable[[str], dict] | None = None,
                     classify_passage: Callable[[str], dict] | None = None) -> tuple[str, dict]:
    """Create an explicitly reviewable source-preserving draft and an audit trail."""
    if edit is not None and revise is not None:
        raise ValueError("Choose one editing strategy")
    raw = [s.strip() for s in re.split(r'''(?<=[.!?])\s+|(?<=[.!?]["'’”])\s+|\n+''', transcript.strip()) if s.strip()]
    passages: list[Passage] = []
    trace: list[dict] = []
    units: list[SourceUnit] = []
    warnings: list[str] = []
    active_times: tuple[str, ...] = ()
    pending_ids: list[str] = []
    pending_prefixes: list[str] = []
    previous_source = ""
    previous_was_cue = False

    for index, original in enumerate(raw):
        source_id = f"S{index + 1:04d}"
        # Recognize spoken digits before deleting repeated words: the repeated
        # zeros in a CUT time are data, not a speech disfluency.
        cleaned = clean_disfluencies(original)
        normalized = clean_disfluencies(normalize_review_times(original))
        correction = CORRECTION.fullmatch(cleaned)
        is_correction = bool(correction and previous_was_cue and active_times)
        if is_correction:
            seconds = _number_phrase(correction['value'], maximum=59)
            if seconds is not None:
                normalized = f"[00:{seconds:02d}]"
                warnings.append(f"{source_id}: speaker gives an uncertain timing correction; both times are retained.")
        times = tuple(source_timecodes(normalized))
        units.append(SourceUnit(source_id, original, times))
        body = BRACKETED_TIMECODE.sub("", normalized).strip(" ,.")
        body = INTRO.sub("", body).strip(" ,.")
        retrospective = bool(RETROSPECTIVE.search(cleaned))
        timing_only = bool(times) and bool(
            not body or is_correction or
            TIMING_FILLER.fullmatch(body)
        )
        row = {"source_id": source_id, "source": original, "normalized": normalized,
               "times": list(times), "timing_only": timing_only}
        trace.append(row)
        if PREFACE.fullmatch(body):
            pending_prefixes.append(body.rstrip(".!?") + ".")
            pending_ids.append(source_id)
            previous_source, previous_was_cue = original, False
            continue
        if timing_only:
            if retrospective and passages:
                passages[-1].times = times
                passages[-1].location = "auto"
                passages[-1].approximate = bool(re.search(r"\b(?:around|guess|don['’]t know)\b", original, re.I))
                passages[-1].source_ids.append(source_id)
                active_times = times
            elif is_correction:
                active_times = tuple(dict.fromkeys(active_times + times))
                pending_ids.append(source_id)
            elif passages and times and set(times).intersection(passages[-1].times):
                passages[-1].times = tuple(dict.fromkeys(passages[-1].times + times))
                passages[-1].source_ids.append(source_id)
                active_times = passages[-1].times
            else:
                active_times = times
                pending_ids.append(source_id)
            # A trailing response to a proposed change is meaningful feedback,
            # even when it shares a sentence with a redundant spoken time.
            affirmation = re.search(r"\b(?:that['’]d|that would) be (?:great|good|helpful)\b", body, re.I)
            if affirmation and passages and set(times).intersection(passages[-1].times):
                passages[-1].texts.append(affirmation.group()[0].upper() + affirmation.group()[1:] + ".")
            previous_source, previous_was_cue = original, True
            continue

        context = f"Previous sentence: {previous_source or '(none)'}\nTarget sentence: {body}"
        unrelated = ask("unrelated", context)
        row["unrelated"] = unrelated
        if unrelated:
            # Current Core model falsely calls some qualifications irrelevant.
            # Preserve them for review instead of silently deleting feedback.
            warnings.append(f"{source_id}: Apple marked this as unrelated or unclear; source wording was retained for review.")
        same = bool(passages) and ask("same", context)
        explicit_general = bool(GENERAL.search(body))
        overall = explicit_general or (ask("overall", context) and not same)
        end = bool(ENDING.search(normalized))
        beginning = bool(BEGINNING.search(normalized))
        continuation = bool(CONTINUATION.search(body))
        if continuation and passages and not explicit_general:
            same, overall = True, False
        # General passages continue until an explicit new topic, and every
        # explicit time with feedback starts its own observation. This keeps
        # caveats attached while allowing independent notes at the same time.
        if passages and passages[-1].location == "general" and not explicit_general:
            same = True
        if times or explicit_general or end or beginning:
            same = False
        if times:
            active_times = times
            location = "auto"
        elif end:
            active_times, location = (), "end"
        elif overall:
            active_times, location = (), "general"
        elif beginning and not active_times:
            location = "beginning"
        else:
            location = passages[-1].location if passages and not active_times else "auto" if active_times else "general"
        row.update(overall=overall, same=same, location=location)
        ids = pending_ids + [source_id]
        pending_ids = []
        evidence = " ".join(unit.text for unit in units if unit.id in ids)
        approximate = bool(re.search(r"\b(?:around|roughly|near|guess|I think)\b", evidence, re.I))
        if passages and same and passages[-1].times == active_times and passages[-1].location == location:
            passage = passages[-1]
            passage.source_ids.extend(ids)
        else:
            passage = Passage(ids, [], active_times, location, approximate)
            passages.append(passage)
        passage.texts.extend(pending_prefixes)
        pending_prefixes = []
        text = body[0].upper() + body[1:] if body else ""
        if text and text[-1] not in ".!?":
            text += "."
        if text and text.casefold() not in {value.casefold() for value in passage.texts}:
            passage.texts.append(text)
        previous_source, previous_was_cue = original, False

    general, timed, revisions, relevance = [], [], [], []
    rendered_ids = []
    for passage in passages:
        if not passage.texts:
            continue
        source_body = " ".join(passage.texts)
        if classify_passage:
            classification = classify_passage(source_body)
            if classification.get("disposition") not in {"keep", "background", "review"}:
                raise ValueError("Invalid passage relevance decision")
            explicit_cut_cue = any(unit.timecodes for unit in units if unit.id in passage.source_ids)
            if classification["disposition"] == "background" and (GENERAL.search(source_body) or explicit_cut_cue):
                classification = dict(classification, disposition="review", protected_editorial_cue=True)
            relevance.append({"source_ids": passage.source_ids, "source": source_body, **classification})
            if classification["disposition"] == "background":
                warnings.append(" / ".join(passage.source_ids) + ": proposed background exclusion; original retained in audit for review.")
                continue
            if classification["disposition"] == "review":
                warnings.append(" / ".join(passage.source_ids) + ": uncertain relevance; retained for review.")
        body = edit(source_body) if edit else source_body
        if revise:
            revision = revise(source_body)
            body = revision.get("proposed")
            if not isinstance(body, str) or not body.strip() or not isinstance(revision.get("issues"), list):
                raise ValueError("Invalid evidence-based revision")
            revisions.append({"source_ids": passage.source_ids, "source": source_body, **revision,
                              "accepted": not revision["issues"]})
            if revision["issues"]:
                body = source_body
                warnings.append(" / ".join(passage.source_ids) + ": revision needs review; source wording retained.")
        if not isinstance(body, str) or not body.strip():
            raise ValueError("Native Apple editing returned no text")
        if edit:
            issues = copyedit_issues(source_body, body)
            revisions.append({"source_ids": passage.source_ids, "source": source_body,
                              "proposed": body, "accepted": not issues, "issues": issues})
            if issues:
                body = source_body
                warnings.append(" / ".join(passage.source_ids) + ": copyedit exceeded the source-preserving contract; source wording retained for review.")
        note = DraftNote("Overall feedback" if passage.location == "general" else "Editorial feedback",
                         body.strip(), tuple(passage.source_ids),
                         location=passage.location, timecodes=passage.times,
                         approximate=passage.approximate)
        (general if passage.location == "general" else timed).append(note)
        rendered_ids.extend(passage.source_ids)
    markdown = render_editorial_draft(title=title, review_date=review_date,
                                     general_notes=general, timestamped_notes=timed, units=units)
    audit = {"schema_version": "cutnotes.formatter.candidate.v1", "requires_review": True,
             "warnings": warnings, "sentences": trace,
             "revisions": revisions, "relevance": relevance,
             "rendered_source_ids": rendered_ids,
             "unassigned_timing_ids": pending_ids}
    return markdown, audit
