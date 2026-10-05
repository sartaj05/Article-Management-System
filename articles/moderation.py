import re


HIGH_RISK_PHRASES = ('free money', 'buy followers', 'guaranteed profit', 'click here to win')
MEDIUM_RISK_PHRASES = ('click here', 'limited time offer', 'act now')
COMMENT_RISK_PHRASES = ('buy now', 'free money', 'guaranteed profit', 'click here to win', 'visit my channel')


def moderate_text(title, content):
    text = f'{title} {content}'.lower()
    flags = []
    for phrase in HIGH_RISK_PHRASES:
        if phrase in text:
            flags.append({'flag_type': 'prohibited_promotion', 'severity': 'high', 'message': f'High-risk promotional phrase detected: {phrase}.', 'matched_text': phrase})
    for phrase in MEDIUM_RISK_PHRASES:
        if phrase in text and phrase not in HIGH_RISK_PHRASES:
            flags.append({'flag_type': 'spam_signal', 'severity': 'medium', 'message': f'Promotional language detected: {phrase}.', 'matched_text': phrase})
    if len(re.findall(r'https?://', text)) > 5:
        flags.append({'flag_type': 'link_spam', 'severity': 'medium', 'message': 'Article contains an unusually high number of links.', 'matched_text': ''})
    return flags


def moderate_comment(content):
    text = content.lower()
    return [phrase for phrase in COMMENT_RISK_PHRASES if phrase in text]
