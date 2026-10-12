from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from .models import Article, ArticleEditEvent, ArticlePresence


class ArticleCollaborationConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.article_id = int(self.scope['url_route']['kwargs']['article_id'])
        self.group_name = f'article-collaboration-{self.article_id}'
        if not await self.can_access_article():
            await self.close(code=4403)
            return
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        await self.send_json({'type': 'connected', 'article_id': self.article_id})

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)
        if hasattr(self, 'article_id') and self.scope.get('user', None) and self.scope['user'].is_authenticated:
            await self.remove_presence()

    async def receive_json(self, content, **kwargs):
        if content.get('type') not in {'presence', 'selection_changed', 'content_changed', 'comment_added'}:
            await self.send_json({'type': 'error', 'detail': 'Unsupported collaboration event.'})
            return
        payload = content.get('payload', {})
        if not isinstance(payload, dict):
            await self.send_json({'type': 'error', 'detail': 'payload must be an object.'})
            return
        presence = await self.update_presence(content)
        event = None if content['type'] == 'presence' else await self.create_event(content['type'], payload)
        await self.channel_layer.group_send(self.group_name, {'type': 'collaboration.message', 'presence': presence, 'event': event})

    async def collaboration_message(self, event):
        await self.send_json({'type': 'collaboration', 'presence': event['presence'], 'event': event['event']})

    @database_sync_to_async
    def can_access_article(self):
        user = self.scope.get('user')
        article = Article.objects.filter(pk=self.article_id).first()
        return bool(user and user.is_authenticated and article and (article.author_id == user.id or user.role in {'Editor', 'Admin'}))

    @database_sync_to_async
    def update_presence(self, content):
        session, _ = ArticlePresence.objects.update_or_create(article_id=self.article_id, user=self.scope['user'], defaults={
            'status': content.get('status', 'editing'), 'section': str(content.get('section', ''))[:80],
            'cursor_position': max(0, int(content.get('cursor_position', 0))),
        })
        return {'user_id': session.user_id, 'username': session.user.username, 'status': session.status, 'section': session.section, 'cursor_position': session.cursor_position}

    @database_sync_to_async
    def create_event(self, event_type, payload):
        event = ArticleEditEvent.objects.create(article_id=self.article_id, user=self.scope['user'], event_type=event_type, payload=payload)
        return {'id': event.id, 'user_id': event.user_id, 'username': event.user.username, 'event_type': event.event_type, 'payload': event.payload, 'created_at': event.created_at.isoformat()}

    @database_sync_to_async
    def remove_presence(self):
        ArticlePresence.objects.filter(article_id=self.article_id, user=self.scope['user']).delete()
