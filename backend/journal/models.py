from django.db import models
from django.db.models import F, Q
from django.utils import timezone

from api.models import Case, City


class Post(models.Model):
    """A citizen report or news item, filed against one district.

    This app deliberately reuses the existing ``api.City`` model instead of
    introducing a second district table, so a post and a court case filed in
    the same district are stored in exactly the same place.

    ``author`` is nullable on purpose: many tips come from people who cannot
    safely be tied to an account, and ``author_name`` carries the attribution
    they are willing to publish. ``status`` defaults to PUBLISHED so a tip is
    never silently lost; staff can move it to REJECTED after review.
    """

    PENDING = "PENDING"
    PUBLISHED = "PUBLISHED"
    REJECTED = "REJECTED"

    STATUS_CHOICES = [
        (PENDING, "Pending Review"),
        (PUBLISHED, "Published"),
        (REJECTED, "Rejected"),
    ]

    # Same filing vocabulary as a court case, so both can share filters.
    CATEGORY_CHOICES = Case.CATEGORY_CHOICES

    author = models.ForeignKey("auth.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="journal_posts")
    author_name = models.CharField(max_length=120, blank=True)
    city = models.ForeignKey(City, on_delete=models.CASCADE, related_name="journal_posts")
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES, default="GENERAL")
    title = models.CharField(max_length=200)
    body = models.TextField()
    image = models.ImageField(upload_to="journal-post-images/", blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="PUBLISHED")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at", "-pk")
        indexes = [
            models.Index(fields=["-created_at"]),
            models.Index(fields=["status", "-created_at"]),
            models.Index(fields=["city", "-created_at"]),
        ]

    def __str__(self):
        return self.title

    @property
    def display_author(self):
        """The name shown publicly, falling back to "Anonymous".

        Only what the author chose to publish is shown - never their email or
        username unless that is genuinely their public byline.
        """
        if self.author_name:
            return self.author_name
        if self.author is not None:
            return self.author.get_full_name() or self.author.username
        return "Anonymous"

    @property
    def author_is_verified(self):
        """True when the account behind this post passed journalist review."""
        if self.author is None:
            return False
        try:
            return self.author.journalist_verification.is_approved
        except JournalistVerification.DoesNotExist:
            return False


class Comment(models.Model):
    """A reader response to a post, optionally replying to another comment."""

    PUBLISHED = "PUBLISHED"
    HIDDEN = "HIDDEN"
    REJECTED = "REJECTED"

    STATUS_CHOICES = [
        (PUBLISHED, "Published"),
        (HIDDEN, "Hidden"),
        (REJECTED, "Rejected"),
    ]

    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey("auth.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="journal_comments")
    author_name = models.CharField(max_length=120, blank=True)
    parent = models.ForeignKey("self", on_delete=models.CASCADE, null=True, blank=True, related_name="replies")
    body = models.TextField(max_length=2000)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="PUBLISHED")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("created_at", "pk")
        indexes = [models.Index(fields=["post", "created_at"])]

    def __str__(self):
        return f"{self.post_id}:{self.pk}"

    @property
    def display_author(self):
        if self.author_name:
            return self.author_name
        if self.author is not None:
            return self.author.get_full_name() or self.author.username
        return "Anonymous"


class Like(models.Model):
    """A like on either a post or a comment - exactly one, never both.

    SQL treats NULLs as distinct, so the two unique constraints alone would
    still allow duplicate comment likes; the check constraint is what actually
    enforces "one target" and "one like per user".
    """

    user = models.ForeignKey("auth.User", on_delete=models.CASCADE, related_name="journal_likes")
    post = models.ForeignKey(Post, on_delete=models.CASCADE, null=True, blank=True, related_name="likes")
    comment = models.ForeignKey(Comment, on_delete=models.CASCADE, null=True, blank=True, related_name="likes")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        constraints = [
            models.UniqueConstraint(fields=["user", "post"], name="unique_post_like"),
            models.UniqueConstraint(fields=["user", "comment"], name="unique_comment_like"),
            models.CheckConstraint(
                condition=(Q(post__isnull=False) & Q(comment__isnull=True))
                | (Q(post__isnull=True) & Q(comment__isnull=False)),
                name="like_targets_exactly_one",
            ),
        ]

    def __str__(self):
        return f"like:{self.pk}"


class Share(models.Model):
    """A record that a post was shared, for reach reporting."""

    LINK = "LINK"
    FACEBOOK = "FACEBOOK"
    WHATSAPP = "WHATSAPP"
    X = "X"
    OTHER = "OTHER"

    CHANNEL_CHOICES = [
        (LINK, "Copied link"),
        (FACEBOOK, "Facebook"),
        (WHATSAPP, "WhatsApp"),
        (X, "X"),
        (OTHER, "Other"),
    ]

    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="shares")
    user = models.ForeignKey("auth.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="journal_shares")
    channel = models.CharField(max_length=20, choices=CHANNEL_CHOICES, default="LINK")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [models.Index(fields=["post", "-created_at"])]

    def __str__(self):
        return f"{self.channel}:{self.pk}"


class ModerationFlag(models.Model):
    """A report from a reader that a post or comment should be reviewed.

    Exactly one of ``post`` / ``comment`` is set, for the same reason as
    ``Like``. Flags are reviewed by staff, and the resolution is recorded so a
    decision can be audited later.
    """

    SPAM = "SPAM"
    ABUSE = "ABUSE"
    MISINFORMATION = "MISINFORMATION"
    PRIVACY = "PRIVACY"
    OTHER = "OTHER"

    REASON_CHOICES = [
        (SPAM, "Spam or advertising"),
        (ABUSE, "Abuse or harassment"),
        (MISINFORMATION, "Misleading or unverified claim"),
        (PRIVACY, "Reveals someone's private information"),
        (OTHER, "Something else"),
    ]

    PENDING = "PENDING"
    RESOLVED = "RESOLVED"
    DISMISSED = "DISMISSED"

    STATUS_CHOICES = [
        (PENDING, "Pending Review"),
        (RESOLVED, "Content actioned"),
        (DISMISSED, "No action needed"),
    ]

    post = models.ForeignKey(Post, on_delete=models.CASCADE, null=True, blank=True, related_name="flags")
    comment = models.ForeignKey(Comment, on_delete=models.CASCADE, null=True, blank=True, related_name="flags")
    reporter = models.ForeignKey("auth.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="journal_flags")
    reporter_email = models.EmailField(blank=True)
    reason = models.CharField(max_length=30, choices=REASON_CHOICES)
    details = models.TextField(max_length=1000, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="PENDING")
    resolution = models.CharField(max_length=200, blank=True)
    handled_by = models.ForeignKey("auth.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="journal_flags_handled")
    created_at = models.DateTimeField(auto_now_add=True)
    handled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)
        constraints = [
            models.CheckConstraint(
                condition=(Q(post__isnull=False) & Q(comment__isnull=True))
                | (Q(post__isnull=True) & Q(comment__isnull=False)),
                name="flag_targets_exactly_one",
            ),
        ]

    def __str__(self):
        return f"{self.reason}:{self.pk}"

    @property
    def target(self):
        return self.post or self.comment


class JournalistVerification(models.Model):
    """A request to carry the verified journalist badge.

    One request per account. Approval is a staff decision recorded with the
    reviewing account and time, so a badge can always be traced back to
    whoever granted it.
    """

    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"

    STATUS_CHOICES = [
        (PENDING, "Pending Review"),
        (APPROVED, "Approved"),
        (REJECTED, "Rejected"),
    ]

    user = models.OneToOneField("auth.User", on_delete=models.CASCADE, related_name="journalist_verification")
    outlet = models.CharField(max_length=160, blank=True)
    credential_url = models.URLField(blank=True)
    statement = models.TextField(max_length=2000, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="PENDING")
    reviewed_by = models.ForeignKey("auth.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="journalist_reviews")
    reviewed_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(max_length=1000, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.user_id}:{self.status}"

    @property
    def is_approved(self):
        return self.status == "APPROVED"


class PostAnalytics(models.Model):
    """Per-post read counts.

    Only views are stored. Likes, comments and shares are counted live from
    their own tables instead of being cached here, because a denormalised
    counter silently drifts the moment a like is deleted, and a wrong
    engagement number on a safety platform is worse than a slower query.
    """

    post = models.OneToOneField(Post, on_delete=models.CASCADE, related_name="analytics")
    views = models.PositiveIntegerField(default=0)
    last_viewed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"views:{self.post_id}"

    def record_view(self):
        """Increment atomically so concurrent readers cannot lose counts."""
        PostAnalytics.objects.filter(pk=self.pk).update(
            views=F("views") + 1, last_viewed_at=timezone.now())
        self.refresh_from_db(fields=["views", "last_viewed_at"])
        return self.views
