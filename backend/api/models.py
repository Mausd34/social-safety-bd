from django.db import models
from django.db.models import Avg, Count

class City(models.Model):
    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(unique=True)
    division = models.CharField(max_length=60, blank=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    reported_cases = models.PositiveIntegerField(default=0)
    under_investigation = models.PositiveIntegerField(default=0)
    under_trial = models.PositiveIntegerField(default=0)
    convicted = models.PositiveIntegerField(default=0)
    acquitted = models.PositiveIntegerField(default=0)

    def __str__(self):
        return self.name

class Area(models.Model):
    city = models.ForeignKey(City, on_delete=models.CASCADE, related_name="areas")
    name = models.CharField(max_length=120)
    reported_cases = models.PositiveIntegerField(default=0)
    under_investigation = models.PositiveIntegerField(default=0)
    under_trial = models.PositiveIntegerField(default=0)
    convicted = models.PositiveIntegerField(default=0)
    acquitted = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ("city", "name")

    def __str__(self):
        return f"{self.city.name} - {self.name}"

class Case(models.Model):
    STATUS_CHOICES = [
        ("REPORTED", "Reported"),
        ("INVESTIGATION", "Under Investigation"),
        ("TRIAL", "Under Trial"),
        ("CONVICTED", "Convicted"),
        ("ACQUITTED", "Acquitted"),
    ]
    CATEGORY_CHOICES = [
        ("GENERAL", "General public safety"),
        ("SEXUAL_OFFENCE", "Sexual offence"),
        ("VIOLENCE", "Violence"),
        ("TRAFFICKING", "Trafficking / exploitation"),
        ("CYBERCRIME", "Cybercrime"),
    ]
    case_id = models.CharField(max_length=80, unique=True)
    city = models.ForeignKey(City, on_delete=models.PROTECT)
    area = models.ForeignKey(Area, on_delete=models.PROTECT, null=True, blank=True)
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES, default="GENERAL")
    offence_section = models.CharField(max_length=200, blank=True)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES)
    court_status = models.CharField(max_length=180, blank=True)
    incident_date = models.DateField(null=True, blank=True)
    source_name = models.CharField(max_length=200)
    source_url = models.URLField(blank=True)
    verified = models.BooleanField(default=False)
    last_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.case_id

class Upazila(models.Model):
    """Sub-district unit. Chat/help requests are routed through these."""

    district = models.ForeignKey(City, on_delete=models.CASCADE, related_name="upazilas")
    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=160)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)

    class Meta:
        unique_together = ("district", "name")
        ordering = ("district__name", "name")

    def __str__(self):
        return f"{self.district.name} - {self.name}"


class ChatThread(models.Model):
    """A help conversation scoped to one upazila."""

    STATUS_CHOICES = [
        ("OPEN", "Open"),
        ("ANSWERED", "Answered"),
        ("CLOSED", "Closed"),
    ]
    upazila = models.ForeignKey(Upazila, on_delete=models.PROTECT, related_name="threads")
    user = models.ForeignKey("auth.User", on_delete=models.SET_NULL, null=True, blank=True)
    subject = models.CharField(max_length=180, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="OPEN")
    created_at = models.DateTimeField(auto_now_add=True)
    last_activity = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-last_activity",)

    def __str__(self):
        return f"{self.upazila.name} #{self.pk}"


class ChatMessage(models.Model):
    SENDER_CHOICES = [
        ("USER", "User"),
        ("STAFF", "Staff"),
    ]
    thread = models.ForeignKey(ChatThread, on_delete=models.CASCADE, related_name="messages")
    sender = models.CharField(max_length=10, choices=SENDER_CHOICES)
    body = models.TextField(max_length=2000)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("created_at",)

    def __str__(self):
        return f"{self.thread_id} {self.sender}"


class SafetyReport(models.Model):
    STATUS_CHOICES = [
        ("PENDING", "Pending Review"),
        ("VERIFIED", "Verified"),
        ("REJECTED", "Rejected"),
    ]
    location = models.CharField(max_length=180)
    category = models.CharField(max_length=120)
    description = models.TextField()
    evidence = models.FileField(upload_to="report-evidence/", blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="PENDING")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.category} - {self.location}"


class Hotel(models.Model):
    """An accommodation travellers can rate for safety.

    A safety rating is a serious claim about a business, so listings only appear
    publicly once staff have verified them. Seeded names are fictional: rating a
    real hotel's safety would be defamatory, so the demo data invents its own.
    """

    PRICE_CHOICES = [
        ("BUDGET", "Budget"),
        ("MID", "Mid-range"),
        ("PREMIUM", "Premium"),
    ]
    name = models.CharField(max_length=160)
    city = models.ForeignKey(City, on_delete=models.CASCADE, related_name="hotels")
    area = models.CharField(max_length=120, blank=True)
    address = models.CharField(max_length=240, blank=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    price_range = models.CharField(max_length=20, choices=PRICE_CHOICES, default="BUDGET")
    photo = models.ImageField(upload_to="hotel-photos/", blank=True, null=True)
    has_24h_front_desk = models.BooleanField(default=False)
    has_cctv = models.BooleanField(default=False)
    has_women_only_floor = models.BooleanField(default=False)
    verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("name",)

    def __str__(self):
        return self.name

    def summary(self):
        """Average ratings from verified reviews only.

        Unverified reviews are excluded so that a pending or rejected review can
        never influence what the public sees.
        """
        totals = self.reviews.filter(status=HotelReview.VERIFIED).aggregate(
            rating=Avg("rating"), safety=Avg("safety_rating"), total=Count("id"))
        return {
            "rating": round(totals["rating"], 1) if totals["rating"] else None,
            "safety_rating": round(totals["safety"], 1) if totals["safety"] else None,
            "review_count": totals["total"] or 0,
        }


class HotelReview(models.Model):
    """A traveller's account of staying at a hotel.

    Reviews land as PENDING and are only published after staff verification,
    matching the moderation policy used for incident reports.
    """

    PENDING = "PENDING"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"

    STATUS_CHOICES = [
        (PENDING, "Pending Review"),
        (VERIFIED, "Verified"),
        (REJECTED, "Rejected"),
    ]
    hotel = models.ForeignKey(Hotel, on_delete=models.CASCADE, related_name="reviews")
    user = models.ForeignKey("auth.User", on_delete=models.SET_NULL, null=True, blank=True)
    author_name = models.CharField(max_length=80)
    rating = models.PositiveSmallIntegerField()
    safety_rating = models.PositiveSmallIntegerField()
    solo_traveller = models.BooleanField(default=False)
    body = models.TextField(max_length=2000)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="PENDING")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        constraints = [
            # One review per signed-in account per hotel. Anonymous rows have a
            # NULL user, which SQL unique constraints ignore, so visitors who are
            # not logged in can still contribute.
            models.UniqueConstraint(
                fields=["hotel", "user"],
                condition=models.Q(user__isnull=False),
                name="unique_review_per_user_per_hotel",
            ),
        ]

    def __str__(self):
        return f"{self.hotel.name} - {self.rating}/5"
