import re


def _hex_rgb(value):
    value = value.lstrip('#')
    if len(value) == 3:
        value = ''.join(character * 2 for character in value)
    if len(value) != 6:
        return None
    try:
        return tuple(int(value[index:index + 2], 16) / 255 for index in (0, 2, 4))
    except ValueError:
        return None


def _relative_luminance(rgb):
    channels = [channel / 12.92 if channel <= .03928 else ((channel + .055) / 1.055) ** 2.4 for channel in rgb]
    return .2126 * channels[0] + .7152 * channels[1] + .0722 * channels[2]


def _contrast_ratio(foreground, background):
    first = _hex_rgb(foreground)
    second = _hex_rgb(background)
    if not first or not second:
        return None
    lighter, darker = sorted((_relative_luminance(first), _relative_luminance(second)), reverse=True)
    return round((lighter + .05) / (darker + .05), 2)


def analyze_article_accessibility(article):
    """Run lightweight, dependency-free checks over article content."""
    content = article.content or ''
    issues = []

    image_tags = re.findall(r'<img\b[^>]*>', content, flags=re.IGNORECASE)
    missing_alt = [tag for tag in image_tags if not re.search(r'\balt\s*=\s*["\']\s*[^"\']+?["\']', tag, flags=re.IGNORECASE)]
    alt_text_suggestions = []
    for tag in missing_alt:
        source = re.search(r'\bsrc\s*=\s*["\']([^"\']+)', tag, flags=re.IGNORECASE)
        filename = (source.group(1).rsplit('/', 1)[-1] if source else 'this image').rsplit('.', 1)[0].replace('-', ' ').replace('_', ' ')
        alt_text_suggestions.append({'source': filename, 'suggestion': f'Describe the purpose of {filename} for someone who cannot see it.'})
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

    contrast_issues = []
    for foreground, background in re.findall(r'(?:color\s*:\s*#([0-9a-f]{3,6})).*?(?:background(?:-color)?\s*:\s*#([0-9a-f]{3,6}))', content, flags=re.IGNORECASE | re.DOTALL):
        ratio = _contrast_ratio(foreground, background)
        if ratio is not None and ratio < 4.5:
            contrast_issues.append({'foreground': f'#{foreground}', 'background': f'#{background}', 'ratio': ratio, 'message': 'Text contrast is below WCAG AA for normal text.'})
    if contrast_issues:
        issues.append({'code': 'color_contrast', 'severity': 'warning', 'message': f'{len(contrast_issues)} color pair(s) may fail WCAG AA contrast.'})

    error_count = sum(issue['severity'] == 'error' for issue in issues)
    warning_count = sum(issue['severity'] == 'warning' for issue in issues)
    score = max(0, 100 - (error_count * 30) - (warning_count * 15))
    return {
        'score': score,
        'passed': not error_count,
        'errors': error_count,
        'warnings': warning_count,
        'issues': issues,
        'wcag': '2.2 AA heuristic scan',
        'alt_text_suggestions': alt_text_suggestions,
        'contrast_issues': contrast_issues,
    }
