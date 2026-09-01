"""Fast, dependency-free intent classification for automatic model routing.

This runs on every chat request, so importing and training a machine-learning
pipeline here adds a large cold-start delay for very little benefit. A small
keyword scorer is deterministic, starts instantly, and preserves the existing
route categories.
"""
import difflib
import re


_TOKEN_RE = re.compile(r"[a-z0-9+#.-]+")
_KEYWORDS = {
    'code': {
        'api', 'bug', 'class', 'code', 'coding', 'css', 'database', 'debug',
        'django', 'error', 'exception', 'flask', 'framework', 'function', 'html',
        'java', 'javascript', 'node', 'php', 'program', 'programming', 'python',
        'react', 'script', 'sql', 'traceback', 'typescript',
    },
    'research': {
        'compare', 'current', 'evidence', 'fact', 'facts', 'latest', 'news',
        'research', 'source', 'sources', 'study', 'today', 'verify',
    },
    'shopping': {
        'buy', 'order', 'price', 'product', 'recommend', 'shop', 'shopping',
        'store',
    },
    'document': {
        'document', 'file', 'pdf', 'presentation', 'spreadsheet', 'summarize',
        'summary',
    },
    'creative': {
        'brainstorm', 'caption', 'creative', 'email', 'poem', 'rewrite',
        'story',
    },
}
_CATEGORY_PRIORITY = ('code', 'research', 'shopping', 'document', 'creative')


def classify(text):
    tokens = set(_TOKEN_RE.findall((text or '').lower()))
    if not tokens:
        return 'general'

    scores = {
        category: len(tokens.intersection(keywords))
        for category, keywords in _KEYWORDS.items()
    }
    best_score = max(scores.values(), default=0)
    if not best_score:
        return 'general'
    return next(category for category in _CATEGORY_PRIORITY if scores[category] == best_score)


def choose_model(text, default_model):
    category = classify(text)
    return {'code': 'code', 'research': 'light'}.get(category, default_model), category


def choose_chatgpt_worker(text):
    """Choose the backing worker for the ChatGPT 5.6 experience.

    Image and document-action routing happens in the view because it depends
    on validated attachments. Code handles programming requests and Quick
    handles other text turns.
    """
    category = classify(text)
    return ('code' if category == 'code' else 'quick'), category


# ---- "save this as a note" intent, for the My Notes sidebar feature ----
# Fixed idiomatic phrases ("take this note", "note it down"), not topic
# keywords — a plain regex match is a better fit here than classify()'s
# token-set scoring above.
_NOTE_INTENT_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in (
        r"\btake (?:a |this )?note\b",
        r"\bmake (?:a |this )?note\b",
        r"\bcreate (?:a |this )?note\b",
        r"\badd (?:a |this )?note\b",
        r"\bwrite (?:a |this )?note\b",
        r"\bsave (?:a |this )?note\b",
        r"\bremember (?:a |this )?note\b",
        r"\bnote (?:it |this |that )?down\b",
        r"\bjot (?:it |this |that )?down\b",
        r"\bsave (?:the |all |my )?details?\b",
    )
]


def is_note_intent(text):
    """True if the user is asking to save something to their notes — 'take
    this note', 'note it down', 'save details related to it', etc."""
    text = _typo_correct_note_keywords(text)
    return any(pattern.search(text) for pattern in _NOTE_INTENT_PATTERNS)


def strip_note_intent(text):
    """Removes the matched trigger phrase from `text`, leaving whatever else
    was typed along with it (e.g. 'note down: buy milk' -> 'buy milk') so
    that can be used as the note's content directly instead of falling back
    to the assistant's last reply. Safe to call even with no match."""
    original = text or ''
    tokens = list(re.finditer(r"[A-Za-z]+", original))
    corrected = [_typo_correct_note_keywords(token.group()).lower() for token in tokens]
    note_index = next((i for i, word in enumerate(corrected) if word in ('note', 'notes')), None)
    if note_index is None:
        return ''
    end_index = note_index
    while end_index + 1 < len(tokens) and corrected[end_index + 1] in ('it', 'this', 'that', 'down', 'as'):
        end_index += 1
    return original[tokens[end_index].end():].strip(' :-—').strip()


# A missed note command doesn't just fail quietly — the message falls
# through to the real AI model, which (per its own conversation history full
# of this router's earlier "Saved to your notes" / "Deleted your note"
# confirmations) will happily fabricate its own fake one instead of just not
# understanding. So typo tolerance here isn't cosmetic: it's what keeps a
# dropped/swapped letter ("delet all notyes") from silently turning into a
# lying reply instead of a real action.
#
# Deliberately narrow to avoid the opposite failure (an ordinary sentence
# getting misread as a notes command): only 4+ letter words get checked,
# only against a same-first-letter candidate (this alone rules out most
# accidental collisions — 'wake'/'lake'/'cake' vs 'take' have different
# first letters, for instance), and a handful of common words that DO still
# survive both filters (verified against a ~150-word sweep of common
# English vocabulary) are hard-excluded below — most importantly 'made',
# which would otherwise turn "she made a note about it" (a past-tense
# remark) into a live 'make a note' command.
_NOTE_KEYWORD_CANONICALS = (
    'note', 'notes', 'delete', 'remove', 'clear', 'erase', 'edit', 'update',
    'change', 'rename', 'correct', 'show', 'list', 'open', 'read', 'view',
    'replace', 'rewrite', 'set', 'take', 'make', 'create', 'save', 'write',
    'add', 'remember', 'all',
)
_NOTE_TYPO_CORRECTION_EXCLUDE = {
    'made', 'safe', 'ready', 'oven', 'slow', 'snow', 'nose', 'node', 'chase',
    'date', 'vote', 'not', 'last', 'lost', 'reached',
}


def _typo_correct_note_keywords(text):
    def fix_word(match):
        word = match.group(0)
        lower = word.lower()
        if lower in _NOTE_KEYWORD_CANONICALS or lower in _NOTE_TYPO_CORRECTION_EXCLUDE or len(lower) < 4:
            return word
        same_first_letter = [c for c in _NOTE_KEYWORD_CANONICALS if c[0] == lower[0]]
        candidates = difflib.get_close_matches(lower, same_first_letter, n=1, cutoff=0.72)
        return candidates[0] if candidates else word
    return re.sub(r"[A-Za-z]+", fix_word, text or '')


# ---- "show / delete / edit my notes" — same idea, for the rest of the My
# Notes lifecycle beyond just saving one. ----
_SHOW_NOTES_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in (
        r"\b(?:show|list|view|open|read|see)\s+(?:me\s+)?(?:all\s+)?(?:my\s+)?notes?\b\s*$",
        r"\bwhat\s+notes?\s+do\s+i\s+have\b",
        r"\bwhat\s+(?:have\s+i|did\s+i)\s+(?:saved?|noted?)\b",
    )
]

_READ_NOTE_RE = re.compile(
    r"\b(?:open|read|show|view)\s+(?:me\s+)?(?:my\s+|the\s+)?note\s+(.+?)\s*$",
    re.IGNORECASE,
)

# Captures an optional 'all'/'my'/'the' prefix (group 1) separately from
# whatever comes after 'note(s)' (group 2, the target to search for) — 'all'
# in the prefix means every note, not one to search for by name.
_DELETE_NOTE_RE = re.compile(
    r"\b(?:delete|remove|clear|erase)\s+((?:the\s+|my\s+|all\s+(?:my\s+)?)?)notes?\b(.*)$",
    re.IGNORECASE,
)
_DELETE_NOTE_RE_TARGET_FIRST = re.compile(
    r"\b(?:delete|remove|clear|erase)\s+(?:the\s+|my\s+)?"
    r"(first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|"
    r"(?:number\s+|id\s+|#)?\d+)\s+note\b\s*$",
    re.IGNORECASE,
)
# Non-greedy up to the first standalone 'to' splits '<target> to <new text>'
# — this misreads a target that itself contains the word 'to' (e.g. 'note
# about how to bake bread'), but that's an acceptable miss for a
# dependency-free heuristic; the caller already handles "couldn't find a
# note matching that" gracefully either way.
_EDIT_NOTE_RE = re.compile(
    r"\b(?:edit|update|change|rename|correct|replace|rewrite)\s+(?:the\s+|my\s+)?(?:full\s+|entire\s+)?note\b(.*?)(?:\b(?:to|with)\b(.*))?$",
    re.IGNORECASE,
)
_EDIT_NOTE_RE_TARGET_FIRST = re.compile(
    r"\b(?:edit|update|change|rename|correct|replace|rewrite)\s+(?:the\s+|my\s+)?"
    r"(first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|"
    r"(?:number\s+|id\s+|#)?\d+)\s+note\b(?:\s+(?:to|with)\s+(.*))?\s*$",
    re.IGNORECASE,
)
_TARGET_PREFIX_RE = re.compile(r"^\s*(?:about|for|called|titled|on|regarding)\b", re.IGNORECASE)
_CONTENT_PREFIX_RE = re.compile(r"^\s*(?:say|read|be)\b", re.IGNORECASE)

DELETE_ALL_NOTES = '__ALL__'
_ORDINALS = {
    'first': '1', 'second': '2', 'third': '3', 'fourth': '4', 'fifth': '5',
    'sixth': '6', 'seventh': '7', 'eighth': '8', 'ninth': '9', 'tenth': '10',
}


def _normalize_note_target(target):
    target = (target or '').strip(' :-—').strip()
    lowered = re.sub(r"^the\s+", '', target.lower()).strip()
    return _ORDINALS.get(lowered, target)


def is_show_notes_intent(text):
    """True for 'show my notes', 'what notes do I have', etc."""
    text = _typo_correct_note_keywords(text)
    return any(pattern.search(text) for pattern in _SHOW_NOTES_PATTERNS)


def match_read_note(text):
    """Return the number/title requested by 'open note 1', etc."""
    match = _READ_NOTE_RE.search(_typo_correct_note_keywords(text))
    if not match:
        return None
    return _normalize_note_target(_TARGET_PREFIX_RE.sub('', match.group(1) or ''))


def match_delete_note(text):
    """None if `text` isn't a 'delete note...' request at all. Otherwise
    DELETE_ALL_NOTES for 'delete all my notes', or the (possibly empty)
    target phrase to search for, e.g. 'delete note about milk' -> 'milk'."""
    corrected = _typo_correct_note_keywords(text)
    match = _DELETE_NOTE_RE.search(corrected)
    if not match:
        alternate = _DELETE_NOTE_RE_TARGET_FIRST.search(corrected)
        return _normalize_note_target(alternate.group(1)) if alternate else None
    if 'all' in (match.group(1) or '').lower():
        return DELETE_ALL_NOTES
    target = _TARGET_PREFIX_RE.sub('', match.group(2) or '')
    return _normalize_note_target(target)


def match_edit_note(text):
    """None if `text` isn't an 'edit note ... to ...' request. Otherwise a
    (target, new_content) tuple — either half can be empty if the phrasing
    didn't include one, which the caller should treat as "ask for more"."""
    corrected = _typo_correct_note_keywords(text)
    match = _EDIT_NOTE_RE.search(corrected)
    if not match:
        alternate = _EDIT_NOTE_RE_TARGET_FIRST.search(corrected)
        if not alternate:
            return None
        original_content = re.search(r"\b(?:to|with)\b\s+(.+?)\s*$", text or '', re.IGNORECASE)
        new_content = original_content.group(1) if original_content else (alternate.group(2) or '')
        return _normalize_note_target(alternate.group(1)), new_content.strip(' :-—').strip()
    target = _TARGET_PREFIX_RE.sub('', match.group(1) or '').strip(' :-—').strip()
    original_content = re.search(r"\b(?:to|with)\b\s+(.+?)\s*$", text or '', re.IGNORECASE)
    raw_content = original_content.group(1) if original_content else (match.group(2) or '')
    new_content = _CONTENT_PREFIX_RE.sub('', raw_content).strip(' :-—').strip()
    return _normalize_note_target(target), new_content


def is_contextual_note_edit(text):
    """Edit wording that can apply to a previously selected database note."""
    corrected = _typo_correct_note_keywords(text).strip()
    return bool(re.match(
        r"^(?:please\s+)?(?:edit|update|change|rename|correct|replace|rewrite|set)\b|"
        r"^(?:only\s+)?(?:the\s+)?(?:time|date|meeting\s+time)\b",
        corrected,
        re.IGNORECASE,
    ))
