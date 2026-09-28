"""Citizen-journalism endpoints: posts, comments, engagement, moderation.

Same style as ``api.views`` - plain Django function views returning JSON, no
DRF serializers - so the whole backend stays on one convention. Every
mutation returns the ``{"success": ..., "message": ...}`` envelope the
existing frontend client already knows how to read.
"""

import json
from datetime import timedelta

from django.db.models import Count, Exists, OuterRef, Q, Sum
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from api.models import City

from .models import (Comment, JournalistVerification, Like, ModerationFlag, Post,
                     PostAnalytics, Share)

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_BODY_CHARS = 5000
TRENDING_WINDOW_DAYS = 30
# Weights used to rank trending posts; engagement matters more than reads.
TRENDING_WEIGHTS = {"like": 3, "comment": 2, "share": 2, "view": 0.2}


def _json(request):
    try:
        return json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return None


def _payload(request):
    """Read fields from a JSON body or a multipart form, so posts with an
    image work the same way as posts without one."""
    if (request.content_type or "").startswith("multipart/"):
        return request.POST.dict()
    return _json(request) or {}


def _error(message, status=400):
    return JsonResponse({"success": False, "message": message}, status=status)


def _ok(message, code=200, **extra):
    """A success envelope. ``code`` sets the HTTP status; everything else in
    ``extra`` goes in the body, so a caller must not pass ``code`` as data."""
    return JsonResponse({"success": True, "message": message, **extra}, status=code)


def _login_required(request):
    """Return an error response, or None when the request may proceed."""
    if not request.user.is_authenticated:
        return _error("You must be signed in to do that.", status=401)
    return None


def _can_edit(user, post):
    return user.is_authenticated and (user.is_staff or post.author_id == user.id)


def _visible_posts(user, queryset=None):
    """Rejected posts stay visible to staff so they can be reviewed."""
    qs = Post.objects.all() if queryset is None else queryset
    if not getattr(user, "is_staff", False):
        qs = qs.filter(status=Post.PUBLISHED)
    return qs


def _annotate_posts(queryset, viewer=None):
    counts = {
        "like_count": Count("likes", distinct=True),
        "comment_count": Count("comments", filter=Q(comments__status=Comment.PUBLISHED), distinct=True),
        "share_count": Count("shares", distinct=True),
    }
    # `liked` is only annotated for a signed-in viewer; anonymous callers get
    # the False default from _post_payload instead, because annotate() rejects
    # plain literals.
    if viewer is not None and viewer.is_authenticated:
        return queryset.annotate(
            liked=Exists(Like.objects.filter(user=viewer, post=OuterRef("pk"))), **counts)
    return queryset.annotate(**counts)


def _post_payload(post):
    return {
        "id": post.id,
        "title": post.title,
        "body": post.body,
        "category": post.category,
        "city": post.city.name,
        "city_slug": post.city.slug,
        "author": post.display_author,
        "author_verified": post.author_is_verified,
        "status": post.status,
        "image": post.image.url if post.image else None,
        "created_at": post.created_at.isoformat(),
        "updated_at": post.updated_at.isoformat(),
        "like_count": getattr(post, "like_count", 0),
        "comment_count": getattr(post, "comment_count", 0),
        "share_count": getattr(post, "share_count", 0),
        "views": post.analytics.views if hasattr(post, "analytics") else 0,
        "liked": bool(getattr(post, "liked", False)),
    }


def _comment_payload(comment):
    return {
        "id": comment.id,
        "post": comment.post_id,
        "parent": comment.parent_id,
        "body": comment.body,
        "author": comment.display_author,
        "status": comment.status,
        "created_at": comment.created_at.isoformat(),
        "like_count": getattr(comment, "like_count", 0),
        "liked": bool(getattr(comment, "liked", False)),
    }


def _comment_queryset(viewer=None):
    qs = Comment.objects.select_related("author").annotate(like_count=Count("likes", distinct=True))
    if not getattr(viewer, "is_staff", False):
        qs = qs.filter(status=Comment.PUBLISHED)
    if viewer is not None and viewer.is_authenticated:
        return qs.annotate(liked=Exists(Like.objects.filter(user=viewer, comment=OuterRef("pk"))))
    return qs


def _city_for(value):
    """Accept a district by id or by slug/name, the way /api/areas/ does."""
    if value in (None, ""):
        return None
    query = City.objects.filter(slug=str(value).strip())
    if not query.exists():
        query = City.objects.filter(name__iexact=str(value).strip())
    return query.first()


def _int_arg(request, name, default, minimum=1, maximum=100):
    try:
        value = int(request.GET.get(name, default))
    except (TypeError, ValueError):
        return default
    return max(minimum, min(value, maximum))


@csrf_exempt
def posts(request):
    """List posts, newest first, with the usual district/category/author filters."""
    if request.method == "GET":
        qs = _annotate_posts(_visible_posts(request.user), request.user)
        if request.GET.get("city"):
            city = _city_for(request.GET.get("city"))
            qs = qs.filter(city=city) if city else qs.none()
        category = request.GET.get("category", "").strip().upper()
        if category:
            qs = qs.filter(category=category)
        search = request.GET.get("q", "").strip()
        if search:
            qs = qs.filter(Q(title__icontains=search) | Q(body__icontains=search))
        author = request.GET.get("author", "").strip()
        if author:
            qs = qs.filter(Q(author__username__iexact=author) | Q(author_name__iexact=author))
        limit = _int_arg(request, "limit", 20, 1, 50)
        offset = _int_arg(request, "offset", 0, 0, 10000)
        return JsonResponse({"count": qs.count(),
                             "results": [_post_payload(p) for p in qs[offset:offset + limit]]})

    denied = _login_required(request)
    if denied:
        return denied
    if request.method != "POST":
        return _error("Only GET and POST are allowed.", status=405)

    body = _payload(request)
    title = str(body.get("title", "")).strip()
    text = str(body.get("body", "")).strip()
    if not title or len(title) > 200:
        return _error("A title of up to 200 characters is required.")
    if not text or len(text) > MAX_BODY_CHARS:
        return _error(f"Body text of 1 to {MAX_BODY_CHARS} characters is required.")
    city = _city_for(body.get("city"))
    if city is None:
        return _error("A valid district is required.")
    category = str(body.get("category", "GENERAL")).strip().upper()
    if category not in dict(Post.CATEGORY_CHOICES):
        return _error("Unknown category.")
    image = request.FILES.get("image")
    if image and image.size > MAX_UPLOAD_BYTES:
        return _error("Image must be 5 MB or smaller.")

    # Status is deliberately not settable here: moderation happens after the
    # post exists, so the author still sees their own post straight away.
    post = Post.objects.create(
        author=request.user, author_name=str(body.get("author_name", "")).strip()[:120],
        city=city, category=category, title=title, body=text, image=image,
        status=Post.PUBLISHED)
    PostAnalytics.objects.get_or_create(post=post)
    return _ok("Post published.", code=201, post=_post_payload(post))



@csrf_exempt
def post_detail(request, post_id):
    """Read one post, edit it, or delete it. Author and staff may do both."""
    try:
        post = _visible_posts(request.user).get(pk=post_id)
    except Post.DoesNotExist:
        return _error("Post not found.", status=404)

    if request.method == "GET":
        return JsonResponse(_post_payload(post))

    denied = _login_required(request)
    if denied:
        return denied
    if not _can_edit(request.user, post):
        return _error("You can only change your own posts.", status=403)

    if request.method == "PATCH":
        body = _json(request)
        if body is None:
            return _error("Invalid JSON data.")
        for field, limit in (("title", 200), ("body", MAX_BODY_CHARS), ("author_name", 120)):
            if field in body:
                value = str(body[field]).strip()
                if not value or len(value) > limit:
                    return _error(f"{field} must be 1 to {limit} characters.")
                setattr(post, field, value)
        if "category" in body:
            category = str(body["category"]).strip().upper()
            if category not in dict(Post.CATEGORY_CHOICES):
                return _error("Unknown category.")
            post.category = category
        if "status" in body:
            # Only staff may reject or unpublish; an author cannot self-approve.
            if not request.user.is_staff:
                return _error("Only staff can change moderation status.", status=403)
            status = str(body["status"]).strip().upper()
            if status not in dict(Post.STATUS_CHOICES):
                return _error("Unknown status.")
            post.status = status
        post.save()
        return _ok("Post updated.", post=_post_payload(post))

    if request.method == "DELETE":
        post.delete()
        return _ok("Post deleted.")

    return _error("Only GET, PATCH and DELETE are allowed.", status=405)



@csrf_exempt
def post_like(request, post_id):
    """Toggle a like: a second click from the same account takes it back."""
    denied = _login_required(request)
    if denied:
        return denied
    try:
        post = _visible_posts(request.user).get(pk=post_id)
    except Post.DoesNotExist:
        return _error("Post not found.", status=404)
    if request.method not in ("POST", "DELETE"):
        return _error("Only POST and DELETE are allowed.", status=405)

    existing = Like.objects.filter(user=request.user, post=post).first()
    if existing and request.method == "DELETE":
        existing.delete()
        return _ok("Like removed.", liked=False, like_count=post.likes.count())
    if not existing:
        Like.objects.get_or_create(user=request.user, post=post)
    return _ok("Like saved.", liked=True, like_count=post.likes.count())


@csrf_exempt
def post_share(request, post_id):
    """Record a share. Open to anonymous readers, since sharing needs no account."""
    if request.method != "POST":
        return _error("Only POST is allowed.", status=405)
    try:
        post = _visible_posts(request.user).get(pk=post_id)
    except Post.DoesNotExist:
        return _error("Post not found.", status=404)
    body = _payload(request)
    channel = str(body.get("channel", "LINK")).strip().upper()
    if channel not in dict(Share.CHANNEL_CHOICES):
        return _error("Unknown share channel.")
    Share.objects.create(post=post, user=request.user if request.user.is_authenticated else None, channel=channel)
    return _ok("Share recorded.", code=201, share_count=post.shares.count())


@csrf_exempt
def post_view(request, post_id):
    """Count a read. Open to anonymous readers and safe to call repeatedly."""
    if request.method != "POST":
        return _error("Only POST is allowed.", status=405)
    try:
        post = _visible_posts(request.user).get(pk=post_id)
    except Post.DoesNotExist:
        return _error("Post not found.", status=404)
    analytics, _ = PostAnalytics.objects.get_or_create(post=post)
    return _ok("View recorded.", views=analytics.record_view())


def _default_feed_city():
    """Dhaka when it exists, so the feed is never empty on a fresh database."""
    return City.objects.filter(slug="dhaka").first() or City.objects.first()


def feed(request):
    """A reader's home feed: their own district, or everywhere when unknown."""
    if request.method != "GET":
        return _error("Only GET is allowed.", status=405)
    qs = _annotate_posts(_visible_posts(request.user), request.user)
    city = _city_for(request.GET.get("city"))
    if city is None and request.user.is_authenticated:
        # No profile table to read a district from, so use wherever this reader
        # posts from most often; a brand-new account falls back to the default.
        recent = (Post.objects.filter(author=request.user)
                  .order_by("-created_at").values_list("city_id", flat=True).first())
        if recent:
            city = City.objects.filter(pk=recent).first()
    if city is None:
        city = _default_feed_city()
    qs = qs.filter(city=city)
    limit = _int_arg(request, "limit", 20, 1, 50)
    offset = _int_arg(request, "offset", 0, 0, 10000)
    return JsonResponse({"city": city.slug if city else None,
                         "results": [_post_payload(p) for p in qs[offset:offset + limit]]})


def _trending_score(post, now):
    """Rank by engagement, faded by age so a week-old post cannot sit on top."""
    age_hours = max((now - post.created_at).total_seconds() / 3600, 0)
    decay = 1 / (1 + age_hours / 24)
    views = post.analytics.views if hasattr(post, "analytics") else 0
    return (TRENDING_WEIGHTS["like"] * getattr(post, "like_count", 0)
            + TRENDING_WEIGHTS["comment"] * getattr(post, "comment_count", 0)
            + TRENDING_WEIGHTS["share"] * getattr(post, "share_count", 0)
            + TRENDING_WEIGHTS["view"] * views) * decay


def trending(request):
    """Most-engaged recent posts. Scored in Python, which is fine at this
    scale; move the ranking into the database before the post table grows."""
    if request.method != "GET":
        return _error("Only GET is allowed.", status=405)
    limit = _int_arg(request, "limit", 10, 1, 50)
    now = timezone.now()
    windowed = _visible_posts(request.user).filter(
        created_at__gte=now - timedelta(days=TRENDING_WINDOW_DAYS))
    qs = _annotate_posts(windowed, request.user).select_related("city", "analytics")[:200]
    ranked = sorted(qs, key=lambda p: _trending_score(p, now), reverse=True)
    return JsonResponse({"results": [_post_payload(p) for p in ranked[:limit]]})



def post_comments(request, post_id):
    """List the published comments on a post."""
    if request.method != "GET":
        return _error("Only GET is allowed.", status=405)
    try:
        post = _visible_posts(request.user).get(pk=post_id)
    except Post.DoesNotExist:
        return _error("Post not found.", status=404)
    qs = _comment_queryset(request.user).filter(post=post)
    return JsonResponse({"count": qs.count(),
                         "results": [_comment_payload(c) for c in qs]})


@csrf_exempt
def comments(request):
    """Add a comment, or a reply when ``parent`` names another comment."""
    denied = _login_required(request)
    if denied:
        return denied
    if request.method != "POST":
        return _error("Only POST is allowed.", status=405)
    body = _payload(request)
    text = str(body.get("body", "")).strip()
    if not text or len(text) > 2000:
        return _error("Comment text of 1 to 2000 characters is required.")
    try:
        post = _visible_posts(request.user).get(pk=int(body.get("post")))
    except (TypeError, ValueError, Post.DoesNotExist):
        return _error("A valid post is required.")

    parent = None
    if body.get("parent"):
        try:
            parent = Comment.objects.get(pk=int(body["parent"]), post=post)
        except (TypeError, ValueError, Comment.DoesNotExist):
            return _error("The comment being replied to was not found on this post.")

    comment = Comment.objects.create(
        post=post, author=request.user, parent=parent, body=text,
        author_name=str(body.get("author_name", "")).strip()[:120])
    return _ok("Comment posted.", code=201, comment=_comment_payload(comment))


@csrf_exempt
def comment_detail(request, comment_id):
    """Read, edit or delete one comment."""
    try:
        comment = _comment_queryset(request.user).get(pk=comment_id)
    except Comment.DoesNotExist:
        return _error("Comment not found.", status=404)
    if request.method == "GET":
        return JsonResponse(_comment_payload(comment))

    denied = _login_required(request)
    if denied:
        return denied
    if not (request.user.is_staff or comment.author_id == request.user.id):
        return _error("You can only change your own comments.", status=403)

    if request.method == "PATCH":
        body = _json(request)
        if body is None:
            return _error("Invalid JSON data.")
        if "body" in body:
            text = str(body["body"]).strip()
            if not text or len(text) > 2000:
                return _error("Comment text of 1 to 2000 characters is required.")
            comment.body = text
        if "status" in body:
            if not request.user.is_staff:
                return _error("Only staff can change moderation status.", status=403)
            status = str(body["status"]).strip().upper()
            if status not in dict(Comment.STATUS_CHOICES):
                return _error("Unknown status.")
            comment.status = status
        comment.save()
        return _ok("Comment updated.", comment=_comment_payload(comment))

    if request.method == "DELETE":
        comment.delete()
        return _ok("Comment deleted.")

    return _error("Only GET, PATCH and DELETE are allowed.", status=405)


@csrf_exempt
def comment_like(request, comment_id):
    """Toggle a like on a comment."""
    denied = _login_required(request)
    if denied:
        return denied
    try:
        comment = _comment_queryset(request.user).get(pk=comment_id)
    except Comment.DoesNotExist:
        return _error("Comment not found.", status=404)
    if request.method not in ("POST", "DELETE"):
        return _error("Only POST and DELETE are allowed.", status=405)

    existing = Like.objects.filter(user=request.user, comment=comment).first()
    if existing and request.method == "DELETE":
        existing.delete()
        return _ok("Like removed.", liked=False, like_count=comment.likes.count())
    if not existing:
        Like.objects.get_or_create(user=request.user, comment=comment)
    return _ok("Like saved.", liked=True, like_count=comment.likes.count())



@csrf_exempt
def flags(request):
    """File a moderation report. Open to signed-out readers on purpose: the
    people most likely to spot something dangerous are often the least willing
    to register, and staff triage these by hand anyway."""
    if request.method != "POST":
        return _error("Only POST is allowed.", status=405)
    body = _payload(request)
    reason = str(body.get("reason", "")).strip().upper()
    if reason not in dict(ModerationFlag.REASON_CHOICES):
        return _error("A valid reason is required.")
    details = str(body.get("details", "")).strip()[:1000]

    post = comment = None
    if body.get("post"):
        try:
            post = _visible_posts(request.user).get(pk=int(body["post"]))
        except (TypeError, ValueError, Post.DoesNotExist):
            return _error("The post being reported was not found.")
    elif body.get("comment"):
        try:
            comment = _comment_queryset(request.user).get(pk=int(body["comment"]))
        except (TypeError, ValueError, Comment.DoesNotExist):
            return _error("The comment being reported was not found.")
    else:
        return _error("A post id or a comment id is required.")

    reporter = request.user if request.user.is_authenticated else None
    if ModerationFlag.objects.filter(reporter=reporter, post=post, comment=comment, reason=reason).exists():
        return _ok("You have already reported this.")

    ModerationFlag.objects.create(
        post=post, comment=comment, reporter=reporter,
        reporter_email=str(body.get("email", ""))[:254], reason=reason, details=details)
    return _ok("Thank you. Staff will review this.", code=201)


@csrf_exempt
def admin_flags(request):
    """The staff moderation queue."""
    if not request.user.is_staff:
        return _error("Staff access required.", status=403)
    if request.method == "GET":
        qs = ModerationFlag.objects.select_related("post", "comment", "reporter", "handled_by")
        status = request.GET.get("status", "").strip().upper()
        if status:
            qs = qs.filter(status=status)
        return JsonResponse({"count": qs.count(), "results": [
            {"id": f.id, "reason": f.reason, "details": f.details, "status": f.status,
             "post": f.post_id, "comment": f.comment_id,
             "reporter": f.reporter_email or (f.reporter.username if f.reporter else None),
             "handled_by": f.handled_by.username if f.handled_by else None,
             "resolution": f.resolution, "created_at": f.created_at.isoformat()}
            for f in qs]})

    if request.method == "PATCH":
        body = _json(request)
        if body is None:
            return _error("Invalid JSON data.")
        try:
            flag = ModerationFlag.objects.get(pk=int(body.get("id")))
        except (TypeError, ValueError, ModerationFlag.DoesNotExist):
            return _error("Report not found.", status=404)
        status = str(body.get("status", "")).strip().upper()
        if status not in {"RESOLVED", "DISMISSED"}:
            return _error("A report can only be resolved or dismissed.")
        flag.status = status
        flag.resolution = str(body.get("resolution", "")).strip()[:200]
        flag.handled_by = request.user
        flag.handled_at = timezone.now()
        flag.save()
        return _ok("Report updated.", id=flag.id, status=flag.status)

    return _error("Only GET and PATCH are allowed.", status=405)



@csrf_exempt
def journalist_apply(request):
    """Ask for the verified journalist badge. One request per account."""
    denied = _login_required(request)
    if denied:
        return denied
    if request.method != "POST":
        return _error("Only POST is allowed.", status=405)
    if JournalistVerification.objects.filter(user=request.user).exists():
        return _error("You have already applied. Staff will be in touch.", status=409)
    body = _payload(request)
    statement = str(body.get("statement", "")).strip()[:2000]
    if not statement:
        return _error("A short statement of your work is required.")
    JournalistVerification.objects.create(
        user=request.user, outlet=str(body.get("outlet", "")).strip()[:160],
        credential_url=str(body.get("credential_url", "")).strip(), statement=statement)
    return _ok("Application received. Staff will review it.", code=201)


@csrf_exempt
def admin_journalists(request):
    """Approve or reject journalist applications."""
    if not request.user.is_staff:
        return _error("Staff access required.", status=403)
    if request.method == "GET":
        qs = JournalistVerification.objects.select_related("user", "reviewed_by")
        status = request.GET.get("status", "").strip().upper()
        if status:
            qs = qs.filter(status=status)
        return JsonResponse({"count": qs.count(), "results": [
            {"id": v.id, "user": v.user.username,
             "name": v.user.get_full_name() or v.user.username,
             "outlet": v.outlet, "credential_url": v.credential_url, "statement": v.statement,
             "status": v.status, "notes": v.notes,
             "reviewed_by": v.reviewed_by.username if v.reviewed_by else None,
             "created_at": v.created_at.isoformat()}
            for v in qs]})

    if request.method == "PATCH":
        body = _json(request)
        if body is None:
            return _error("Invalid JSON data.")
        try:
            application = JournalistVerification.objects.get(pk=int(body.get("id")))
        except (TypeError, ValueError, JournalistVerification.DoesNotExist):
            return _error("Application not found.", status=404)
        status = str(body.get("status", "")).strip().upper()
        if status not in {"APPROVED", "REJECTED"}:
            return _error("An application can only be approved or rejected.")
        application.status = status
        application.notes = str(body.get("notes", "")).strip()[:1000]
        application.reviewed_by = request.user
        application.reviewed_at = timezone.now()
        application.save()
        return _ok("Application updated.", id=application.id, status=status)

    return _error("Only GET and PATCH are allowed.", status=405)



def search(request):
    """Search posts and comments at once, for the site's search box."""
    if request.method != "GET":
        return _error("Only GET is allowed.", status=405)
    term = request.GET.get("q", "").strip()
    if len(term) < 2:
        return _error("Search needs at least 2 characters.")
    limit = _int_arg(request, "limit", 20, 1, 50)

    post_hits = _visible_posts(request.user).filter(
        Q(title__icontains=term) | Q(body__icontains=term) | Q(author_name__icontains=term))
    comment_hits = _comment_queryset(request.user).filter(
        Q(body__icontains=term) | Q(author_name__icontains=term))
    return JsonResponse({
        "query": term,
        "posts": [_post_payload(p) for p in post_hits[:limit]],
        "comments": [_comment_payload(c) for c in comment_hits[:limit]],
    })


def stats(request):
    """Headline numbers for the journal section, by district when asked."""
    if request.method != "GET":
        return _error("Only GET is allowed.", status=405)
    published = _visible_posts(request.user)
    city = _city_for(request.GET.get("city"))
    if city is not None:
        published = published.filter(city=city)
    post_ids = published.values_list("pk", flat=True)
    return JsonResponse({
        "city": city.slug if city else None,
        "posts": published.count(),
        "comments": Comment.objects.filter(post__in=post_ids, status=Comment.PUBLISHED).count(),
        "likes": Like.objects.filter(Q(post__in=post_ids) | Q(comment__post__in=post_ids)).count(),
        "shares": Share.objects.filter(post__in=post_ids).count(),
        "pending_flags": ModerationFlag.objects.filter(status="PENDING").count(),
    })


def my_posts(request):
    """Everything the signed-in account has published, including anything a
    moderator has rejected - an author should still be able to see it."""
    denied = _login_required(request)
    if denied:
        return denied
    if request.method != "GET":
        return _error("Only GET is allowed.", status=405)
    qs = _annotate_posts(Post.objects.filter(author=request.user), request.user)
    return JsonResponse({"count": qs.count(),
                         "results": [_post_payload(p) for p in qs]})


def my_analytics(request):
    """The signed-in author's reach dashboard."""
    denied = _login_required(request)
    if denied:
        return denied
    if request.method != "GET":
        return _error("Only GET is allowed.", status=405)
    mine = Post.objects.filter(author=request.user)
    post_ids = mine.values_list("pk", flat=True)
    return JsonResponse({
        "posts": mine.count(),
        "published": mine.filter(status=Post.PUBLISHED).count(),
        "rejected": mine.filter(status=Post.REJECTED).count(),
        "views": PostAnalytics.objects.filter(post__in=post_ids).aggregate(
            total=Sum("views"))["total"] or 0,
        "likes_received": Like.objects.filter(post__in=post_ids).count(),
        "shares_received": Share.objects.filter(post__in=post_ids).count(),
        "comments_received": Comment.objects.filter(post__in=post_ids).count(),
        "flags_against_my_posts": ModerationFlag.objects.filter(post__in=post_ids).count(),
        "journalist_badge": JournalistVerification.objects.filter(
            user=request.user, status="APPROVED").exists(),
    })

