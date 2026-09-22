"""Evidence and bounded revision checks for the development formatter.

These checks catch known failure classes, not arbitrary semantic errors. Their
result never establishes release acceptance or permits silent source deletion.
"""
from __future__ import annotations

from difflib import SequenceMatcher
import re

SENTENCES = re.compile(r'''(?<=[.!?])\s+|(?<=[.!?]["'’”])\s+|\n+''')
REQUEST = re.compile(
    r"(?:^|[,:;]\s*)(?:please\s+)?(?:do not\s+|don't\s+)?(?:keep|leave|add|remove|move|hold|bring|lower|"
    r"increase|reduce|align|change|show|trim|give|check|make|stylize|crossfade|fix)\b|"
    r"\b(?:should|needs? to|would (?:like|prefer)|could we|let['’]s|"
    r"(?:would be|be) (?:nice|great|awesome|helpful|better) if)\b", re.I)
UNCERTAIN = re.compile(r"\b(?:may|might|maybe|perhaps|possibly|possible|could|unsure|not sure|"
                       r"(?:I )?(?:do not|don't|don’t) know)\b", re.I)
CONDITIONAL = re.compile(r"\b(?:if|unless|provided|only when|before)\b", re.I)
SMALL = re.compile(r"\b(?:slight\w*|subtle|little|bit)\b", re.I)
REASON = re.compile(r"\b(?:because|so that|so we|so the|since|in order to)\b", re.I)
FUNCTION_WORDS = frozenset("a an the is are am was were be been being it its that this these those i we you they he she them their there of to in on with and but as at for from by just um uh".split())


def statements(text: str) -> list[str]:
    return [part.strip() for part in SENTENCES.split(text.strip()) if part.strip()]


def has_request(text: str) -> bool:
    return any(REQUEST.search(sentence) for sentence in statements(text))


def has_condition(text: str) -> bool:
    # Epistemic "if" introduces uncertainty, not a condition on requested work.
    text = re.sub(r"\b(?:(?:do not|don't|don’t) know|not sure|unsure|wonder)\s+if\b",
                  "whether", text, flags=re.I)
    return bool(CONDITIONAL.search(text))


def evidence_for(source: str) -> list[dict]:
    """Keep every source sentence; role hints are explicit syntax, not decisions."""
    rows = []
    for index, text in enumerate(statements(source), 1):
        tags = []
        if REQUEST.search(text):
            tags.append("explicit_change_or_keep_request")
        if UNCERTAIN.search(text):
            tags.append("uncertainty")
        if has_condition(text):
            tags.append("condition")
        if SMALL.search(text):
            tags.append("limited_degree")
        if REASON.search(text):
            tags.append("reason")
        rows.append({"id": f"C{index}", "quote": text, "syntax_hints": tags or ["statement"]})
    return rows


def relevance_review(source: str, *, editorial: bool | None, conversation: bool | None) -> dict:
    """Require two specific signals and preserve request/qualification passages.

    A proposed exclusion is reversible and stays in the audit. This experiment
    must not become a production deletion gate without native acceptance.
    """
    protected = bool(has_request(source) or UNCERTAIN.search(source))
    disposition = ("keep" if editorial is True else
                   "background" if editorial is False and conversation is True and not protected else "review")
    return {"disposition": disposition, "editorial": editorial, "conversation": conversation,
            "protected_request_or_qualification": protected, "requires_review": True}


def validate_extracted_facts(source: str, facts: list[dict]) -> list[str]:
    """Require literal evidence and full character coverage before using a plan."""
    if not isinstance(facts, list) or not facts or len(facts) > 12:
        return ["Invalid or empty evidence list"]
    covered = set()
    issues = []
    for fact in facts:
        if not isinstance(fact, dict) or fact.get("role") not in {"observation", "request", "qualification"}:
            issues.append("Invalid evidence role")
            continue
        quote = fact.get("quote")
        if not isinstance(quote, str) or not quote or quote not in source:
            issues.append("Evidence is not an exact source quote")
            continue
        # One quote must not stand in for multiple occurrences without an audit.
        start = source.find(quote)
        while start >= 0 and all(i in covered for i in range(start, start + len(quote))):
            start = source.find(quote, start + 1)
        if start < 0:
            issues.append("Evidence occurrence repeated without source coverage")
            continue
        covered.update(range(start, start + len(quote)))
        if has_request(quote) and fact["role"] == "observation":
            issues.append("Explicit request labeled as observation")
        if UNCERTAIN.search(quote) and fact["role"] == "observation":
            issues.append("Uncertainty not represented in evidence role")
    if any(c.isalnum() and i not in covered for i, c in enumerate(source)):
        issues.append("Source statements missing from the evidence plan")
    return list(dict.fromkeys(issues))


def _words(text):
    text = text.casefold().replace("’", "'")
    for short, full in (("don't", "do not"), ("doesn't", "does not"), ("didn't", "did not"),
                        ("isn't", "is not"), ("aren't", "are not"), ("can't", "cannot"),
                        ("it's", "it is"), ("that's", "that is"), ("there's", "there is"),
                        ("that'd", "that would"), ("they're", "they are")):
        text = text.replace(short, full)
    return re.findall(r"[a-z]+|\d+", text)


def _content(text):
    return [w for w in _words(text) if w not in FUNCTION_WORDS]


def _clauses(text):
    return [c.strip() for c in re.split(r"[.!?;]+|\b(?:and|but)\b", text) if c.strip()]


def _negative(text):
    return any(w in {"not", "never", "cannot", "no"} for w in _words(text))


def revision_issues(source: str, candidate: str) -> list[str]:
    """Flag demonstrable risks without banning every useful content-word edit.

    Unflagged output still requires semantic/native and human evaluation. These
    bounded rules deliberately do not claim general negation-scope parsing.
    """
    if not isinstance(candidate, str) or not candidate.strip():
        return ["Empty revision"]
    issues = []
    before, after = _content(source), _content(candidate)
    if re.findall(r"\d+", source) != re.findall(r"\d+", candidate):
        issues.append("Numbers changed or omitted")
    for quote in re.findall(r'[“"]([^”"]+)[”"]', source):
        if " ".join(_words(quote)) not in " ".join(_words(candidate)):
            issues.append("Quoted dialogue changed or omitted")
    if not has_request(source) and has_request(candidate):
        issues.append("Observation acquired a change request")
    if has_request(source) and not has_request(candidate):
        issues.append("Explicit request may have become an observation")
    if has_condition(source) and not has_condition(candidate):
        issues.append("Condition may be missing")
    if _negative(source) != _negative(candidate):
        # This deliberately defers some faithful antonym substitutions too.
        # It catches a lost negative observation alongside a retained request;
        # matching content-word sets alone cannot detect that omission.
        issues.append("Explicit negation added or lost; verify statement coverage")
    for label, pattern in (("Uncertainty", UNCERTAIN), ("Limited degree", SMALL), ("Reason", REASON)):
        if pattern.search(source) and not pattern.search(candidate):
            issues.append(label + " may be missing")
    # Token sets miss a property swap. Identical sets in a different sequence
    # require review even when no word has been added or removed.
    unique_before = list(dict.fromkeys(before))
    unique_after = list(dict.fromkeys(after))
    if set(before) == set(after) and unique_before != unique_after:
        issues.append("Content words changed order; verify their relationships")
    for original in _clauses(source):
        tokens = set(_content(original)) - {"not", "no", "never", "cannot", "do", "does", "did"}
        if not tokens:
            continue
        for revised in _clauses(candidate):
            revised_tokens = set(_content(revised)) - {"not", "no", "never", "cannot", "do", "does", "did"}
            if tokens == revised_tokens and _negative(original) != _negative(revised):
                issues.append("Negation changed within a matching clause")
    # A large unrelated completion is a review risk, not a synonym blacklist.
    if len(set(after) - set(before)) >= 5 and len(set(before) & set(after)) / max(1, len(set(after))) < 0.5:
        issues.append("Revision introduces substantial unsupported vocabulary")
    return list(dict.fromkeys(issues))


def revision_review(source: str, candidate: str) -> dict:
    if not isinstance(candidate, str) or not candidate.strip():
        raise ValueError("Native Apple revision returned no text")
    issues = revision_issues(source, candidate)
    old, new = _content(source), _content(candidate)
    changes = [{"operation": op, "source": old[a:b], "candidate": new[c:d]}
               for op, a, b, c, d in SequenceMatcher(a=old, b=new, autojunk=False).get_opcodes() if op != "equal"]
    return {"schema_version": "cutnotes.editorial-edit-review.v1", "source_evidence": evidence_for(source),
            "proposed": candidate, "issues": issues, "content_changes": changes,
            "accepted_for_review": not issues, "semantic_correctness_proven": False}
