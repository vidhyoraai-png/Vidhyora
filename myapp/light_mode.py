"""Retrieval logic for the EduTrellis Light model: check the saved
KnowledgeEntry table first (fast, free, no external call), and only fall
back to a live web search (myapp.web_search, via Tavily) when nothing
relevant is found — saving the top result back to the knowledge base so the
same question is a knowledge-base hit next time instead of another search.
"""
import re

from django.db.models import Q

from myapp import web_search
from myapp import semantic_search
from myapp.models import KnowledgeEntry

MIN_KEYWORD_LEN = 3
# A pasted code block or long document can yield hundreds of "keywords"
# (every CSS class, JS identifier, etc), and each one adds branches to the
# OR'd Q() built below — enough of them overflows SQLite's hard-coded
# expression-tree depth limit (1000) and the query raises OperationalError.
# Capping the keyword count keeps every real query's Q() tree small while
# losing nothing in practice: a genuine question rarely has more than a
# couple dozen meaningful keywords anyway.
MAX_KEYWORDS_FOR_QUERY = 40
KB_MAX_ENTRIES = 3
KB_CONTEXT_MAX_CHARS = 4000
WEB_CONTEXT_MAX_CHARS = 4000
_STOPWORDS = {
    'the', 'a', 'an', 'is', 'are', 'was', 'were', 'what', 'how', 'why', 'who',
    'when', 'where', 'does', 'do', 'did', 'can', 'could', 'should', 'would',
    'for', 'and', 'or', 'of', 'to', 'in', 'on', 'at', 'it', 'this', 'that',
    'you', 'your', 'me', 'my', 'please', 'tell', 'about',
}


def _keywords(text):
    words = re.findall(r"[a-zA-Z0-9']+", (text or '').lower())
    return [w for w in words if len(w) >= MIN_KEYWORD_LEN and w not in _STOPWORDS]


def search_knowledge_base(query, user=None, session_key=''):
    """Simple substring/keyword match, ranked by how many query keywords
    appear in topic+content — not embeddings, which would be overkill for a
    small, mostly hand-curated table and would work against being 'fast'.
    Requires at least 2 shared keywords AND at least half the query's
    keywords to match — a single incidental shared word (e.g. a year like
    '2026' appearing in both an unrelated saved entry and a brand-new
    question) isn't enough, or a completely unrelated topic can hijack an
    otherwise-uncovered question instead of triggering a fresh search.

    Only searches entries that are either shared (no owner) or private to
    THIS caller (matching user, or matching session_key for a guest) — a
    private entry from a file upload or someone's own account details is
    never visible to anyone else's search."""
    keywords = _keywords(query)[:MAX_KEYWORDS_FOR_QUERY]
    if not keywords:
        return []
    q = Q()
    for kw in keywords:
        q |= Q(topic__icontains=kw) | Q(content__icontains=kw)
    owner_q = Q(user__isnull=True, session_key='')
    if user is not None and getattr(user, 'is_authenticated', False):
        owner_q |= Q(user=user)
    elif session_key:
        owner_q |= Q(session_key=session_key)
    candidates = list(KnowledgeEntry.objects.filter(q).filter(owner_q)[:50])

    def score(entry):
        haystack = (entry.topic + ' ' + entry.content).lower()
        return sum(1 for kw in keywords if kw in haystack)

    min_score = max(2, (len(keywords) + 1) // 2)
    scored = [(c, score(c)) for c in candidates]
    scored = [(c, s) for c, s in scored if s >= min_score]
    scored.sort(key=lambda pair: pair[1], reverse=True)
    matches = [c for c, _ in scored][:KB_MAX_ENTRIES]
    if matches:
        return matches

    # Keyword search misses synonyms and paraphrases. Fall back to local
    # embeddings over a bounded owner-scoped corpus.
    semantic_candidates = KnowledgeEntry.objects.filter(owner_q)[:200]
    return semantic_search.rank(query, semantic_candidates, KB_MAX_ENTRIES)


def context_from_entries(entries):
    blocks, total = [], 0
    for e in entries:
        block = f"### {e.topic}\n{e.content}"
        if total + len(block) > KB_CONTEXT_MAX_CHARS:
            break
        blocks.append(block)
        total += len(block)
    return '\n\n'.join(blocks)


def web_search_and_save(query):
    """Runs a live Tavily search and saves the top result to the knowledge
    base for next time. Returns (context_text, 'web_search'), or
    (None, None) if search is unavailable, fails, or returns nothing."""
    try:
        results = web_search.search(query, max_results=5)
    except web_search.SearchError:
        return None, None
    if not results:
        return None, None

    blocks, total = [], 0
    for r in results:
        block = f"### {r['title']}\nSource: {r['url']}\n{r['content']}"
        if total + len(block) > WEB_CONTEXT_MAX_CHARS:
            break
        blocks.append(block)
        total += len(block)

    top = results[0]
    KnowledgeEntry.objects.create(
        topic=query[:200],
        content=top['content'][:4000],
        source=KnowledgeEntry.SOURCE_WEB,
        source_url=top['url'][:200],
    )
    return '\n\n'.join(blocks), 'web_search'


CHAT_SAVE_MIN_MESSAGE_CHARS = 4     # skip near-empty prompts ("hi", "ok")
CHAT_SAVE_TOPIC_MAX_CHARS = 200
CHAT_SAVE_CONTENT_MAX_CHARS = 6000


def _account_context_leaked(account_context, reply_text):
    """True if the reply echoes something unique to this user's own account
    snapshot (an order number, an exact currency amount, a cart/order item
    name, or their own name) — the sign that this answer is specific to
    them, not a generally reusable fact, and must never end up in the
    shared knowledge base where a different user's Light-mode question
    could retrieve someone else's cart, order, wallet, or identity details.
    Deliberately broad/over-inclusive: a false positive here just means one
    extra entry stays private instead of shared (harmless); a false
    negative means a stranger's real account data leaks into a shared
    answer (not harmless), so every token worth catching is worth catching."""
    if not account_context or not reply_text:
        return False
    tokens = set(re.findall(r'#\d+', account_context)) | set(re.findall(r'Rs [\d,]+\.\d{2}', account_context))
    # Cart line: "- {product_name} x{quantity} — Rs {subtotal}"
    tokens.update(m.group(1).strip() for m in re.finditer(r'-\s+(.+?)\s+x\d+\s+—', account_context))
    # Order line: "...Items: {name} x{qty}, {name} x{qty}, ..."
    items_match = re.search(r'Items:\s*(.+)', account_context)
    if items_match:
        for part in items_match.group(1).split(','):
            name = re.sub(r'\s*x\d+\s*$', '', part.strip())
            if name:
                tokens.add(name)
    # "Logged in as: {name}."
    name_match = re.search(r'Logged in as:\s*(.+?)\.', account_context)
    if name_match:
        tokens.add(name_match.group(1).strip())
    reply_lower = reply_text.lower()
    return any(tok and len(tok) >= 3 and tok.lower() in reply_lower for tok in tokens)


def save_from_chat(question, answer, account_context=None, had_attachment=False,
                    user=None, session_key=''):
    """Saves a real question+answer pair from ANY model's chat (not just
    Light) so the whole site's conversation history feeds Light over time.
    Skips near-empty questions entirely. A turn that had a file/image
    attached, or whose answer leaked this specific user's own account
    details (see _account_context_leaked), is still saved — just scoped
    private to that one user (or guest session, via session_key) instead of
    shared, since uploaded content or personal account data has no business
    being retrievable by anyone else's Light-mode question. Silently a
    no-op if there's genuinely nowhere safe to save it — callers don't need
    to branch on this themselves."""
    question = (question or '').strip()
    answer = (answer or '').strip()
    if len(question) < CHAT_SAVE_MIN_MESSAGE_CHARS or not answer:
        return

    is_authenticated = user is not None and getattr(user, 'is_authenticated', False)
    private = had_attachment or _account_context_leaked(account_context, answer)

    entry_user = None
    entry_session_key = ''
    if private:
        if is_authenticated:
            entry_user = user
        elif session_key:
            entry_session_key = session_key
        else:
            # Nothing to scope a private entry to — safer to drop it than
            # accidentally save it shared.
            return

    KnowledgeEntry.objects.create(
        topic=question[:CHAT_SAVE_TOPIC_MAX_CHARS],
        content=answer[:CHAT_SAVE_CONTENT_MAX_CHARS],
        source=KnowledgeEntry.SOURCE_CHAT,
        user=entry_user,
        session_key=entry_session_key,
    )
