from django.contrib import admin

from .models import (Comment, JournalistVerification, Like, ModerationFlag, Post,
                     PostAnalytics, Share)


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "city", "category", "status", "author_name", "created_at")
    list_filter = ("status", "category", "city")
    search_fields = ("title", "body", "author_name", "author__username")
    readonly_fields = ("created_at", "updated_at")
    actions = ("publish_posts", "reject_posts")

    @admin.action(description="Publish selected posts")
    def publish_posts(self, request, queryset):
        self.message_user(request, f"Published {queryset.update(status=Post.PUBLISHED)} post(s).")

    @admin.action(description="Reject selected posts")
    def reject_posts(self, request, queryset):
        self.message_user(request, f"Rejected {queryset.update(status=Post.REJECTED)} post(s).")


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ("id", "post", "author_name", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("body", "author_name")
    readonly_fields = ("created_at",)


@admin.register(ModerationFlag)
class ModerationFlagAdmin(admin.ModelAdmin):
    list_display = ("id", "reason", "status", "post", "comment", "handled_by", "created_at")
    list_filter = ("status", "reason")
    search_fields = ("details", "reporter_email")
    readonly_fields = ("created_at", "handled_at")
    actions = ("resolve_flags",)

    @admin.action(description="Mark selected reports as actioned")
    def resolve_flags(self, request, queryset):
        self.message_user(request, f"Resolved {queryset.update(status=ModerationFlag.RESOLVED)} report(s).")


@admin.register(JournalistVerification)
class JournalistVerificationAdmin(admin.ModelAdmin):
    list_display = ("user", "outlet", "status", "reviewed_by", "reviewed_at", "created_at")
    list_filter = ("status",)
    search_fields = ("user__username", "outlet", "statement")
    readonly_fields = ("created_at", "reviewed_at")
    actions = ("approve_applications",)

    @admin.action(description="Approve selected applications")
    def approve_applications(self, request, queryset):
        self.message_user(request, f"Approved {queryset.update(status=JournalistVerification.APPROVED)} application(s).")


@admin.register(Like)
class LikeAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "post", "comment", "created_at")
    list_filter = ("created_at",)
    search_fields = ("user__username",)


@admin.register(Share)
class ShareAdmin(admin.ModelAdmin):
    list_display = ("id", "post", "channel", "user", "created_at")
    list_filter = ("channel",)
    search_fields = ("post__title",)


@admin.register(PostAnalytics)
class PostAnalyticsAdmin(admin.ModelAdmin):
    list_display = ("post", "views", "last_viewed_at")
    search_fields = ("post__title",)
