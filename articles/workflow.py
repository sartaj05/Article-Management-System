WORKFLOW_STEPS = (
    ('draft', 'Draft'),
    ('submitted', 'Submitted'),
    ('approved', 'Approved'),
    ('published', 'Published'),
)


def workflow_steps(article):
    """Return a UI-friendly progress model for the editorial state machine."""

    current = article.workflow_status
    if current == 'rejected':
        return [
            {'key': key, 'label': label, 'state': 'rejected' if key == 'submitted' else ('complete' if key == 'draft' else 'upcoming')}
            for key, label in WORKFLOW_STEPS
        ]

    active_index = next((index for index, (key, _) in enumerate(WORKFLOW_STEPS) if key == current), 0)
    return [
        {
            'key': key,
            'label': label,
            'state': 'complete' if index < active_index else ('current' if index == active_index else 'upcoming'),
        }
        for index, (key, label) in enumerate(WORKFLOW_STEPS)
    ]


def available_actions(article, user):
    """Return only actions valid for the current user and workflow state."""

    if not getattr(user, 'is_authenticated', False):
        return []

    actions = []
    is_manager = user.role in {'Editor', 'Admin'}
    is_author = article.author_id == user.id
    if is_author and article.workflow_status in {'draft', 'rejected'}:
        actions.append('submit')
    if is_manager and article.workflow_status == 'submitted':
        actions.append('review')
    if is_manager and article.workflow_status == 'approved':
        actions.extend(['publish', 'schedule'])
    if is_manager and article.scheduled_publish_at:
        actions.append('unschedule')
    return actions
