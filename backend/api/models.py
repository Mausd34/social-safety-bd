from django.db import models

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
