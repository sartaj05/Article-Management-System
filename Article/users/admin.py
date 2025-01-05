# admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import Permission
from django.utils.safestring import mark_safe
from .models import CustomUser, Profile
from django.conf import settings

# Customizing the admin panel for CustomUser
@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    model = CustomUser
    list_display = ['username', 'email', 'role', 'is_active', 'is_staff', 'is_superuser']
    list_filter = ['role', 'is_active', 'is_staff']
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Personal Info', {'fields': ('first_name', 'last_name', 'email')}),
        ('Roles & Permissions', {'fields': ('role', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important Dates', {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'role', 'password1', 'password2'),
        }),
    )
    search_fields = ['username', 'email']
    ordering = ['username']
    filter_horizontal = ['groups', 'user_permissions']

    # Custom action to deactivate multiple users
    @admin.action(description="Deactivate selected users")
    def deactivate_users(self, request, queryset):
        queryset.update(is_active=False)
    
    actions = [deactivate_users]


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    model = Profile
    list_display = ['user', 'bio', 'contact_info', 'profile_picture_preview']
    search_fields = ['user__username', 'bio']
    list_filter = ['user__role']  # Correct way to filter by role in CustomUser

    # Custom actions for assigning permissions
    @admin.action(description="Assign 'View Profile' permission to selected users")
    def assign_view_permission(self, request, queryset):
        try:
            permission = Permission.objects.get(codename='view_profile')
        except Permission.DoesNotExist:
            self.message_user(request, "Permission 'view_profile' does not exist.")
            return
        for profile in queryset:
            profile.user.user_permissions.add(permission)

    @admin.action(description="Assign 'Change Profile' permission to selected users")
    def assign_change_permission(self, request, queryset):
        try:
            permission = Permission.objects.get(codename='change_profile')
        except Permission.DoesNotExist:
            self.message_user(request, "Permission 'change_profile' does not exist.")
            return
        for profile in queryset:
            profile.user.user_permissions.add(permission)

    actions = ['assign_view_permission', 'assign_change_permission']

    # Method to show profile picture preview in the admin list view
    def profile_picture_preview(self, obj):
        if obj.profile_picture:
            return mark_safe(f'<img src="{obj.profile_picture.url}" width="50" height="50" />')
        return "No image"
    profile_picture_preview.short_description = 'Profile Picture'
