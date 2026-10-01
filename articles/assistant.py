import re
from collections import Counter


STOP_WORDS = {
    'about', 'after', 'again', 'against', 'because', 'before', 'being', 'between', 'could',
    'from', 'have', 'into', 'more', 'other', 'over', 'said', 'some', 'than', 'that',
    'their', 'there', 'these', 'they', 'this', 'through', 'under', 'very', 'what', 'when',
    'where', 'which', 'while', 'with', 'would', 'your', 'will', 'were', 'also', 'only',
}


def sentences(text):
    return [part.strip() for part in re.split(r'(?<=[.!?])\s+', text.strip()) if part.strip()]


def make_summary(content, limit=420):
    selected = ' '.join(sentences(content)[:2])
    if len(selected) <= limit:
        return selected
    return selected[:limit].rsplit(' ', 1)[0] + '…'


def make_headlines(article):
    base = article.title.strip().rstrip('.!?')
    first_sentence = sentences(article.content)[0] if sentences(article.content) else base
    topic = first_sentence[:70].rstrip(' ,.;:')
    return [base, f"What to know about {topic.lower()}", f"A closer look at {topic}"]


def make_keywords(article):
    words = re.findall(r"[A-Za-z][A-Za-z'-]{3,}", f'{article.title} {article.content}'.lower())
    counts = Counter(word for word in words if word not in STOP_WORDS)
    return [word for word, _ in counts.most_common(8)]


def make_suggestions(article, action):
    if action == 'summarize':
        return {'summary': make_summary(article.content)}
    if action == 'headline':
        return {'headlines': make_headlines(article)}
    if action == 'seo':
        summary = make_summary(article.content, 155)
        return {
            'meta_title': article.title[:60],
            'meta_description': summary,
            'seo_keywords': ', '.join(make_keywords(article)),
        }
    if action == 'proofread':
        cleaned = re.sub(r'\s+', ' ', article.content).strip()
        cleaned = re.sub(r'\s+([,.!?])', r'\1', cleaned)
        return {'content': cleaned}
    raise ValueError('Supported actions are summarize, headline, seo, and proofread.')
