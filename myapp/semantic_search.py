"""Optional local embedding-based retrieval for the AI knowledge base."""
_model = None


def rank(query, entries, limit=3):
    entries = list(entries)
    if not query or not entries:
        return []
    global _model
    try:
        if _model is None:
            from sentence_transformers import SentenceTransformer
            _model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
        documents = [f"{entry.topic}\n{entry.content}" for entry in entries]
        query_vector = _model.encode_query(query, normalize_embeddings=True)
        vectors = _model.encode_document(documents, normalize_embeddings=True)
        scores = vectors @ query_vector
        order = scores.argsort()[::-1][:limit]
        return [entries[int(i)] for i in order if float(scores[int(i)]) >= 0.25]
    except Exception:
        # A TF-IDF similarity fallback provides useful local retrieval when
        # the embedding model has not been downloaded on this deployment.
        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
            from sklearn.metrics.pairwise import cosine_similarity
            documents = [f"{entry.topic}\n{entry.content}" for entry in entries]
            matrix = TfidfVectorizer(ngram_range=(1, 2), stop_words='english').fit_transform([query] + documents)
            scores = cosine_similarity(matrix[0:1], matrix[1:]).ravel()
            order = scores.argsort()[::-1][:limit]
            return [entries[int(i)] for i in order if float(scores[int(i)]) >= 0.08]
        except Exception:
            return []
