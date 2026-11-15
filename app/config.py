"""Plants, production lines, shifts, downtime reasons and OEE thresholds.

The plants stand in real Indonesian industrial estates (coordinates are real), but every
company name is FICTIONAL: the production numbers are simulated and must not be read as
data about any real factory.

OEE (Overall Equipment Effectiveness) = availability x performance x quality, the measure
introduced by Seiichi Nakajima for Total Productive Maintenance (TPM). The 85% "world class"
benchmark and the 65% "acceptable" floor are widely used industry conventions, not a
regulation; set your own targets per line before relying on the alerts.
"""
import os
from datetime import timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = Path(os.environ.get("OEE_DB", ROOT / "data" / "oee.db"))

WIB = timezone(timedelta(hours=7))  # Western Indonesia Time, no daylight saving

PLANTS = [
    {"id": "kiic", "name": "PT Sinar Logam Presisi", "estate": "KIIC", "city": "Karawang",
     "province": "Jawa Barat", "lat": -6.357, "lon": 107.293,
     "sector": {"en": "Automotive parts", "id": "Komponen otomotif"}},
    {"id": "suryacipta", "name": "PT Arunika Plastindo", "estate": "Suryacipta City of Industry",
     "city": "Karawang", "province": "Jawa Barat", "lat": -6.406, "lon": 107.358,
     "sector": {"en": "Plastic injection moulding", "id": "Cetak injeksi plastik"}},
    {"id": "jababeka", "name": "PT Embun Pagi Minuman", "estate": "Kawasan Industri Jababeka",
     "city": "Cikarang", "province": "Jawa Barat", "lat": -6.285, "lon": 107.165,
     "sector": {"en": "Beverages", "id": "Minuman"}},
    {"id": "mm2100", "name": "PT Pilar Baja Pipa", "estate": "MM2100", "city": "Cikarang Barat",
     "province": "Jawa Barat", "lat": -6.293, "lon": 107.091,
     "sector": {"en": "Steel pipe", "id": "Pipa baja"}},
    {"id": "batamindo", "name": "PT Selat Elektronika Presisi", "estate": "Batamindo Industrial Park",
     "city": "Batam", "province": "Kepulauan Riau", "lat": 1.048, "lon": 104.031,
     "sector": {"en": "Electronics assembly", "id": "Perakitan elektronik"}},
    {"id": "jiipe", "name": "PT Delta Kemasan Timur", "estate": "JIIPE", "city": "Gresik",
     "province": "Jawa Timur", "lat": -7.100, "lon": 112.600,
     "sector": {"en": "Packaging", "id": "Kemasan"}},
    {"id": "batang", "name": "PT Lintang Busana Jaya", "estate": "Kawasan Industri Terpadu Batang",
     "city": "Batang", "province": "Jawa Tengah", "lat": -6.935, "lon": 109.873,
     "sector": {"en": "Garments", "id": "Garmen"}},
]
PLANT_IDS = {p["id"] for p in PLANTS}

# ideal_cycle_s: the fastest sustainable time per unit (the line's rated speed).
# profile drives the simulator: how often the line stops, how fast it runs, how much it scraps.
#   steady      well-maintained line
#   average     typical line
#   struggling  old equipment or an unstable process
LINES = [
    {"id": "kiic-press-a", "plant_id": "kiic", "name": "Press line A", "ideal_cycle_s": 5.0,
     "product": {"en": "Body panels", "id": "Panel bodi"}, "profile": "steady"},
    {"id": "kiic-press-b", "plant_id": "kiic", "name": "Press line B", "ideal_cycle_s": 5.0,
     "product": {"en": "Brackets", "id": "Braket"}, "profile": "struggling"},
    {"id": "kiic-weld", "plant_id": "kiic", "name": "Robot welding cell", "ideal_cycle_s": 40.0,
     "product": {"en": "Sub-frames", "id": "Sub-rangka"}, "profile": "average"},
    {"id": "sury-imm-350", "plant_id": "suryacipta", "name": "Moulding 350 t", "ideal_cycle_s": 28.0,
     "product": {"en": "Dashboard parts", "id": "Komponen dasbor"}, "profile": "average"},
    {"id": "sury-imm-650", "plant_id": "suryacipta", "name": "Moulding 650 t", "ideal_cycle_s": 42.0,
     "product": {"en": "Bumpers", "id": "Bemper"}, "profile": "struggling"},
    {"id": "sury-assy", "plant_id": "suryacipta", "name": "Assembly line", "ideal_cycle_s": 18.0,
     "product": {"en": "Lamp housings", "id": "Rumah lampu"}, "profile": "steady"},
    {"id": "jbb-pet", "plant_id": "jababeka", "name": "PET filling line", "ideal_cycle_s": 0.15,
     "product": {"en": "600 ml bottled water", "id": "Air minum botol 600 ml"}, "profile": "steady"},
    {"id": "jbb-cup", "plant_id": "jababeka", "name": "Cup filling line", "ideal_cycle_s": 0.25,
     "product": {"en": "240 ml cups", "id": "Gelas 240 ml"}, "profile": "average"},
    {"id": "jbb-gallon", "plant_id": "jababeka", "name": "Gallon line", "ideal_cycle_s": 6.0,
     "product": {"en": "19 l gallons", "id": "Galon 19 l"}, "profile": "average"},
    {"id": "mm-erw", "plant_id": "mm2100", "name": "ERW pipe mill", "ideal_cycle_s": 12.0,
     "product": {"en": "Welded steel pipe", "id": "Pipa baja las"}, "profile": "average"},
    {"id": "mm-thread", "plant_id": "mm2100", "name": "Threading line", "ideal_cycle_s": 30.0,
     "product": {"en": "Threaded pipe", "id": "Pipa berulir"}, "profile": "struggling"},
    {"id": "btm-smt-1", "plant_id": "batamindo", "name": "SMT line 1", "ideal_cycle_s": 22.0,
     "product": {"en": "Control boards", "id": "Papan kendali"}, "profile": "steady"},
    {"id": "btm-smt-2", "plant_id": "batamindo", "name": "SMT line 2", "ideal_cycle_s": 22.0,
     "product": {"en": "Power boards", "id": "Papan daya"}, "profile": "average"},
    {"id": "btm-box", "plant_id": "batamindo", "name": "Box build", "ideal_cycle_s": 65.0,
     "product": {"en": "Network units", "id": "Unit jaringan"}, "profile": "steady"},
    {"id": "jiipe-corr", "plant_id": "jiipe", "name": "Corrugator", "ideal_cycle_s": 0.5,
     "product": {"en": "Carton sheets", "id": "Lembaran karton"}, "profile": "average"},
    {"id": "jiipe-film", "plant_id": "jiipe", "name": "Film bag line", "ideal_cycle_s": 2.0,
     "product": {"en": "Plastic bags", "id": "Kantong plastik"}, "profile": "struggling"},
    {"id": "btg-sew-a", "plant_id": "batang", "name": "Sewing line A", "ideal_cycle_s": 60.0,
     "product": {"en": "Shirts", "id": "Kemeja"}, "profile": "average"},
    {"id": "btg-sew-b", "plant_id": "batang", "name": "Sewing line B", "ideal_cycle_s": 75.0,
     "product": {"en": "Jackets", "id": "Jaket"}, "profile": "steady"},
    {"id": "btg-pack", "plant_id": "batang", "name": "Finishing & packing", "ideal_cycle_s": 20.0,
     "product": {"en": "Folded garments", "id": "Garmen terlipat"}, "profile": "average"},
]
LINE_IDS = {line["id"] for line in LINES}

# Three 8-hour shifts (WIB). Each has a 60-minute meal break, so the planned production
# time is 420 minutes per shift. `break_hour` is the local hour taken by the break.
SHIFTS = [
    {"key": "1", "start": 7, "break_hour": 11, "en": "Shift 1 (07:00-15:00)", "id": "Shift 1 (07.00-15.00)"},
    {"key": "2", "start": 15, "break_hour": 19, "en": "Shift 2 (15:00-23:00)", "id": "Shift 2 (15.00-23.00)"},
    {"key": "3", "start": 23, "break_hour": 3, "en": "Shift 3 (23:00-07:00)", "id": "Shift 3 (23.00-07.00)"},
]
SHIFT_HOURS = 8
BREAK_MINUTES = 60
PLANNED_MINUTES_PER_SHIFT = SHIFT_HOURS * 60 - BREAK_MINUTES  # 420

# Why a line stopped. Every stop inside planned production time is an availability loss.
DOWNTIME_REASONS = {
    "breakdown": {"en": "Machine breakdown", "id": "Kerusakan mesin"},
    "changeover": {"en": "Changeover", "id": "Ganti produk (changeover)"},
    "material": {"en": "Material shortage", "id": "Kekurangan material"},
    "quality_check": {"en": "Quality check", "id": "Pemeriksaan mutu"},
    "power": {"en": "Power outage (PLN)", "id": "Pemadaman listrik (PLN)"},
    "operator": {"en": "Operator absence", "id": "Operator tidak hadir"},
    "minor_stop": {"en": "Minor stops", "id": "Henti singkat"},
}

# OEE bands (fractions, checked from the top). Industry conventions, not a standard.
OEE_BANDS = [
    {"key": "world_class", "min": 0.85, "en": "World class", "id": "Kelas dunia", "color": "#1f9d6b"},
    {"key": "acceptable", "min": 0.65, "en": "Acceptable", "id": "Cukup", "color": "#2f7de1"},
    {"key": "low", "min": 0.0, "en": "Low", "id": "Rendah", "color": "#e4561f"},
]

# Alerts
OEE_ALERT = 0.65                 # a line's OEE over a shift below this raises an alert
DOWNTIME_ALERT_MINUTES = 30      # a single stop longer than this raises an alert
MIN_ALERT_PLANNED_MINUTES = 120  # judge a shift's OEE only after 2 h of planned time
