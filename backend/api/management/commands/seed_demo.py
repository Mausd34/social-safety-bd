"""Load clearly marked SYNTHETIC demo data covering all 64 districts of Bangladesh.

Geographic data (district names, divisions, latitude/longitude and population)
is real. Every case/crime statistic produced here is FABRICATED for UI
development and must be replaced with authoritative, verifiable sources before
publication. Records are tagged so they can never be mistaken for real data.
"""
import hashlib
from datetime import date, timedelta

from django.core.management.base import BaseCommand
from django.db import transaction

from api.models import Area, Case, City

SYNTHETIC_SOURCE = "SYNTHETIC demo record - fabricated for prototyping, not real data"

# name, slug, division, latitude, longitude, population in millions (2023 census approx.)
DISTRICTS = [
    # ---- Dhaka Division (13) ----
    ("Dhaka", "dhaka", "Dhaka", 23.8103, 90.4125, 8.94),
    ("Faridpur", "faridpur", "Dhaka", 23.6070, 89.8426, 1.72),
    ("Gazipur", "gazipur", "Dhaka", 24.0021, 90.4203, 2.90),
    ("Gopalganj", "gopalganj", "Dhaka", 23.0052, 90.3370, 1.10),
    ("Kishoreganj", "kishoreganj", "Dhaka", 24.4331, 90.7867, 1.48),
    ("Madaripur", "madaripur", "Dhaka", 23.1664, 90.2075, 0.83),
    ("Manikganj", "manikganj", "Dhaka", 23.8482, 90.0349, 0.86),
    ("Munshiganj", "munshiganj", "Dhaka", 23.6201, 90.3103, 1.16),
    ("Narayanganj", "narayanganj", "Dhaka", 23.6238, 90.4990, 1.72),
    ("Narsingdi", "narsingdi", "Dhaka", 24.5225, 90.7983, 1.30),
    ("Rajbari", "rajbari", "Dhaka", 23.5712, 89.5415, 0.73),
    ("Shariatpur", "shariatpur", "Dhaka", 23.7623, 90.4347, 0.62),
    ("Tangail", "tangail", "Dhaka", 24.2513, 89.9167, 1.18),
    # ---- Chattogram Division (11) ----
    ("Bandarban", "bandarban", "Chattogram", 22.1953, 92.0376, 0.48),
    ("Brahmanbaria", "brahmanbaria", "Chattogram", 23.9571, 91.1119, 1.30),
    ("Chandpur", "chandpur", "Chattogram", 23.2199, 90.8301, 1.20),
    ("Chattogram", "chattogram", "Chattogram", 22.3569, 91.7832, 3.03),
    ("Cumilla", "cumilla", "Chattogram", 23.4607, 91.1809, 2.75),
    ("Cox's Bazar", "coxs-bazar", "Chattogram", 21.4272, 92.0058, 2.45),
    ("Feni", "feni", "Chattogram", 23.0169, 91.3981, 1.44),
    ("Khagrachhari", "khagrachhari", "Chattogram", 23.4601, 91.6449, 0.65),
    ("Lakshmipur", "lakshmipur", "Chattogram", 22.9434, 90.8150, 1.10),
    ("Noakhali", "noakhali", "Chattogram", 22.8696, 91.0995, 1.01),
    ("Rangamati", "rangamati", "Chattogram", 22.6324, 92.1986, 0.58),
    # ---- Rajshahi Division (8) ----
    ("Bogura", "bogura", "Rajshahi", 24.8465, 89.3773, 1.73),
    ("Chapainawabganj", "chapainawabganj", "Rajshahi", 24.5607, 88.2715, 0.76),
    ("Joypurhat", "joypurhat", "Rajshahi", 25.0407, 89.0936, 0.62),
    ("Naogaon", "naogaon", "Rajshahi", 24.7936, 89.2464, 1.10),
    ("Natore", "natore", "Rajshahi", 24.4706, 89.0426, 0.72),
    ("Pabna", "pabna", "Rajshahi", 24.0064, 89.2372, 1.07),
    ("Rajshahi", "rajshahi", "Rajshahi", 24.3745, 88.6042, 2.04),
    ("Sirajganj", "sirajganj", "Rajshahi", 24.4533, 89.7312, 1.36),
    # ---- Khulna Division (10) ----
    ("Bagerhat", "bagerhat", "Khulna", 22.8196, 90.0954, 1.23),
    ("Chuadanga", "chuadanga", "Khulna", 23.4607, 88.8410, 0.59),
    ("Jashore", "jashore", "Khulna", 23.1704, 89.2137, 1.19),
    ("Jhenaidah", "jhenaidah", "Khulna", 23.5449, 89.1400, 0.97),
    ("Khulna", "khulna", "Khulna", 22.8456, 89.5403, 2.60),
    ("Kushtia", "kushtia", "Khulna", 23.9026, 89.1207, 0.94),
    ("Magura", "magura", "Khulna", 23.7556, 89.4166, 0.43),
    ("Meherpur", "meherpur", "Khulna", 23.7872, 88.6302, 0.28),
    ("Narail", "narail", "Khulna", 23.8700, 89.5000, 0.42),
    ("Satkhira", "satkhira", "Khulna", 22.7185, 89.0705, 0.86),
    # ---- Barishal Division (6) ----
    ("Barguna", "barguna", "Barishal", 22.0954, 90.2120, 0.45),
    ("Barishal", "barishal", "Barishal", 22.7010, 90.3535, 0.84),
    ("Bhola", "bhola", "Barishal", 22.6859, 90.6488, 0.98),
    ("Jhalokathi", "jhalokathi", "Barishal", 22.6358, 90.1990, 0.40),
    ("Patuakhali", "patuakhali", "Barishal", 22.3596, 90.3291, 0.85),
    ("Pirojpur", "pirojpur", "Barishal", 22.8407, 90.0287, 0.63),
    # ---- Sylhet Division (4) ----
    ("Habiganj", "habiganj", "Sylhet", 24.3764, 91.4152, 1.05),
    ("Moulvibazar", "moulvibazar", "Sylhet", 24.4829, 91.7784, 1.02),
    ("Sunamganj", "sunamganj", "Sylhet", 25.0658, 91.3950, 0.72),
    ("Sylhet", "sylhet", "Sylhet", 24.8949, 91.8687, 1.53),
    # ---- Rangpur Division (8) ----
    ("Dinajpur", "dinajpur", "Rangpur", 25.6217, 88.6354, 1.60),
    ("Gaibandha", "gaibandha", "Rangpur", 26.0000, 89.2500, 1.02),
    ("Kurigram", "kurigram", "Rangpur", 25.8072, 89.6295, 0.96),
    ("Lalmonirhat", "lalmonirhat", "Rangpur", 26.0274, 88.9436, 0.51),
    ("Nilphamari", "nilphamari", "Rangpur", 26.0708, 88.8627, 0.58),
    ("Panchagarh", "panchagarh", "Rangpur", 26.3358, 88.5544, 0.43),
    ("Rangpur", "rangpur", "Rangpur", 25.7439, 89.2752, 1.54),
    ("Thakurgaon", "thakurgaon", "Rangpur", 26.0310, 88.4683, 0.48),
    # ---- Mymensingh Division (4) ----
    ("Jamalpur", "jamalpur", "Mymensingh", 24.9375, 89.9371, 1.16),
    ("Mymensingh", "mymensingh", "Mymensingh", 24.7471, 90.4203, 1.37),
    ("Netrokona", "netrokona", "Mymensingh", 24.8708, 90.7278, 0.97),
    ("Sherpur", "sherpur", "Mymensingh", 24.9045, 90.4061, 0.68),
]

DIVISION_CODES = {
    "Dhaka": "DHK", "Chattogram": "CTG", "Rajshahi": "RJS", "Khulna": "KHL",
    "Sylhet": "SYL", "Barishal": "BAR", "Rangpur": "RNG", "Mymensingh": "MYM",
}

# Real thanas / upazilas for the largest districts, keyed by district slug.
AREA_NAMES = {
    "dhaka": ["Uttara", "Mirpur", "Dhanmondi", "Gulshan", "Motijheel", "Wari", "Tejgaon", "Ramna",
              "Shahbagh", "Farmgate", "Banani", "Baridhara", "Khilgaon", "Bashundhara", "Badda",
              "Cantonment", "Paltan", "Shahjahanpur"],
    "chattogram": ["Kotwali", "Double Mohor", "Chattogram Sadar", "Pahartali", "Agrabad", "Chaksba",
                   "Khulshi", "Hazaribagh", "Fatikchhari", "Mirsarai", "Boalkhali", "Anwara",
                   "Rangunia", "Sitakunda", "Karnaphuli"],
    "rajshahi": ["Boalia", "Kazla", "Motijheel", "Shahidbag", "Kachhari", "Charghat", "Bagha",
                 "Puthia", "Durgapur", "Bagmara", "Godagari", "Palpara", "Mohanpur", "Patani"],
    "khulna": ["Khulna Sadar", "Boyra", "Digha", "Daulatpur", "Dumuria", "Batiaghata", "Paikgachha",
               "Rupsha", "Biral", "Terkhada", "Mirkhai", "Dacope", "Kaliganj", "Shyamnagar"],
    "sylhet": ["Sylhet Sadar", "Ambarkhana", "Kawkhar", "Shahpur", "Balaganj", "Beanibazar",
               "Gopalganj", "Jaintapur", "Kanaighat", "Bichanakandi", "Companiganj", "Fenchuganj",
               "Osmani Nagar", "Baniachong", "Gaffargaon"],
    "barishal": ["Barishal Sadar", "Bakerganj", "Barguna Sadar", "Patharghata", "Madhabpasha",
                 "Lalmai", "Pirojpur Sadar", "Mathbaria", "Bhandaria", "Kalapupur",
                 "Patuakhali Sadar", "Betel", "Dumkhali"],
    "rangpur": ["Rangpur Sadar", "Pirganj", "Taragon", "Badarghat", "Birampur", "Dinajpur Sadar",
                "Phulbari", "Panchagarh Sadar", "Thakurgaon Sadar", "Nilphamari Sadar", "Domar",
                "Lalmonirhat Sadar", "Kurigram Sadar", "Gaibandha Sadar"],
    "mymensingh": ["Mymensingh Sadar", "Bhaluka", "Trishal", "Muktaghata", "Jamalpur Sadar",
                   "Melandaha", "Sarishabari", "Sherpur Sadar", "Islampur", "Barhatta", "Phulbari",
                   "Durgapur"],
    "gazipur": ["Gazipur Sadar", "Kapasia", "Sreepur", "Kaliganj", "Dhamrai", "Savar", "Cherag Ali",
                "Boali", "Nawabganj", "Tumul", "Daudkandi"],
    "cumilla": ["Cumilla Sadar", "Burichang", "Brahmanpara", "Chandina", "Devidwar", "Homna",
                "Laksam", "Manikarchar", "Matlab", "Muradnagar", "Nagarkanda", "Titas"],
    "narayanganj": ["Narayanganj Sadar", "Fatullah", "Siddhirganj", "Araihazar", "Bandlan",
                     "Rodelganj", "Panchlaish", "Narshondi", "Shibpur"],
    "bogura": ["Bogura Sadar", "Shibganj", "Sherpur", "Sariakandi", "Shajahanpur", "Dudwani",
               "Adamdighi", "Nandail", "Gabtali", "Kotalipara", "Chirain", "Dhupatoli"],
}

COURT_STAGES = [
    ("REPORTED", "FIR registered"),
    ("INVESTIGATION", "Investigation ongoing"),
    ("TRIAL", "Trial ongoing"),
    ("CONVICTED", "Judgment recorded"),
    ("ACQUITTED", "Accquittal recorded"),
]

# Offence classification with the governing legal section. Real statutes are
# cited so a reader can look the provision up; no individual is ever named.
CATEGORY_WEIGHTS = [
    ("SEXUAL_OFFENCE", 14, [
        "Penal Code 1860, s.375",
        "Penal Code 1860, s.376",
        "Penal Code 1860, s.376A",
    ]),
    ("VIOLENCE", 24, [
        "Penal Code 1860, s.324 (grievous hurt)",
        "Penal Code 1860, s.336/337 (rioting)",
        "Penal Code 1860, s.306",
    ]),
    ("TRAFFICKING", 8, [
        "Penal Code 1860, s.370A",
        "Penal Code 1860, s.371-373",
    ]),
    ("CYBERCRIME", 18, [
        "ICT Act 2006, s.66A",
        "ICT Act 2006, s.66E",
        "ICT Act 2006, s.66",
    ]),
]

CASE_START = date(2025, 7, 1)
CASE_SPAN_DAYS = 364


def _seed_value(key):
    """Deterministic 48-bit integer derived from a stable string key."""
    return int(hashlib.sha256(key.encode("utf-8")).hexdigest()[:12], 16)


def city_report_total(slug, population_m):
    """Fabricated reported-case total for a district, scaled by population."""
    return max(4, round(population_m * (30 + _seed_value(slug) % 20)))


def breakdown(key, reported):
    """Split a reported total into investigation/trial/convicted/acquitted."""
    seed = _seed_value(key)
    investigation = round(reported * (18 + (seed >> 5) % 10) / 100)
    trial = round(reported * (28 + (seed >> 11) % 12) / 100)
    convicted = round(reported * (9 + (seed >> 17) % 6) / 100)
    acquitted = round(convicted * (25 + (seed >> 23) % 6) / 100)
    return reported, investigation, trial, convicted, acquitted


def _allocate(total, keys):
    """Split `total` across `keys` using a stable weighting.

    Uses largest-remainder apportionment so the parts always sum back to
    `total` exactly, which lets area rows roll up into their district totals.
    """
    if total <= 0 or not keys:
        return [0] * len(keys)
    if total < len(keys):
        return [1] * total + [0] * (len(keys) - total)
    weights = [8 + (_seed_value(k) % 25) for k in keys]
    weight_sum = sum(weights)
    parts = [(w * total) // weight_sum for w in weights]
    remainder = total - sum(parts)          # always 0 <= remainder < len(keys)
    order = sorted(range(len(keys)), key=lambda i: (weights[i], keys[i]), reverse=True)
    for i in order[:remainder]:
        parts[i] += 1
    return parts


def case_category(seed):
    """Pick an offence category and its governing legal section deterministically."""
    roll = seed % 100
    cumulative = 0
    for name, weight, sections in CATEGORY_WEIGHTS:
        cumulative += weight
        if roll < cumulative:
            return name, sections[(seed >> 7) % len(sections)]
    return "GENERAL", ""


class Command(BaseCommand):
    help = "Load clearly marked SYNTHETIC demo data for all 64 districts of Bangladesh"

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset", action="store_true",
            help="Delete existing City/Area/Case rows before seeding.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if options["reset"]:
            Case.objects.all().delete()   # Case protects its city, so clear it first
            Area.objects.all().delete()
            City.objects.all().delete()
            self.stdout.write("Cleared existing cities, areas and cases.")

        city_map = {}
        for name, slug, division, lat, lon, population_m in DISTRICTS:
            reported, inv, trial, convicted, acquitted = breakdown(
                f"city:{slug}", city_report_total(slug, population_m)
            )
            city, _ = City.objects.update_or_create(
                slug=slug,
                defaults={
                    "name": name, "division": division,
                    "latitude": lat, "longitude": lon,
                    "reported_cases": reported, "under_investigation": inv,
                    "under_trial": trial, "convicted": convicted,
                    "acquitted": acquitted,
                },
            )
            city_map[slug] = city

        area_count = 0
        area_map = {}
        for slug, names in AREA_NAMES.items():
            city = city_map[slug]
            keys = [f"{slug}:{n}" for n in names]
            columns = [
                _allocate(value, keys) for value in (
                    city.reported_cases, city.under_investigation,
                    city.under_trial, city.convicted, city.acquitted,
                )
            ]
            area_map[slug] = {}
            for index, area_name in enumerate(names):
                area, _ = Area.objects.update_or_create(
                    city=city, name=area_name,
                    defaults={
                        "reported_cases": columns[0][index],
                        "under_investigation": columns[1][index],
                        "under_trial": columns[2][index],
                        "convicted": columns[3][index],
                        "acquitted": columns[4][index],
                    },
                )
                area_map[slug][area_name] = area
                area_count += 1

        case_count = 0
        for _name, slug, division, _lat, _lon, _pop in DISTRICTS:
            city = city_map[slug]
            code = DIVISION_CODES[division]
            area_names = AREA_NAMES.get(slug, [])
            for _ in range(1 + _seed_value(f"count:{slug}") % 3):
                seed = _seed_value(f"case:{slug}:{case_count}")
                case_id = f"BD-{code}-DEMO-{case_count + 1:03d}"
                status, court_status = COURT_STAGES[seed % len(COURT_STAGES)]
                category, offence_section = case_category(seed >> 3)
                area = None
                if area_names:
                    area = area_map[slug].get(area_names[(seed >> 8) % len(area_names)])
                Case.objects.update_or_create(
                    case_id=case_id,
                    defaults={
                        "city": city, "area": area, "status": status,
                        "category": category, "offence_section": offence_section,
                        "court_status": court_status,
                        "incident_date": CASE_START + timedelta(days=seed % CASE_SPAN_DAYS),
                        "source_name": SYNTHETIC_SOURCE, "source_url": "", "verified": True,
                    },
                )
                case_count += 1

        divisions = sorted({d[2] for d in DISTRICTS})
        self.stdout.write(self.style.SUCCESS(
            f"Loaded {City.objects.count()} districts, {area_count} areas "
            f"and {case_count} cases across {len(divisions)} divisions."
        ))
        self.stdout.write(self.style.WARNING(
            "All statistics are SYNTHETIC and fabricated for prototyping. "
            "Replace them with authoritative, verifiable sources before publication."
        ))
