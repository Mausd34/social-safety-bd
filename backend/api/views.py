import json
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.db.models import Count, Q, Sum
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .models import Area, Case, ChatMessage, ChatThread, City, SafetyReport, Upazila


def _json(request):
    try:
        return json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return None


def _user_payload(user):
    return {"id": user.id, "username": user.username, "email": user.email,
            "is_staff": user.is_staff, "is_superuser": user.is_superuser}


@csrf_exempt
def login_view(request):
    if request.method != "POST":
        return JsonResponse({"success": False, "message": "Only POST method is allowed."}, status=405)
    body = _json(request)
    if body is None:
        return JsonResponse({"success": False, "message": "Invalid JSON data."}, status=400)
    email, password = str(body.get("email", "")).strip(), body.get("password", "")
    user = User.objects.filter(email__iexact=email).first() if email else None
    if not user or not authenticate(username=user.username, password=password):
        return JsonResponse({"success": False, "message": "Invalid email or password."}, status=401)
    login(request, user)
    return JsonResponse({"success": True, "message": "Login successful.", "user": _user_payload(user)})


@csrf_exempt
def register_view(request):
    if request.method != "POST":
        return JsonResponse({"success": False, "message": "Only POST method is allowed."}, status=405)
    body = _json(request)
    if body is None:
        return JsonResponse({"success": False, "message": "Invalid JSON data."}, status=400)
    name = str(body.get("name", "")).strip()
    email = str(body.get("email", "")).strip().lower()
    password = str(body.get("password", ""))
    if not name or not email or len(password) < 8:
        return JsonResponse({"success": False, "message": "Name, valid email and an 8+ character password are required."}, status=400)
    if User.objects.filter(email__iexact=email).exists() or User.objects.filter(username__iexact=email).exists():
        return JsonResponse({"success": False, "message": "An account with this email already exists."}, status=409)
    user = User.objects.create_user(username=email, email=email, password=password, first_name=name[:150])
    login(request, user)
    return JsonResponse({"success": True, "message": "Account created successfully.", "user": _user_payload(user)}, status=201)


def me(request):
    if not request.user.is_authenticated:
        return JsonResponse({"authenticated": False})
    return JsonResponse({"authenticated": True, "user": _user_payload(request.user)})


@csrf_exempt
def logout_view(request):
    logout(request)
    return JsonResponse({"success": True, "message": "Logged out."})


def cities(request):
    data = [{"id": c.id, "name": c.name, "slug": c.slug, "division": c.division,
             "latitude": c.latitude, "longitude": c.longitude,
             "reported": c.reported_cases,
             "investigation": c.under_investigation, "trial": c.under_trial,
             "convicted": c.convicted, "acquitted": c.acquitted}
            for c in City.objects.all().order_by("name")]
    return JsonResponse(data, safe=False)


def areas(request):
    city = request.GET.get("city", "").strip()
    qs = Area.objects.select_related("city").all()
    if city:
        qs = qs.filter(Q(city__slug__iexact=city) | Q(city__name__iexact=city))
    data = [{"id": a.id, "city": a.city.name, "city_slug": a.city.slug, "name": a.name,
             "reported": a.reported_cases, "investigation": a.under_investigation,
             "trial": a.under_trial, "convicted": a.convicted, "acquitted": a.acquitted}
            for a in qs.order_by("city__name", "name")]
    return JsonResponse(data, safe=False)


def cases(request):
    qs = Case.objects.select_related("city", "area").filter(verified=True)
    search = request.GET.get("search", "").strip()
    status = request.GET.get("status", "").strip().upper()
    city = request.GET.get("city", "").strip()
    category = request.GET.get("category", "").strip().upper()
    if search:
        qs = qs.filter(Q(case_id__icontains=search) | Q(city__name__icontains=search) |
                       Q(area__name__icontains=search) | Q(source_name__icontains=search) |
                       Q(offence_section__icontains=search))
    if category:
        qs = qs.filter(category=category)
    if status:
        qs = qs.filter(status=status)
    if city:
        qs = qs.filter(Q(city__slug__iexact=city) | Q(city__name__iexact=city))
    data = [{"case_id": c.case_id, "city": c.city.name, "area": c.area.name if c.area else None,
             "category": c.category, "category_label": c.get_category_display(),
             "offence_section": c.offence_section,
             "status": c.status, "court_status": c.court_status,
             "incident_date": c.incident_date.isoformat() if c.incident_date else None,
             "source_name": c.source_name, "source_url": c.source_url,
             "verified": c.verified, "last_updated": c.last_updated.isoformat()}
            for c in qs.order_by("-incident_date", "-last_updated")]
    return JsonResponse(data, safe=False)


def statistics(request):
    qs = City.objects.all()
    totals = qs.aggregate(reported=Sum("reported_cases"), investigation=Sum("under_investigation"),
                          trial=Sum("under_trial"), convicted=Sum("convicted"), acquitted=Sum("acquitted"))
    return JsonResponse({"cities": qs.count(), **{k: v or 0 for k, v in totals.items()},
                         "case_status": list(Case.objects.filter(verified=True).values("status").annotate(count=Count("id")).order_by("status")),
                         "city_totals": list(qs.values("name", "slug", "reported_cases", "convicted").order_by("-reported_cases"))})


def dashboard(request):
    return statistics(request)


def case_detail(request, case_id):
    case = Case.objects.select_related("city", "area").filter(case_id=case_id, verified=True).first()
    if not case:
        return JsonResponse({"success": False, "message": "Verified case not found."}, status=404)
    return JsonResponse({"case_id": case.case_id, "city": case.city.name, "area": case.area.name if case.area else None,
                         "status": case.status, "court_status": case.court_status,
                         "incident_date": case.incident_date.isoformat() if case.incident_date else None,
                         "source_name": case.source_name, "source_url": case.source_url, "verified": case.verified})


@csrf_exempt
def report_create(request):
    if request.method != "POST":
        return JsonResponse({"success": False, "message": "Only POST method is allowed."}, status=405)
    location = request.POST.get("location", "").strip()
    category = request.POST.get("category", "").strip()
    description = request.POST.get("description", "").strip()
    evidence = request.FILES.get("evidence")
    if not location or not category or not description:
        return JsonResponse({"success": False, "message": "Location, category and description are required."}, status=400)
    if len(description) > 5000:
        return JsonResponse({"success": False, "message": "Description must be 5000 characters or fewer."}, status=400)
    if evidence and evidence.size > 5 * 1024 * 1024:
        return JsonResponse({"success": False, "message": "Evidence file must be 5 MB or smaller."}, status=400)
    report = SafetyReport.objects.create(location=location, category=category, description=description, evidence=evidence)
    return JsonResponse({"success": True, "message": "Report submitted for review.", "id": report.id}, status=201)


@csrf_exempt
def admin_reports(request):
    if not request.user.is_staff:
        return JsonResponse({"success": False, "message": "Staff access required."}, status=403)
    if request.method == "GET":
        data = [{"id": r.id, "location": r.location, "category": r.category, "description": r.description,
                 "status": r.status, "created_at": r.created_at.isoformat(),
                 "evidence": r.evidence.url if r.evidence else None}
                for r in SafetyReport.objects.all().order_by("-created_at")]
        return JsonResponse(data, safe=False)
    if request.method == "PATCH":
        body = _json(request) or {}
        try:
            report = SafetyReport.objects.get(pk=int(body.get("id")))
        except (TypeError, ValueError, SafetyReport.DoesNotExist):
            return JsonResponse({"success": False, "message": "Report not found."}, status=404)
        status = str(body.get("status", "")).upper()
        if status not in {"PENDING", "VERIFIED", "REJECTED"}:
            return JsonResponse({"success": False, "message": "Invalid report status."}, status=400)
        report.status = status
        report.save(update_fields=["status"])
        return JsonResponse({"success": True, "message": "Report status updated."})
    return JsonResponse({"success": False, "message": "Only GET and PATCH are allowed."}, status=405)


def upazilas(request):
    district = request.GET.get("district", "").strip()
    search = request.GET.get("search", "").strip()
    qs = Upazila.objects.select_related("district").all()
    if district:
        qs = qs.filter(Q(district__slug__iexact=district) | Q(district__name__iexact=district))
    if search:
        qs = qs.filter(Q(name__icontains=search) | Q(district__name__icontains=search))
    data = [{"id": u.id, "name": u.name, "slug": u.slug,
             "district": u.district.name, "district_slug": u.district.slug}
            for u in qs.order_by("district__name", "name")]
    return JsonResponse(data, safe=False)


def _thread_payload(thread, include_messages=True):
    payload = {"id": thread.id, "upazila": thread.upazila.name,
               "district": thread.upazila.district.name,
               "upazila_slug": thread.upazila.slug,
               "status": thread.status, "subject": thread.subject,
               "created_at": thread.created_at.isoformat()}
    if include_messages:
        payload["messages"] = [
            {"id": m.id, "sender": m.sender, "body": m.body,
             "created_at": m.created_at.isoformat()}
            for m in thread.messages.all()
        ]
    return payload


@csrf_exempt
def chat_thread_create(request):
    """Start a help thread for an upazila (optionally with a first message)."""
    if request.method != "POST":
        return JsonResponse({"success": False, "message": "Only POST is allowed."}, status=405)
    body = _json(request)
    if body is None:
        return JsonResponse({"success": False, "message": "Invalid JSON."}, status=400)
    try:
        upazila = Upazila.objects.get(pk=int(body.get("upazila")))
    except (TypeError, ValueError, Upazila.DoesNotExist):
        return JsonResponse({"success": False, "message": "Select a valid upazila."}, status=400)
    first = str(body.get("message", "")).strip()
    if not first:
        return JsonResponse({"success": False, "message": "Write a message to start."}, status=400)
    if len(first) > 2000:
        return JsonResponse({"success": False, "message": "Message too long (2000 max)."}, status=400)
    subject = str(body.get("subject", "")).strip()[:180]
    thread = ChatThread.objects.create(
        upazila=upazila,
        user=request.user if request.user.is_authenticated else None,
        subject=subject,
    )
    ChatMessage.objects.create(thread=thread, sender="USER", body=first)
    return JsonResponse({"success": True, "thread": _thread_payload(thread)}, status=201)


@csrf_exempt
def chat_thread_detail(request, thread_id):
    """Read a thread. Anyone who knows the id can post to it, so replies are
    rate-unlimited by design for a demo - tighten before real use."""
    thread = ChatThread.objects.select_related("upazila", "upazila__district").filter(pk=thread_id).first()
    if not thread:
        return JsonResponse({"success": False, "message": "Thread not found."}, status=404)
    if request.method == "GET":
        return JsonResponse({"success": True, "thread": _thread_payload(thread)})
    if request.method == "POST":
        body = _json(request) or {}
        text = str(body.get("message", "")).strip()
        if not text:
            return JsonResponse({"success": False, "message": "Message cannot be empty."}, status=400)
        if len(text) > 2000:
            return JsonResponse({"success": False, "message": "Message too long (2000 max)."}, status=400)
        is_staff = request.user.is_staff
        if thread.status == "CLOSED":
            return JsonResponse({"success": False, "message": "This conversation is closed."}, status=409)
        ChatMessage.objects.create(thread=thread, sender="STAFF" if is_staff else "USER", body=text)
        if is_staff and thread.status == "OPEN":
            thread.status = "ANSWERED"
            thread.save(update_fields=["status"])
        thread.save(update_fields=["last_activity"])
        return JsonResponse({"success": True, "thread": _thread_payload(thread)}, status=201)
    return JsonResponse({"success": False, "message": "Only GET and POST are allowed."}, status=405)


@csrf_exempt
def admin_chat_threads(request):
    """Staff inbox: list threads and post official replies."""
    if not request.user.is_staff:
        return JsonResponse({"success": False, "message": "Staff access required."}, status=403)
    if request.method == "GET":
        threads = ChatThread.objects.select_related("upazila", "upazila__district").all()[:100]
        return JsonResponse([_thread_payload(t) for t in threads], safe=False)
    if request.method == "POST":
        body = _json(request) or {}
        try:
            thread = ChatThread.objects.get(pk=int(body.get("id")))
        except (TypeError, ValueError, ChatThread.DoesNotExist):
            return JsonResponse({"success": False, "message": "Thread not found."}, status=404)
        text = str(body.get("message", "")).strip()
        status = str(body.get("status", "")).upper()
        if text:
            ChatMessage.objects.create(thread=thread, sender="STAFF", body=text[:2000])
            if not status and thread.status == "OPEN":
                status = "ANSWERED"
        if status in {code for code, _ in ChatThread.STATUS_CHOICES}:
            thread.status = status
        thread.save(update_fields=["status", "last_activity"])
        return JsonResponse({"success": True, "thread": _thread_payload(thread)})
    return JsonResponse({"success": False, "message": "Only GET and POST are allowed."}, status=405)


def health(request):
    return JsonResponse({"status": "ok", "service": "Social Safety BD API"})
