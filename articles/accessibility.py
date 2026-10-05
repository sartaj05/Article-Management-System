import re


def analyze_article_accessibility(article):
    """Run lightweight, dependency-free checks over article content."""
    content = article.content or ''
    issues = []

    image_tags = re.findall(r'<img\b[^>]*>', content, flags=re.IGNORECASE)
    missing_alt = [tag for tag in image_tags if not re.search(r'\balt\s*=\s*["\']\s*[^"\']+?["\']', tag, flags=re.IGNORECASE)]
    if missing_alt:
        issues.append({
            'code': 'missing_image_alt',
            'severity': 'error',
            'message': f'{len(missing_alt)} image(s) need meaningful alt text.',
        })

    heading_levels = [int(level) for level in re.findall(r'<h([1-6])\b', content, flags=re.IGNORECASE)]
    if any(current - previous > 1 for previous, current in zip(heading_levels, heading_levels[1:])):
        issues.append({
            'code': 'heading_order',
            'severity': 'warning',
            'message': 'Heading levels should not skip levels.',
        })

    empty_links = re.findall(r'<a\b([^>]*)>\s*</a>', content, flags=re.IGNORECASE)
    if empty_links:
        issues.append({
            'code': 'empty_link',
            'severity': 'error',
            'message': f'{len(empty_links)} link(s) have no accessible text.',
        })

    if not (article.summary or '').strip():
        issues.append({
            'code': 'missing_summary',
            'severity': 'warning',
            'message': 'Add a summary so readers and assistive technologies get useful context.',
        })

    error_count = sum(issue['severity'] == 'error' for issue in issues)
    warning_count = sum(issue['severity'] == 'warning' for issue in issues)
    score = max(0, 100 - (error_count * 30) - (warning_count * 15))
    return {
        'score': score,
        'passed': not error_count,
        'errors': error_count,
        'warnings': warning_count,
        'issues': issues,
    }
