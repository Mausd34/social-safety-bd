"""Demo content for the citizen-journalism layer.

Separate from ``seed_demo`` on purpose: that command is still being edited, and
this one only touches journal tables. Safe to re-run - it matches on title and
does nothing when the content is already there.
"""

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction

from api.models import City

from journal.models import (Comment, JournalistVerification, Like,
                            ModerationFlag, Post, PostAnalytics, Share)

DEMO_NOTE = "SYNTHETIC demo record - fabricated for prototyping, not real data"

# (title, district, category, body, author role). The second field must be a
# real district name from api.City, because posts are filed per district.
POSTS = [
    ("Well-lit crossing outside the Uttara school", "Dhaka", "GENERAL",
     "Parents asked for a crossing guard here after the last rain. Street lights now work past the gate.", "reader"),
    ("Unclaimed parcel scam reported in Agrabad", "Chattogram", "CYBERCRIME",
     "Three residents were sent a courier fee demand for a parcel they never ordered. Details in the comments.", "reader"),
    ("Riders asked for a safe waiting area at the ferry ghat", "Dhaka", "GENERAL",
     "Evening ferry queues have no lighting after 8pm. Collecting signatures for a written request.", "journalist"),
    ("Bus stop shelter damaged, commuters walking in the road", "Khulna", "GENERAL",
     "The shelter collapsed in the last storm. Nobody has been assigned to repair it yet.", "reader"),
    ("Mobile clinic schedule published for the upazila", "Cumilla", "GENERAL",
     "The health complex posted next month's clinic dates, so nobody has to travel twice.", "journalist"),
]

REPLIES = [
    "Is there a number to call for the crossing guard?",
    "Our building filed the same complaint last month.",
    "Adding the ward office contact to the comments.",
]


class Command(BaseCommand):
    help = "Load synthetic citizen-journal posts, comments and moderation demo data."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true",
                            help="Delete existing journal content before seeding.")

    @transaction.atomic
    def handle(self, *args, **options):
        if options["reset"]:
            for model in (Like, Share, ModerationFlag, Comment, PostAnalytics,
                          Post, JournalistVerification):
                deleted, _ = model.objects.all().delete()
                self.stdout.write(f"  removed {deleted} {model.__name__} row(s)")
            User.objects.filter(username__endswith="@demo.socialsafety").delete()

        reader = self._user("demo.reader@demo.socialsafety", "Demo Reader", verified=False)
        journalist = self._user("demo.journalist@demo.socialsafety", "Demo Journalist", verified=True)

        created = []
        for title, area, category, text, role in POSTS:
            post, made = Post.objects.get_or_create(
                title=title,
                defaults={"city": self._city(area), "category": category,
                          "body": f"{text}\n\n{DEMO_NOTE}",
                          "author": journalist if role == "journalist" else reader,
                          "author_name": "Demo Journalist" if role == "journalist" else ""})
            if made:
                PostAnalytics.objects.get_or_create(post=post)
                created.append(post)
                self.stdout.write(f"  + post {post.pk} {post.title!r}")

        if created:
            first = created[0]
            for text in REPLIES:
                Comment.objects.get_or_create(post=first, body=f"{text}\n\n{DEMO_NOTE}",
                                              defaults={"author": reader})
            Like.objects.get_or_create(user=reader, post=first)
            Like.objects.get_or_create(user=journalist, post=first)
            Share.objects.get_or_create(user=reader, post=first, channel="LINK")
            ModerationFlag.objects.get_or_create(
                post=first, reason="SPAM",
                defaults={"reporter": reader, "details": DEMO_NOTE})

        self.stdout.write(self.style.SUCCESS(
            f"Journal demo ready: {Post.objects.count()} post(s), {Comment.objects.count()} comment(s)."))

    def _user(self, email, name, verified):
        user, made = User.objects.get_or_create(
            username=email, email=email, defaults={"first_name": name})
        if made:
            user.set_password("demo-pass-123")
            user.save()
        if verified:
            JournalistVerification.objects.get_or_create(
                user=user, defaults={"status": "APPROVED", "outlet": "Daily Star (demo)",
                                     "reviewed_by": user, "statement": DEMO_NOTE})
        return user

    def _city(self, name):
        """Posts are filed against a real district; fall back to Dhaka so the
        seed still works on a database that has not been seeded yet."""
        city = City.objects.filter(name__iexact=name).first()
        if city is None:
            city, _ = City.objects.get_or_create(
                name="Dhaka", slug="dhaka", defaults={"division": "Dhaka Division"})
            self.stdout.write(f"  ! district {name!r} not found, filed under Dhaka")
        return city
