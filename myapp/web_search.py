"""Thin wrapper around the Tavily search API — the live web-search fallback
for EduTrellis Light. NVIDIA's chat completions endpoint has no browsing
capability of its own; this is the separate piece that actually reaches the
internet, and its results get handed to the model as plain text context.
"""
import requests
from django.conf import settings

TAVILY_URL = 'https://api.tavily.com/search'
_TIMEOUT = 7


class SearchError(Exception):
    pass


def search(query, max_results=5):
    if not settings.TAVILY_API_KEY:
        raise SearchError('Web search is not configured.')
    try:
        resp = requests.post(
            TAVILY_URL,
            json={
                'api_key': settings.TAVILY_API_KEY,
                'query': query,
                'max_results': max_results,
                'search_depth': 'basic',
            },
            timeout=_TIMEOUT,
        )
    except requests.RequestException as e:
        raise SearchError(f'Could not reach the search service: {e}')
    if resp.status_code != 200:
        raise SearchError(f'Search failed (HTTP {resp.status_code}).')
    data = resp.json()
    return [
        {'title': r.get('title', ''), 'url': r.get('url', ''), 'content': r.get('content', '')}
        for r in data.get('results', []) if r.get('content')
    ]
