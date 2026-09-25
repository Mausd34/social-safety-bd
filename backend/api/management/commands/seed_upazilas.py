"""Load upazila (sub-district) reference data.

The names below are a hand-built DEMO set covering a subset of Bangladesh's
districts. They are good enough to exercise the chat/help routing end to end,
but they are NOT the authoritative list. Before any real deployment, replace
them with the official upazila gazetteer (LGED / Bangladesh Bureau of Statistics)
so every upazila in the country is present and correctly spelt.

This command is independent of `seed_demo` and is safe to re-run.
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.text import slugify

from api.models import City, Upazila

# district slug -> upazila names
UPAZILAS = {
    "rangpur": ["Rangpur Sadar", "Pirganj", "Taragon", "Badarghat", "Mithirdanga", "Birampur", "Gangachhari"],
    "dinajpur": ["Dinajpur Sadar", "Phulbari", "Birampur", "Chirain", "Parbatipur", "Nawabganj", "Hakimpur"],
    "nilphamari": ["Nilphamari Sadar", "Domar", "Dimla", "Jaldhaka"],
    "lalmonirhat": ["Lalmonirhat Sadar", "Adina", "Hatibandha", "Patgram", "Balapara"],
    "kurigram": ["Kurigram Sadar", "Ulpur", "Chilmari", "Rowmari", "Rajibari"],
    "gaibandha": ["Gaibandha Sadar", "Sadullapur", "Polibari", "Palashbari", "Fulchhari"],
    "panchagarh": ["Panchagarh Sadar", "Atwari", "Boda", "Tentulia", "Dewanganj"],
    "thakurgaon": ["Thakurgaon Sadar", "Pirganj", "Ballermara", "Ranisankail", "Haripur"],
    "bogura": ["Bogura Sadar", "Shibganj", "Sherpur", "Sariakandi", "Shajahanpur", "Dudwani",
               "Adamdighi", "Nandail", "Gabtali", "Kotalipara", "Chirain", "Dhupatoli"],
    "cumilla": ["Cumilla Sadar", "Burichang", "Brahmanpara", "Chandina", "Devidwar", "Homna",
                "Laksam", "Manikarchar", "Matlab", "Muradnagar", "Nagarkanda", "Titas",
                "Meghna", "Lakshmipur Sadar"],
    "brahmanbaria": ["Brahmanbaria Sadar", "Sarail", "Nakhail", "Kajla", "Akhaura", "Kasba", "Morichandi"],
    "chandpur": ["Chandpur Sadar", "Faridganj", "Kabilai", "Sudkpur", "Bashkail", "Shahjadpur",
                 "Hajiganj", "Khoshbas"],
    "lakshmipur": ["Lakshmipur Sadar", "Ramganj", "Raipura", "Companiganj"],
    "barishal": ["Barishal Sadar", "Bakerganj", "Betel", "Agailjhal", "Kankua", "Taltali", "Wazirpur", "Malap"],
    "barguna": ["Barguna Sadar", "Patharghata", "Lalmai", "Amtola"],
    "bhola": ["Bhola Sadar", "Egarasindur", "Nolitola", "Kalaiya"],
    "jhalokathi": ["Jhalokathi Sadar", "Kanthial", "Nalchity", "Amerkhasra"],
    "patuakhali": ["Patuakhali Sadar", "Kalapupur", "Bauphal", "Dumuria", "Mirkhai", "Galachipa", "Rangabali"],
    "pirojpur": ["Pirojpur Sadar", "Kawkhali", "Induri", "Mathbaria", "Nartola"],
    "khulna": ["Khulna Sadar", "Dumuria", "Batiaghata", "Paikgachha", "Boyra", "Biral",
               "Terkhada", "Dacope", "Mirkhai", "Amtola", "Kaliganj", "Shyamnagar"],
    "jashore": ["Jashore Sadar", "Chougachha", "Godragile", "Keshabpur", "Sreedharpur",
                "Manikpur", "Abjhul"],
    "jhenaidah": ["Jhenaidah Sadar", "Kaliganj", "Sreepur", "Kotwali", "Moheshpur", "Haridaha", "Maheshpur"],
    "satkhira": ["Satkhira Sadar", "Kalia", "Kaliganj", "Tushkhali", "Debidroganj", "Nalka", "Kalaroa"],
    "bagerhat": ["Bagerhat Sadar", "Morichganj", "Sarikal", "Khandura", "Rampathal"],
    "mymensingh": ["Mymensingh Sadar", "Trishal", "Muktaghata", "Bhaluka", "Gafargaon",
                   "Ishwarganj", "Haluaghat", "Tarakanda", "Fulbaria"],
    "jamalpur": ["Jamalpur Sadar", "Sarisabari", "Melandaha", "Jamalganj", "Deomganj",
                 "Bakshiganj", "Islampur"],
    "netrokona": ["Netrokona Sadar", "Kalmakanda", "Durgapur", "Katiadi", "Barhatta",
                  "Purbachal", "Madhupur", "Narsundi"],
    "sylhet": ["Sylhet Sadar", "Balaganj", "Biswanath", "Gopalganj", "Beanibazar", "Fenchuganj",
               "Osmaninagar", "Kanaighat", "Companiganj", "Bichanakandi", "Jaintapur", "Baniachong"],
    "sunamganj": ["Sunamganj Sadar", "Salla", "Jamalganj", "Chhatak", "Chhata", "Madhyanagar"],
    "habiganj": ["Habiganj Sadar", "Chunarhat", "Kulaura", "Haripur", "Shyamganj",
                 "Nabiganj", "Bahadurpur", "Luxmibazar"],
    "gazipur": ["Gazipur Sadar", "Kapasia", "Kaliganj", "Sreepur", "Nawabganj", "Boali", "Chandrura"],
    "narayanganj": ["Narayanganj Sadar", "Fatullah", "Siddhirganj", "Araihazar", "Bandlan",
                    "Rodelganj", "Panchlaish", "Narshondi", "Shibpur"],
    "dhaka": ["Savar", "Dhamrai", "Keraniganj", "Uttara East", "Uttara West", "Cantonment",
              "Paltan", "Shahjahanpur", "Ramna", "Tejgaon", "Gulshan", "Motijheel",
              "Khilgaon", "Badda", "Kafrul", "Sabujbagh", "Shahbagh", "Kalabagan",
              "Farmgate", "Banani", "Baridhara"],
    "tangail": ["Tangail Sadar", "Kalihati", "Bhuapur", "Delduar", "Ghata", "Madhupur",
                "Mirzapur", "Nagarkanda", "Basail"],
    "chattogram": ["Chattogram Sadar", "Kotwali", "Pahartali", "Mirsarai", "Rangunia",
                   "Boalkhali", "Anwara", "Sandwip", "Sitakunda", "Karnaphuli", "Fatikchhari",
                   "Kumbhkhali", "Lama"],
    "coxs-bazar": ["Cox's Bazar Sadar", "Ramu", "Ukhiya", "Teknaf", "Chakma", "Peik"],
    "rajshahi": ["Rajshahi Sadar", "Boalia", "Kazla", "Motijheel", "Shahidbag", "Kachhari",
                 "Charghat", "Bagha", "Puthia", "Durgapur", "Bagmara", "Godagari", "Palpara",
                 "Mohanpur", "Patani", "Sonatoy"],
}


class Command(BaseCommand):
    help = "Load upazila reference data (demo gazetteer - replace with the official LGED list)"

    @transaction.atomic
    def handle(self, *args, **options):
        created = updated = 0
        missing = []
        for district_slug, names in UPAZILAS.items():
            district = City.objects.filter(slug=district_slug).first()
            if not district:
                missing.append(district_slug)
                continue
            for name in names:
                slug = slugify(f"{district_slug}-{name}")
                _obj, was_created = Upazila.objects.update_or_create(
                    district=district, name=name, defaults={"slug": slug}
                )
                created += was_created
                updated += not was_created
        self.stdout.write(self.style.SUCCESS(
            f"Loaded {Upazila.objects.count()} upazilas "
            f"({created} created, {updated} updated) across {len(UPAZILAS) - len(missing)} districts."
        ))
        if missing:
            self.stdout.write(self.style.WARNING(
                f"Skipped unknown district slugs: {', '.join(missing)} (run seed_demo first)."
            ))
        self.stdout.write(self.style.WARNING(
            "This gazetteer is a partial DEMO list. Replace it with the official "
            "LGED/BBS upazila list before deployment."
        ))
