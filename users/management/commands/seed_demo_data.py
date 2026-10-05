from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from articles.models import Article, Category, Tag
from users.models import CustomUser, Workspace, WorkspaceMembership


DEMO_USERS = {
    "journalist": {
        "username": "demo_journalist",
        "email": "demo.journalist@example.com",
        "password": "DemoJournalist123!",
        "role": "Journalist",
        "first_name": "Demo",
        "last_name": "Journalist",
    },
    "editor": {
        "username": "demo_editor",
        "email": "demo.editor@example.com",
        "password": "DemoEditor123!",
        "role": "Editor",
        "first_name": "Demo",
        "last_name": "Editor",
    },
    "admin": {
        "username": "demo_admin",
        "email": "demo.admin@example.com",
        "password": "DemoAdmin123!",
        "role": "Admin",
        "first_name": "Demo",
        "last_name": "Admin",
        "is_staff": True,
    },
}


class Command(BaseCommand):
    help = "Create or refresh local demo users, workspace data, and articles."

    @transaction.atomic
    def handle(self, *args, **options):
        users = {}
        for key, data in DEMO_USERS.items():
            user, _ = CustomUser.objects.get_or_create(
                username=data["username"],
                defaults={
                    field: value
                    for field, value in data.items()
                    if field not in {"username", "password"}
                },
            )
            for field, value in data.items():
                if field not in {"username", "password"}:
                    setattr(user, field, value)
            user.set_password(data["password"])
            user.checkbox = True
            user.save()
            users[key] = user

        workspace, _ = Workspace.objects.get_or_create(
            slug="demo-newsroom",
            defaults={
                "name": "Demo Newsroom",
                "description": "Sample workspace for testing editorial workflows.",
                "owner": users["editor"],
            },
        )
        if workspace.owner_id != users["editor"].id:
            workspace.owner = users["editor"]
            workspace.save(update_fields=["owner", "updated_at"])

        WorkspaceMembership.objects.update_or_create(
            workspace=workspace,
            user=users["editor"],
            defaults={"role": "owner"},
        )
        WorkspaceMembership.objects.update_or_create(
            workspace=workspace,
            user=users["journalist"],
            defaults={"role": "writer"},
        )
        WorkspaceMembership.objects.update_or_create(
            workspace=workspace,
            user=users["admin"],
            defaults={"role": "admin"},
        )

        categories = {
            "news": "Current events and newsroom updates.",
            "opinion": "Analysis, commentary, and informed perspectives.",
            "features": "Long-form stories and human-interest reporting.",
        }
        for name, description in categories.items():
            Category.objects.get_or_create(
                slug=name,
                defaults={"name": name.title(), "description": description},
            )

        for name in ("tech", "political", "entertainment"):
            Tag.objects.get_or_create(name=name.title())

        now = timezone.now()
        today = timezone.localdate()
        article_data = [
            {
                "slug": "demo-digital-newsroom",
                "title": "How a Digital Newsroom Builds Trust",
                "subtitle": "A practical look at clear, responsible publishing.",
                "content": (
                    "A modern newsroom earns trust through transparent reporting, "
                    "careful editing, and useful context. This sample article lets "
                    "you preview the published reader experience."
                ),
                "category": "news",
                "tags": "tech,political",
                "publish_date": today - timedelta(days=2),
                "status": "published",
                "review_status": "approved",
                "workflow_status": "published",
                "is_visible": True,
                "is_featured": True,
                "featured_at": now - timedelta(days=2),
                "published_at": now - timedelta(days=2),
                "author": users["journalist"],
                "author_name": "Demo Journalist",
                "email": users["journalist"].email,
                "agreed_to_terms": True,
            },
            {
                "slug": "demo-editorial-workflow",
                "title": "A Better Editorial Workflow",
                "subtitle": "Small process improvements for stronger stories.",
                "content": (
                    "Good editorial systems make collaboration visible without "
                    "slowing writers down. Use this draft to test editing, review, "
                    "assignment, and approval screens."
                ),
                "category": "opinion",
                "tags": "tech",
                "publish_date": today + timedelta(days=7),
                "status": "draft",
                "review_status": "pending",
                "workflow_status": "draft",
                "is_visible": False,
                "author": users["journalist"],
                "author_name": "Demo Journalist",
                "email": users["journalist"].email,
                "agreed_to_terms": True,
            },
            {
                "slug": "demo-community-reporting",
                "title": "Community Reporting Starts Local",
                "subtitle": "A submitted story for the editor review queue.",
                "content": (
                    "This sample submission is ready for an editor to review. "
                    "It demonstrates a pending workflow item in the editorial "
                    "workspace."
                ),
                "category": "features",
                "tags": "political",
                "publish_date": today + timedelta(days=14),
                "status": "draft",
                "review_status": "pending",
                "workflow_status": "submitted",
                "is_visible": False,
                "submitted_at": now - timedelta(hours=3),
                "author": users["journalist"],
                "author_name": "Demo Journalist",
                "email": users["journalist"].email,
                "agreed_to_terms": True,
            },
        ]

        for data in article_data:
            slug = data.pop("slug")
            Article.all_objects.update_or_create(slug=slug, defaults=data)

        self.stdout.write(self.style.SUCCESS("Demo data is ready."))
        self.stdout.write("Login accounts:")
        for key in ("journalist", "editor", "admin"):
            account = DEMO_USERS[key]
            self.stdout.write(
                f"  {account['role']}: {account['username']} / {account['password']}"
            )
        self.stdout.write("Sample workspace: Demo Newsroom")
        self.stdout.write("Sample articles created: 3")
