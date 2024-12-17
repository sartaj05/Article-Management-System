from django.contrib import admin
from .models import Article, Tag, Category

@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)

@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = ('title', 'author', 'status', 'review_status', 'category', 'publish_date', 'is_visible')
    list_filter = ('status', 'review_status', 'category', 'is_visible', 'publish_date')
    search_fields = ('title', 'subtitle', 'author_name', 'email', 'tags__name')
    autocomplete_fields = ('tags',)
    readonly_fields = ('created_at', 'updated_at')
    filter_horizontal = ('tags',)
    date_hierarchy = 'publish_date'
    
    actions = ['mark_as_published', 'mark_as_draft', 'mark_as_approved', 'mark_as_rejected']

    fieldsets = (
        ('Content', {
            'fields': ('title', 'subtitle', 'content', 'summary', 'image'),
        }),
        ('Author Details', {
            'fields': ('author', 'author_name', 'email'),
        }),
        ('Categorization & Status', {
            'fields': ('tags', 'category', 'status', 'review_status', 'is_visible'),
        }),
        ('Publishing Details', {
            'fields': ('publish_date', 'agreed_to_terms'),
        }),
        ('Additional Details', {
            'fields': ('created_at', 'updated_at'),
        }),
    )

    def mark_as_published(self, request, queryset):
        count = queryset.update(status='published', review_status='approved', is_visible=True)
        self.message_user(request, f"{count} selected articles marked as Published.")
    mark_as_published.short_description = "Mark selected articles as Published"

    def mark_as_draft(self, request, queryset):
        count = queryset.update(status='draft', is_visible=False)
        self.message_user(request, f"{count} selected articles marked as Draft.")
    mark_as_draft.short_description = "Mark selected articles as Draft"

    def mark_as_approved(self, request, queryset):
        count = queryset.update(review_status='approved')
        self.message_user(request, f"{count} selected articles marked as Approved.")
    mark_as_approved.short_description = "Mark selected articles as Approved"

    def mark_as_rejected(self, request, queryset):
        count = queryset.update(review_status='rejected', is_visible=False)
        self.message_user(request, f"{count} selected articles marked as Rejected.")
    mark_as_rejected.short_description = "Mark selected articles as Rejected"

# Register the Category model
@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name',)  # Display the category name in the list
    search_fields = ('name',)  # Allow search by category name
