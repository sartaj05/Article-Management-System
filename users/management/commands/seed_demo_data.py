from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from articles.models import (
    Article,
    ArticleAssignment,
    ArticleEngagementEvent,
    ArticleView,
    AuditLog,
    Category,
    DistributionJob,
    EditorialComment,
    Notification,
    Tag,
    WorkflowRule,
    WorkspaceApprovalPolicy,
    WorkspaceReliabilityPolicy,
)
from users.models import (
    CustomUser,
    Workspace,
    WorkspaceMembership,
)


DEMO_WORKSPACE_NAME = "Northstar Newsroom"

DEMO_USERS = {
    "journalist": {
        "username": "demo_journalist",
        "email": "maya.chen@northstarnewsroom.example",
        "password": "DemoJournalist123!",
        "role": "Journalist",
        "first_name": "Maya",
        "last_name": "Chen",
        "is_staff": False,
    },
    "editor": {
        "username": "demo_editor",
        "email": "rafael.okafor@northstarnewsroom.example",
        "password": "DemoEditor123!",
        "role": "Editor",
        "first_name": "Rafael",
        "last_name": "Okafor",
        "is_staff": False,
    },
    "admin": {
        "username": "demo_admin",
        "email": "priya.nair@northstarnewsroom.example",
        "password": "DemoAdmin123!",
        "role": "Admin",
        "first_name": "Priya",
        "last_name": "Nair",
        "is_staff": True,
    },
}


class Command(BaseCommand):
    help = "Create or refresh a realistic, deterministic client newsroom workspace."

    @transaction.atomic
    def handle(self, *args, **options):
        users = {}
        for key, data in DEMO_USERS.items():
            user, _ = CustomUser.objects.get_or_create(
                username=data["username"],
                defaults={field: value for field, value in data.items() if field not in {"username", "password"}},
            )
            for field, value in data.items():
                if field != "password":
                    setattr(user, field, value)
            user.set_password(data["password"])
            user.checkbox = True
            user.save()
            users[key] = user

        workspace, _ = Workspace.objects.get_or_create(
            slug="demo-newsroom",
            defaults={
                "name": DEMO_WORKSPACE_NAME,
                "description": "A regional newsroom covering people, policy, and practical change.",
                "owner": users["editor"],
            },
        )
        workspace.name = DEMO_WORKSPACE_NAME
        workspace.description = "A regional newsroom covering people, policy, and practical change."
        workspace.owner = users["editor"]
        workspace.save(update_fields=["name", "description", "owner", "updated_at"])

        for user, role in ((users["editor"], "owner"), (users["journalist"], "writer"), (users["admin"], "admin")):
            WorkspaceMembership.objects.update_or_create(workspace=workspace, user=user, defaults={"role": role})

        WorkspaceApprovalPolicy.objects.update_or_create(
            workspace=workspace,
            defaults={"require_dual_publish": True, "require_dual_billing": True},
        )
        WorkspaceReliabilityPolicy.objects.update_or_create(
            workspace=workspace,
            defaults={
                "rto_minutes": 60,
                "rpo_minutes": 15,
                "backup_region": "eu-west-1",
                "restore_verified_at": timezone.now() - timedelta(hours=5),
                "status_page_enabled": True,
            },
        )

        WorkflowRule.objects.filter(workspace=workspace).delete()
        WorkflowRule.objects.bulk_create([
            WorkflowRule(
                workspace=workspace,
                name="Editorial review before publish",
                from_status="submitted",
                to_status="approved",
                required_role="Editor",
                require_sources=True,
                require_fact_check=True,
            ),
            WorkflowRule(
                workspace=workspace,
                name="Approved stories enter distribution",
                from_status="approved",
                to_status="published",
                required_role="Editor",
                auto_assign_role="Editor",
            ),
        ])

        categories = {
            "news": ("News", "Verified reporting on the decisions shaping the region."),
            "opinion": ("Opinion", "Ideas and analysis from people close to the story."),
            "features": ("Features", "Human-centred reporting with time to breathe."),
        }
        category_objects = {}
        for slug, (name, description) in categories.items():
            category_objects[slug], _ = Category.objects.update_or_create(
                slug=slug,
                defaults={"name": name, "description": description},
            )

        tag_objects = {}
        for name in ("Tech", "Political", "Entertainment"):
            tag_objects[name.lower()], _ = Tag.objects.get_or_create(name=name)

        Article.all_objects.filter(workspace=workspace).delete()
        Article.all_objects.filter(slug__in=["demo-digital-newsroom", "demo-editorial-workflow", "demo-community-reporting"]).delete()
        Notification.objects.filter(recipient__in=list(users.values())).delete()
        AuditLog.objects.filter(workspace=workspace).delete()

        now = timezone.now()
        today = timezone.localdate()
        stories = [
            {
                "slug": "northstar-main-street-rebuild",
                "title": "The Quiet Rebuild of Main Street",
                "subtitle": "What renewal looks like block by block",
                "category": "features",
                "tags": "political,entertainment",
                "content": "On a grey Tuesday morning, the first signs of change are easy to miss: a bakery reopening its side entrance, a new bus shelter waiting for glass, and a small brass plaque outside the library. Together, they tell the story of a neighbourhood rebuilding itself without losing its character.\n\nNorthstar spoke with shop owners, planners, and residents about the choices behind the renewal and the work still ahead.",
                "summary": "A neighbourhood-by-neighbourhood look at how Main Street is changing without losing its character.",
                "status": "published",
                "workflow_status": "published",
                "review_status": "approved",
                "publish_date": today - timedelta(days=2),
                "published_at": now - timedelta(days=2, hours=3),
                "featured_at": now - timedelta(days=2),
                "is_featured": True,
                "is_visible": True,
                "byline": "Maya Chen",
            },
            {
                "slug": "northstar-river-restoration",
                "title": "Why the River Is Running Clearer",
                "subtitle": "Three years of restoration, measured",
                "category": "news",
                "tags": "political,tech",
                "content": "Water samples collected along the eastern basin show a steady improvement in clarity after three years of restoration work. The change is visible from the footbridge, but the more important story is in the data: fewer overflow events, stronger wetlands, and a return of species that had disappeared from the shallows.\n\nThe recovery is not complete. Scientists and residents say the next test will come during the first heavy autumn storms.",
                "summary": "The data behind a visible improvement in the eastern basin, and the work still required to protect it.",
                "status": "published",
                "workflow_status": "published",
                "review_status": "approved",
                "publish_date": today - timedelta(days=4),
                "published_at": now - timedelta(days=4, hours=2),
                "is_visible": True,
                "byline": "Maya Chen",
            },
            {
                "slug": "northstar-regional-transit-map",
                "title": "A New Map for Regional Transit",
                "subtitle": "The routes connecting work and home",
                "category": "news",
                "tags": "political,tech",
                "content": "A proposed regional transit map would connect the outer districts to three employment corridors before the end of next year. The plan is designed around the journeys people already make, rather than the boundaries on an old planning document.\n\nNorthstar reviewed the proposal, spoke with commuters, and followed one early-morning route from the hill districts to the central station.",
                "summary": "What the proposed regional transit map could change for commuters across the outer districts.",
                "status": "published",
                "workflow_status": "published",
                "review_status": "approved",
                "publish_date": today - timedelta(days=6),
                "published_at": now - timedelta(days=6, hours=5),
                "is_visible": True,
                "is_premium": True,
                "byline": "Maya Chen",
            },
            {
                "slug": "northstar-night-shift",
                "title": "Inside the City’s Night Shift",
                "subtitle": "The people keeping the city moving",
                "category": "features",
                "tags": "entertainment",
                "content": "After midnight, the city becomes a different workplace. A baker starts the first batch, a maintenance crew checks the power lines, and the overnight dispatch team keeps a thousand small promises on schedule.\n\nPhotographer Lena Ortiz spent a week following the people whose work is mostly invisible by daylight.",
                "summary": "A photo-led report on the people who keep the city moving while most of us are asleep.",
                "status": "published",
                "workflow_status": "published",
                "review_status": "approved",
                "publish_date": today - timedelta(days=9),
                "published_at": now - timedelta(days=9, hours=1),
                "is_visible": True,
                "byline": "Maya Chen",
            },
            {
                "slug": "northstar-climate-brief",
                "title": "The Five-Minute Climate Brief",
                "subtitle": "The numbers worth watching this week",
                "category": "news",
                "tags": "tech,political",
                "content": "This week’s climate brief tracks the signals that matter locally: reservoir levels, the urban heat index, and the pace of building retrofits. The headline is encouraging, but uneven. Progress is visible in the centre of the city while older neighbourhoods remain exposed to the same summer risks.\n\nHere is what changed, what did not, and what officials will measure next.",
                "summary": "A concise, evidence-led guide to the climate indicators shaping the week ahead.",
                "status": "draft",
                "workflow_status": "draft",
                "review_status": "pending",
                "publish_date": today + timedelta(days=3),
                "scheduled_publish_at": now + timedelta(days=3, hours=8),
                "is_visible": False,
                "byline": "Maya Chen",
            },
            {
                "slug": "northstar-small-publishers",
                "title": "What Small Publishers Get Right",
                "subtitle": "Trust grows through useful habits",
                "category": "opinion",
                "tags": "tech,political",
                "content": "The strongest small publishers do not try to sound bigger than they are. They explain how a story was reported, correct mistakes in public, and make it easy for readers to ask a better question. Those habits are not a marketing strategy. They are the infrastructure of trust.\n\nA look at the practical systems helping independent newsrooms build lasting reader relationships.",
                "summary": "The transparent editorial habits helping independent publishers build lasting reader relationships.",
                "status": "draft",
                "workflow_status": "submitted",
                "review_status": "pending",
                "publish_date": today + timedelta(days=5),
                "submitted_at": now - timedelta(hours=4),
                "is_visible": False,
                "byline": "Maya Chen",
            },
            {
                "slug": "northstar-longer-lunch",
                "title": "Schools Test a Longer Lunch Break",
                "subtitle": "A small timetable change, closely watched",
                "category": "news",
                "tags": "political",
                "content": "Seven schools are testing a longer lunch break this term, giving pupils more time to eat, move, and return to class ready to learn. The pilot grew from a simple observation: the lunch queue was taking longer than the lunch itself.\n\nTeachers, families, and students are measuring the result in different ways. Northstar will follow the pilot through the winter.",
                "summary": "Seven schools are testing whether a longer lunch can improve the rhythm of the school day.",
                "status": "draft",
                "workflow_status": "approved",
                "review_status": "approved",
                "publish_date": today + timedelta(days=2),
                "scheduled_publish_at": now + timedelta(days=2, hours=4),
                "reviewed_at": now - timedelta(hours=2),
                "reviewed_by": users["editor"],
                "is_visible": False,
                "byline": "Maya Chen",
            },
            {
                "slug": "northstar-public-data-trust",
                "title": "Can Public Data Earn Trust?",
                "subtitle": "Making civic numbers easier to use",
                "category": "opinion",
                "tags": "tech,political",
                "content": "Public data is often published as if availability were the same as access. A spreadsheet can be technically open and still be impossible for a resident to understand. The next generation of civic tools will have to make the source, the limits, and the meaning of a number visible at the same time.\n\nThis column sets out a practical standard for clearer public information.",
                "summary": "Why open data needs context, ownership, and plain language before it can earn public trust.",
                "status": "draft",
                "workflow_status": "submitted",
                "review_status": "pending",
                "publish_date": today + timedelta(days=8),
                "submitted_at": now - timedelta(hours=7),
                "is_visible": False,
                "byline": "Maya Chen",
            },
            {
                "slug": "northstar-better-meetings",
                "title": "A Field Guide to Better Meetings",
                "subtitle": "Five ways to leave with a decision",
                "category": "features",
                "tags": "tech,entertainment",
                "content": "The most productive meeting in the city may be the one that ends ten minutes early. Across local teams, a few simple practices are making decisions clearer: publish the question in advance, name the owner, and leave a written record that people can actually find.\n\nThese are small changes, but they compound quickly when a newsroom is moving at speed.",
                "summary": "Five practical habits that help busy teams make clearer decisions in less time.",
                "status": "draft",
                "workflow_status": "draft",
                "review_status": "pending",
                "publish_date": today + timedelta(days=12),
                "is_visible": False,
                "byline": "Maya Chen",
            },
        ]

        articles = []
        for story in stories:
            story = dict(story)
            slug = story.pop("slug")
            byline = story.pop("byline")
            tags = story["tags"].split(",")
            story.update({
                "workspace": workspace,
                "author": users["journalist"],
                "author_name": byline,
                "email": users["journalist"].email,
                "agreed_to_terms": True,
                "category_ref": category_objects[story["category"]],
                "meta_title": story["title"],
                "meta_description": story["summary"],
                "seo_keywords": ", ".join(tags),
            })
            article = Article.all_objects.create(slug=slug, **story)
            article.tag_objects.set([tag_objects[tag] for tag in tags])
            articles.append(article)

        published = [article for article in articles if article.workflow_status == "published"]
        submitted = [article for article in articles if article.workflow_status == "submitted"]
        approved = [article for article in articles if article.workflow_status == "approved"]

        for article in articles:
            is_done = article.workflow_status == "published"
            ArticleAssignment.objects.update_or_create(
                article=article,
                editor=users["editor"],
                defaults={
                    "can_review": True,
                    "can_edit": not is_done,
                    "can_publish": is_done,
                    "status": "done" if is_done else ("review" if article.workflow_status == "submitted" else "queued"),
                    "priority": "high" if article in submitted else "normal",
                    "due_at": now - timedelta(hours=2) if article in submitted else now + timedelta(days=2),
                    "notes": "Ready for the next editorial handoff." if not is_done else "Published and distributed successfully.",
                },
            )

        comment_assignment = ArticleAssignment.objects.get(article=submitted[0], editor=users["editor"])
        EditorialComment.objects.update_or_create(
            assignment=comment_assignment,
            author=users["editor"],
            body="Please add the latest ridership figure and one commuter perspective before approval.",
            defaults={"mentions": [users["journalist"].username], "status": "open"},
        )

        ArticleView.objects.filter(article__in=articles).delete()
        ArticleEngagementEvent.objects.filter(article__in=articles).delete()
        for index, article in enumerate(published):
            for view_number in range(12 + index * 5):
                ArticleView.objects.create(article=article, user=None)
            for event_number in range(4 + index):
                ArticleEngagementEvent.objects.create(
                    article=article,
                    user=users["journalist"] if event_number % 2 else users["editor"],
                    visitor_key=f"northstar-reader-{index}-{event_number}",
                    session_key=f"northstar-session-{index}-{event_number}",
                    event_type="read_start",
                    created_at=now - timedelta(days=index, hours=event_number),
                )
            for event_number in range(2 + index // 2):
                ArticleEngagementEvent.objects.create(
                    article=article,
                    user=users["journalist"],
                    visitor_key=f"northstar-complete-{index}-{event_number}",
                    session_key=f"northstar-complete-session-{index}-{event_number}",
                    event_type="read_complete",
                    value=100,
                    created_at=now - timedelta(days=index, hours=event_number + 1),
                )
            ArticleEngagementEvent.objects.create(
                article=article,
                user=users["editor"],
                visitor_key=f"northstar-share-{index}",
                session_key=f"northstar-share-session-{index}",
                event_type="share",
                value=1,
                created_at=now - timedelta(days=index),
            )

        DistributionJob.objects.filter(article__in=articles).delete()
        distribution_plan = [
            (published[0], "rss", "delivered"),
            (published[0], "newsletter", "delivered"),
            (published[1], "rss", "delivered"),
            (published[1], "social", "failed"),
            (published[2], "newsletter", "queued"),
            (approved[0], "newsletter", "queued"),
        ]
        for index, (article, channel, status) in enumerate(distribution_plan):
            DistributionJob.objects.create(
                article=article,
                requested_by=users["editor"],
                idempotency_key=f"northstar-{article.slug}-{channel}",
                channel=channel,
                status=status,
                attempts=2 if status == "failed" else (1 if status == "delivered" else 0),
                last_error="Provider timeout; retry is ready." if status == "failed" else "",
                last_attempt_at=now - timedelta(hours=2) if status != "queued" else None,
                scheduled_for=now + timedelta(hours=3) if status == "queued" else None,
                delivered_at=now - timedelta(hours=index + 1) if status == "delivered" else None,
                provider_reference=f"northstar-{channel}-{index}" if status == "delivered" else "",
            )

        notification_data = [
            (users["editor"], submitted[0], "submitted", "A new story is ready for editorial review: A New Map for Regional Transit.", "high", False),
            (users["editor"], submitted[1], "submitted", "The latest opinion draft is waiting for a source review.", "normal", False),
            (users["journalist"], submitted[0], "assignment", "Rafael left a note on your transit story.", "high", False),
            (users["journalist"], published[0], "published", "Your feature is live: The Quiet Rebuild of Main Street.", "normal", True),
            (users["admin"], published[1], "reader_alert", "Distribution needs attention for Why the River Is Running Clearer.", "high", False),
        ]
        for recipient, article, kind, message, priority, is_read in notification_data:
            Notification.objects.create(
                recipient=recipient,
                article=article,
                notification_type=kind,
                message=message,
                action_url="/articles/editor/assignments/" if kind in {"submitted", "assignment"} else "/articles/workspace/monitoring/",
                priority=priority,
                is_read=is_read,
                read_at=now - timedelta(hours=1) if is_read else None,
            )

        failed_distribution = DistributionJob.objects.get(article=published[1], channel="social")
        audit_events = [
            ("workspace_created", "Workspace", workspace.pk, {"name": workspace.name}),
            ("article_published", "Article", published[0].pk, {"title": published[0].title}),
            ("article_published", "Article", published[1].pk, {"title": published[1].title}),
            ("article_submitted", "Article", submitted[0].pk, {"title": submitted[0].title}),
            ("assignment_created", "ArticleAssignment", comment_assignment.pk, {"priority": "high"}),
            ("distribution_job_failed", "DistributionJob", failed_distribution.pk, {"channel": "social"}),
            ("backup_verified", "Workspace", workspace.pk, {"rto_minutes": 60, "rpo_minutes": 15}),
        ]
        for action, target_model, target_id, details in audit_events:
            AuditLog.objects.create(
                actor=users["admin"] if action in {"workspace_created", "backup_verified"} else users["editor"],
                workspace=workspace,
                article=next((article for article in articles if str(article.pk) == str(target_id)), None),
                action=action,
                target_model=target_model,
                target_id=str(target_id),
                details=details,
            )

        self.stdout.write(self.style.SUCCESS("Northstar client newsroom is ready."))
        self.stdout.write("Login accounts:")
        for key in ("journalist", "editor", "admin"):
            account = DEMO_USERS[key]
            self.stdout.write(f"  {account['role']}: {account['username']} / {account['password']}")
        self.stdout.write(f"Workspace: {DEMO_WORKSPACE_NAME}")
        self.stdout.write(f"Stories: {len(articles)} ({len(published)} published, {len(submitted)} in review, {len(approved)} approved)")
