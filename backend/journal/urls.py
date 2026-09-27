"""Routes for the citizen-journalism layer, mounted under /api/journal/.

Mounted as a sub-path rather than at the root of /api/ so that every existing
/api/ route keeps working untouched.
"""

from django.urls import path

from . import views

urlpatterns = [
    path("posts/", views.posts, name="journal-posts"),
    path("posts/trending/", views.trending, name="journal-trending"),
    path("posts/<int:post_id>/", views.post_detail, name="journal-post-detail"),
    path("posts/<int:post_id>/like/", views.post_like, name="journal-post-like"),
    path("posts/<int:post_id>/share/", views.post_share, name="journal-post-share"),
    path("posts/<int:post_id>/view/", views.post_view, name="journal-post-view"),
    path("posts/<int:post_id>/comments/", views.post_comments, name="journal-post-comments"),
    path("feed/", views.feed, name="journal-feed"),
    path("comments/", views.comments, name="journal-comments"),
    path("comments/<int:comment_id>/", views.comment_detail, name="journal-comment-detail"),
    path("comments/<int:comment_id>/like/", views.comment_like, name="journal-comment-like"),
    path("search/", views.search, name="journal-search"),
    path("stats/", views.stats, name="journal-stats"),
    path("flags/", views.flags, name="journal-flags"),
    path("admin/flags/", views.admin_flags, name="journal-admin-flags"),
    path("journalist/apply/", views.journalist_apply, name="journal-journalist-apply"),
    path("admin/journalists/", views.admin_journalists, name="journal-admin-journalists"),
    path("me/posts/", views.my_posts, name="journal-my-posts"),
    path("me/analytics/", views.my_analytics, name="journal-my-analytics"),
]
