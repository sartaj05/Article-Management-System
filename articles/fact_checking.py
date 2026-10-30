"""Source-grounded claim extraction used by the editorial fact-check workflow."""

import re


def _tokens(value):
    return {token for token in re.findall(r"[a-z0-9]{4,}", (value or '').lower()) if token not in {
        'about', 'after', 'before', 'being', 'could', 'from', 'have', 'into', 'more', 'that',
        'their', 'there', 'these', 'they', 'this', 'through', 'what', 'when', 'which', 'with',
    }}


def _sentences(content):
    return [item.strip() for item in re.split(r'(?<=[.!?])\s+', (content or '').strip()) if len(item.strip()) >= 24]


def make_fact_check_suggestions(article, sources):
    """Return explainable suggestions without claiming that metadata proves a fact.

    The local provider deliberately labels claims unresolved when source metadata
    is insufficient. A remote provider can replace this with a source-grounded
    model response while keeping this output contract.
    """
    source_rows = list(sources or [])
    suggestions = []
    for claim in _sentences(article.content)[:8]:
        claim_tokens = _tokens(claim)
        ranked = []
        for source in source_rows:
            source_text = f"{source.get('title', '')} {source.get('publisher', '')} {source.get('notes', '')}"
            overlap = len(claim_tokens & _tokens(source_text)) / max(len(claim_tokens), 1)
            if overlap:
                ranked.append((overlap, source))
        ranked.sort(key=lambda item: item[0], reverse=True)
        matches = [source for _, source in ranked[:3]]
        best_overlap = ranked[0][0] if ranked else 0
        if not matches:
            verdict, confidence = 'unverified', 0.15
            explanation = 'No supporting source metadata matched this claim.'
            unresolved = True
        elif best_overlap >= 0.35 and any(source.get('source_type') == 'primary' for source in matches):
            verdict, confidence = 'partly_verified', min(0.85, round(0.55 + best_overlap, 2))
            explanation = 'A primary source appears relevant, but the claim still needs editorial verification against the source text.'
            unresolved = True
        else:
            verdict, confidence = 'unverified', min(0.55, round(0.25 + best_overlap, 2))
            explanation = 'Related source metadata was found, but it does not establish the claim by itself.'
            unresolved = True
        suggestions.append({
            'claim': claim,
            'verdict': verdict,
            'confidence': confidence,
            'explanation': explanation,
            'source_ids': [source['id'] for source in matches],
            'source_citations': [
                {'id': source['id'], 'title': source.get('title', ''), 'publisher': source.get('publisher', ''), 'url': source.get('url', ''), 'citation_key': source.get('citation_key', '')}
                for source in matches
            ],
            'unresolved': unresolved,
        })
    return {'claims': suggestions, 'source_count': len(source_rows), 'unresolved_count': sum(item['unresolved'] for item in suggestions)}
