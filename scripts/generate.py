"""Generate realistic, messy veterinary practice-management (PIMS) exports plus wellness-plan app data.

Everything here is synthetic. It reproduces the problems a wellness-plan company runs into when it ingests
data from many clinics on different PIMS:

  * two PIMS with different shapes: a Cornerstone-style CSV export and an AllyDVM-style JSONL API dump
  * repeated extracts of the same appointment with changing status (latest extract must win)
  * local clinic time in one system, UTC in the other
  * invoice totals that include tax in one system and exclude it in the other, plus manual adjustments
  * a clinic that migrated from Cornerstone to AllyDVM mid-year, so history exists in both systems
  * stale "booked" appointments left behind in the old system after the cutover
  * owners and pets spelled differently in the app and in the PIMS
  * item codes that differ per PIMS, and new codes nobody mapped yet
  * a feed that stopped arriving (stale source)

Usage: python scripts/generate.py [--scale 1.0] [--seed 7]
"""
import argparse, csv, json, random, uuid, os
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

p = argparse.ArgumentParser()
p.add_argument("--scale", type=float, default=1.0)
p.add_argument("--seed", type=int, default=7)
p.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "..", "data", "raw"))
a = p.parse_args()
R = random.Random(a.seed)
OUT = os.path.abspath(a.out)
os.makedirs(OUT, exist_ok=True)

NOW = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
START = date(NOW.year - 1, NOW.month, 1)
TODAY = NOW.date()
CUTOVER = date(TODAY.year, TODAY.month, 1) - timedelta(days=150)
CUTOVER = CUTOVER.replace(day=1)


def uid():
    return str(uuid.UUID(int=R.getrandbits(128)))


FIRST = "Olivia Liam Emma Noah Ava Elijah Sophia James Isabella Lucas Mia Mason Amelia Ethan Harper Logan Evelyn Aiden Abigail Jackson Emily Sebastian Ella Mateo Avery Henry Scarlett Owen Grace Wyatt Chloe Jack Layla Leo Riley Daniel Zoey Levi Nora Michael Lily".split()
LAST = "Smith Johnson Williams Brown Jones Garcia Miller Davis Rodriguez Martinez Hernandez Lopez Gonzalez Wilson Anderson Thomas Taylor Moore Jackson Martin Lee Perez Thompson White Harris Sanchez Clark Ramirez Lewis Robinson Walker Young Allen King Wright Scott Torres Nguyen Hill Flores Green Adams Nelson Baker Hall Rivera Campbell Mitchell Carter Roberts".split()
DOGS = "Bella Luna Charlie Lucy Cooper Max Bailey Daisy Sadie Lola Buddy Molly Stella Tucker Bear Zoey Duke Harley Maggie Jax Bentley Milo Oliver Riley Rocky Penny Sophie Chloe Jack Lily Murphy Winston Gus Rosie Ruby Teddy Biscuit Pepper Mochi Koda".split()
CATS = "Luna Bella Oliver Leo Milo Charlie Lucy Kitty Nala Simba Loki Cleo Willow Jasper Pepper Smokey Shadow Tiger Mittens Gizmo Salem Coco Ziggy Pumpkin Olive".split()
DOG_BREEDS = ["Labrador Retriever", "Golden Retriever", "French Bulldog", "German Shepherd", "Poodle Mix", "Beagle", "Mixed Breed", "Dachshund"]
CAT_BREEDS = ["Domestic Shorthair", "Domestic Longhair", "Siamese", "Maine Coon", "Ragdoll"]

CLINICS = [
    # id, name, pims, practice id, timezone, tax rate
    ("c1", "Riverbend Animal Hospital", "cornerstone", "CS-1041", "America/New_York", 0.06),
    ("c2", "Oak Street Veterinary", "cornerstone", "CS-2210", "America/Chicago", 0.0725),
    ("c3", "Lakeside Pet Clinic", "cornerstone", "CS-3307", "America/Denver", 0.029),
    ("c4", "Summit Vet Care", "allydvm", "AD-7f3a", "America/Los_Angeles", 0.0725),
    ("c5", "Harbor Paws Veterinary", "allydvm", "AD-91c2", "America/New_York", 0.0),
    ("c6", "Maple Grove Animal Clinic", "migrated", None, "America/Chicago", 0.0625),  # Cornerstone -> AllyDVM
]
CLINIC_IDS = {c[0]: uid() for c in CLINICS}
MAPLE_CS, MAPLE_AD = "CS-4418", "AD-c6e0"

# canonical service -> (cornerstone code(s), ally sku(s), price in cents)
SERVICES = {
    "exam_wellness": (["1001"], ["exam-wellness"], 6800),
    "exam_sick": (["1002"], ["exam-problem"], 7800),
    "vaccine_rabies": (["V-RAB1", "V-RAB3"], ["rabies-1yr", "rabies-3yr"], 3200),
    "vaccine_dhpp": (["V-DHPP"], ["dhpp"], 3600),
    "vaccine_fvrcp": (["V-FVRCP"], ["fvrcp"], 3400),
    "vaccine_bordetella": (["V-BORD"], ["bordetella-oral"], 3100),
    "vaccine_lepto": (["V-LEPTO"], ["lepto"], 3300),
    "fecal_test": (["L-FEC"], ["fecal-float"], 4500),
    "heartworm_test": (["L-HW4DX", "L-4DXP"], ["snap-4dx"], 5900),  # L-4DXP is a new code, deliberately unmapped
    "wellness_bloodwork": (["L-CBC", "L-CHEM"], ["cbc", "chem-17"], 14500),
    "dental_cleaning": (["D-CLEAN"], ["dental-prophy"], 52000),
    "nail_trim": (["G-NAIL"], ["nail-trim"], 2200),
    "microchip": (["M-CHIP"], ["microchip"], 5500),
    "xray": (["R-XR2"], ["rad-2view"], 21000),
    "surgery_spay_neuter": (["S-SPAY", "S-NEUT"], ["spay", "neuter"], 48000),
    "medication": (["RX-APOQ", "RX-CARP", "RX-AMOX"], ["rx-apoquel", "rx-carprofen", "rx-amoxicillin"], 4800),
    "flea_tick_prevention": (["P-FLEA"], ["nexgard"], 7600),
}
DESCR = {k: k.replace("_", " ").title() for k in SERVICES}

PLANS = [  # plan code, species, monthly price cents
    ("ESSENTIAL", "dog", 3900), ("ESSENTIAL", "cat", 2900),
    ("PLUS", "dog", 5900), ("PLUS", "cat", 4900),
    ("COMPLETE", "dog", 8900), ("COMPLETE", "cat", 7400),
]


def rand_date(d0, d1):
    return d0 + timedelta(days=R.randint(0, max(0, (d1 - d0).days)))


def messy_email(e):
    r = R.random()
    if r < 0.15: return e.upper()
    if r < 0.25: return " " + e + " "
    if r < 0.30: return e.replace("@", "+vet@")
    return e


def phone():
    return f"{R.randint(201, 989)}{R.randint(200, 999)}{R.randint(1000, 9999)}"


def fmt_phone(ph, style):
    if style == 0: return f"({ph[:3]}) {ph[3:6]}-{ph[6:]}"
    if style == 1: return f"{ph[:3]}-{ph[3:6]}-{ph[6:]}"
    if style == 2: return f"+1{ph}"
    return ph


# ---------------------------------------------------------------- owners and pets
members, app_pets, memberships, payments = [], [], [], []
owners = []  # every pet owner across clinics, members and non-members
n_owners = int(2600 * a.scale)
for i in range(n_owners):
    fn, ln = R.choice(FIRST), R.choice(LAST)
    email = f"{fn.lower()}.{ln.lower()}{R.randint(1, 999)}@{R.choice(['gmail.com', 'yahoo.com', 'outlook.com', 'icloud.com'])}"
    clinic = R.choices(CLINICS, weights=[22, 18, 14, 18, 12, 16])[0]
    is_member = R.random() < 0.55
    o = dict(fn=fn, ln=ln, email=email, phone=phone(), clinic=clinic, member=is_member, pets=[])
    for _ in range(R.choices([1, 2, 3], weights=[70, 24, 6])[0]):
        sp = R.choices(["dog", "cat"], weights=[68, 32])[0]
        name = R.choice(DOGS if sp == "dog" else CATS)
        while any(pp["name"] == name for pp in o["pets"]):
            name = R.choice(DOGS if sp == "dog" else CATS)
        dob = rand_date(date(2010, 1, 1), TODAY - timedelta(days=90))
        pet = dict(name=name, species=sp, dob=dob, breed=R.choice(DOG_BREEDS if sp == "dog" else CAT_BREEDS),
                   deceased=(R.random() < 0.012), enrolled=False)
        if pet["deceased"]:
            pet["deceased_on"] = rand_date(START + timedelta(days=60), TODAY - timedelta(days=10))
        o["pets"].append(pet)
    owners.append(o)

for o in owners:
    if not o["member"]:
        continue
    created = datetime.combine(rand_date(START - timedelta(days=200), TODAY - timedelta(days=5)), datetime.min.time(), timezone.utc) + timedelta(minutes=R.randint(0, 1439))
    o["member_id"] = uid()
    members.append(dict(member_id=o["member_id"], email=messy_email(o["email"]), phone=fmt_phone(o["phone"], R.randint(0, 3)),
                        first_name=o["fn"], last_name=o["ln"] if R.random() > 0.04 else o["ln"] + "-" + R.choice(LAST),
                        created_at=created.isoformat()))
    for pet in o["pets"]:
        if R.random() < 0.85:
            pet["enrolled"] = True
            pet["pet_id"] = uid()
            pet["not_in_pims"] = R.random() < 0.03  # enrolled in the app, never registered at the clinic yet
            app_name = pet["name"]
            r = R.random()
            if r < 0.05: app_name = f"{pet['name']} {o['ln']}"
            elif r < 0.09: app_name = pet["name"].lower()
            elif r < 0.12: app_name = pet["name"] + "y" if not pet["name"].endswith("y") else pet["name"][:-1]
            app_pets.append(dict(pet_id=pet["pet_id"], member_id=o["member_id"], clinic_id=CLINIC_IDS[o["clinic"][0]],
                                 name=app_name, species=pet["species"],
                                 birth_date=pet["dob"].isoformat() if R.random() > 0.2 else "",
                                 created_at=created.isoformat()))
            plan = R.choices(["ESSENTIAL", "PLUS", "COMPLETE"], weights=[45, 38, 17])[0]
            price = [pp[2] for pp in PLANS if pp[0] == plan and pp[1] == pet["species"]][0]
            start = max(created.date(), START - timedelta(days=200))
            cancel = None
            if R.random() < 0.14:
                cancel = rand_date(start + timedelta(days=40), TODAY)
            pet["membership"] = dict(membership_id=uid(), pet_id=pet["pet_id"], plan_code=plan, started_at=start.isoformat(),
                                     cancelled_at=cancel.isoformat() if cancel else "", monthly_price_cents=price)
            memberships.append(pet["membership"])
            # monthly charges
            d = start
            while d <= (cancel or TODAY):
                if d >= START - timedelta(days=31):
                    st = "succeeded" if R.random() > 0.045 else "failed"
                    payments.append(dict(payment_id=uid(), membership_id=pet["membership"]["membership_id"],
                                         charged_at=datetime.combine(d, datetime.min.time(), timezone.utc).replace(hour=R.randint(6, 9)).isoformat(),
                                         amount_cents=price, status=st))
                    if st == "failed" and R.random() < 0.7:
                        payments.append(dict(payment_id=uid(), membership_id=pet["membership"]["membership_id"],
                                             charged_at=datetime.combine(d + timedelta(days=3), datetime.min.time(), timezone.utc).replace(hour=8).isoformat(),
                                             amount_cents=price, status="succeeded"))
                m = d.month + 1
                d = d.replace(year=d.year + (m > 12), month=(m - 1) % 12 + 1, day=min(d.day, 28))
            if cancel and R.random() < 0.3:
                payments.append(dict(payment_id=uid(), membership_id=pet["membership"]["membership_id"],
                                     charged_at=datetime.combine(cancel, datetime.min.time(), timezone.utc).replace(hour=15).isoformat(),
                                     amount_cents=-price, status="refunded"))
    # a few members signed up but their pet is registered at a different clinic in the PIMS (wrong clinic chosen in app)
    if R.random() < 0.025:
        o["clinic_override"] = R.choice([c for c in CLINICS if c != o["clinic"]])

# ---------------------------------------------------------------- PIMS records
cs_clients, cs_patients, cs_appts, cs_inv, cs_items = [], [], [], [], []
ad_clients, ad_patients, ad_appts, ad_inv = [], [], [], []
cs_next = {"client": 1000, "patient": 5000, "appt": 900000, "inv": 300000}


def cs_id(kind):
    cs_next[kind] += R.randint(1, 3)
    return str(cs_next[kind])


def local_to_utc(d_local: datetime, tz):
    return d_local.replace(tzinfo=ZoneInfo(tz)).astimezone(timezone.utc)


def visit_lines(pet, kind):
    lines = []
    if kind == "wellness":
        lines.append("exam_wellness")
        core = ["vaccine_rabies", "vaccine_dhpp"] if pet["species"] == "dog" else ["vaccine_rabies", "vaccine_fvrcp"]
        lines += [s for s in core if R.random() < 0.55]
        if pet["species"] == "dog":
            if R.random() < 0.45: lines.append("heartworm_test")
            if R.random() < 0.3: lines.append("vaccine_bordetella")
            if R.random() < 0.25: lines.append("vaccine_lepto")
        if R.random() < 0.4: lines.append("fecal_test")
        if R.random() < 0.25: lines.append("wellness_bloodwork")
        if R.random() < 0.3: lines.append("nail_trim")
        if R.random() < 0.35: lines.append("flea_tick_prevention")
    elif kind == "sick":
        lines.append("exam_sick")
        if R.random() < 0.6: lines.append("medication")
        if R.random() < 0.2: lines.append("xray")
        if R.random() < 0.15: lines.append("wellness_bloodwork")
    elif kind == "dental":
        lines += ["exam_wellness", "dental_cleaning"]
        if R.random() < 0.5: lines.append("wellness_bloodwork")
    elif kind == "surgery":
        lines += ["exam_wellness", "surgery_spay_neuter", "medication"]
    return lines


extract_times_cs = [NOW - timedelta(days=d, hours=R.randint(1, 5)) for d in (63, 35, 14, 1)] + [NOW - timedelta(hours=3)]
APPT_TYPES = [("wellness", 60), ("sick", 28), ("dental", 7), ("surgery", 5)]

for o in owners:
    clinic = o.get("clinic_override", o["clinic"])
    cid, cname, pims, practice, tz, tax = clinic
    systems = []
    if pims == "cornerstone": systems = [("cs", practice, START, TODAY + timedelta(days=60))]
    elif pims == "allydvm": systems = [("ad", practice, START, TODAY + timedelta(days=60))]
    else:  # migrated clinic: history in Cornerstone until cutover, AllyDVM from cutover (with imported recent history)
        systems = [("cs", MAPLE_CS, START, CUTOVER - timedelta(days=1)), ("ad", MAPLE_AD, CUTOVER - timedelta(days=75), TODAY + timedelta(days=60))]
    ph_style = R.randint(0, 3)
    ids = {}
    for sysname, prac, d0, d1 in systems:
        email_in_pims = o["email"] if R.random() > 0.08 else ""
        if sysname == "cs":
            cl = cs_id("client")
            cs_clients.append(dict(CLIENT_ID=cl, PRACTICE_ID=prac, FIRST_NAME=o["fn"].upper(), LAST_NAME=o["ln"].upper(),
                                   EMAIL=email_in_pims, PHONE=fmt_phone(o["phone"], ph_style), EXTRACTED_AT=extract_times_cs[-1].isoformat()))
        else:
            cl = uid()
            ad_clients.append(dict(clientGuid=cl, practiceId=prac, name=f"{o['ln']}, {o['fn']}",
                                   emails=[email_in_pims] if email_in_pims else [], phones=[fmt_phone(o["phone"], 2)],
                                   updatedAt=(NOW - timedelta(hours=R.randint(2, 30))).isoformat()))
        ids[sysname] = {"client": cl}
    for pet in o["pets"]:
        if pet.get("not_in_pims"):
            continue
        pet_sys = {}
        for sysname, prac, d0, d1 in systems:
            if sysname == "cs":
                pid = cs_id("patient")
                cs_patients.append(dict(PATIENT_ID=pid, CLIENT_ID=ids["cs"]["client"], PRACTICE_ID=prac, PATIENT_NAME=pet["name"].upper(),
                                        SPECIES="CANINE" if pet["species"] == "dog" else "FELINE", BREED=pet["breed"],
                                        BIRTH_DATE=pet["dob"].strftime("%m/%d/%Y") if R.random() > 0.05 else "",
                                        DECEASED="Y" if pet["deceased"] else "N",
                                        DECEASED_DATE=pet["deceased_on"].strftime("%m/%d/%Y") if pet["deceased"] else "",
                                        EXTRACTED_AT=extract_times_cs[-1].isoformat()))
            else:
                pid = uid()
                ad_patients.append(dict(patientGuid=pid, clientGuid=ids["ad"]["client"], practiceId=prac, name=pet["name"],
                                        species="Dog" if pet["species"] == "dog" else "Cat", breed=pet["breed"],
                                        dateOfBirth=pet["dob"].isoformat(),
                                        deceasedAt=pet["deceased_on"].isoformat() if pet["deceased"] else None,
                                        updatedAt=(NOW - timedelta(hours=R.randint(2, 30))).isoformat()))
            pet_sys[sysname] = pid
        # visits across the year (members use the plan more)
        rate = 5.5 if pet.get("enrolled") else 2.2
        n = max(0, int(R.gauss(rate, 1.6)))
        days = sorted(R.sample(range((START - START).days, (TODAY + timedelta(days=45) - START).days), k=min(n, 200)))
        for dd in days:
            vday = START + timedelta(days=dd)
            if pet["deceased"] and vday > pet["deceased_on"]:
                continue
            kind = R.choices([k for k, _ in APPT_TYPES], weights=[w for _, w in APPT_TYPES])[0]
            local = datetime.combine(vday, datetime.min.time()).replace(hour=R.randint(8, 17), minute=R.choice([0, 15, 30, 45]))
            future = vday > TODAY
            final = "booked" if future else R.choices(["completed", "no_show", "cancelled"], weights=[83, 6, 11])[0]
            lines = visit_lines(pet, kind) if final == "completed" else []
            # which system(s) recorded it
            recs = [s for s in systems if s[2] <= vday <= s[3]]
            if pims == "migrated" and CUTOVER <= vday <= CUTOVER + timedelta(days=45) and R.random() < 0.5:
                # booked in Cornerstone before the switch, never updated again: an orphan in the old system
                local_o = local.replace(hour=R.randint(8, 17))
                cs_appts.append(dict(APPT_ID=cs_id("appt"), PRACTICE_ID=MAPLE_CS, PATIENT_ID=pet_sys["cs"],
                                     APPT_DATE=local_o.strftime("%m/%d/%Y"), APPT_TIME=local_o.strftime("%I:%M %p"),
                                     REASON=kind.upper(), DURATION_MIN="30", STATUS="S",
                                     EXTRACTED_AT=datetime.combine(CUTOVER - timedelta(days=2), datetime.min.time(), timezone.utc).isoformat()))
            for sysname, prac, d0, d1 in recs:
                imported = (pims == "migrated" and sysname == "ad" and vday < CUTOVER)
                if sysname == "cs":
                    appt_id = cs_id("appt")
                    status_code = {"completed": "C", "no_show": "N", "cancelled": "X", "booked": "S"}[final]
                    # migrated clinic: appointments booked in Cornerstone for after the cutover stay 'S' forever
                    base = dict(APPT_ID=appt_id, PRACTICE_ID=prac, PATIENT_ID=pet_sys["cs"], APPT_DATE=local.strftime("%m/%d/%Y"),
                                APPT_TIME=local.strftime("%I:%M %p"), REASON=kind.upper(), DURATION_MIN=str(R.choice([15, 30, 45, 60])))
                    for et in extract_times_cs:
                        booked_at = datetime.combine(vday - timedelta(days=R.randint(3, 40)), datetime.min.time(), timezone.utc)
                        if et < booked_at:
                            continue
                        appt_utc = local_to_utc(local, tz)
                        st = status_code if et >= appt_utc + timedelta(hours=6) else "S"
                        if st == "S" and et >= appt_utc and R.random() < 0.5:
                            st = "I"  # checked in at extract time
                        cs_appts.append(dict(base, STATUS=st, EXTRACTED_AT=et.isoformat()))
                    if final == "completed" and lines:
                        inv = cs_id("inv")
                        items, net = [], 0
                        for ln_no, s in enumerate(lines, 1):
                            code = R.choice(SERVICES[s][0])
                            qty = 1
                            price = int(SERVICES[s][2] * R.uniform(0.85, 1.25))
                            disc = 0 if R.random() > 0.08 else int(price * 0.1)
                            ext = qty * price - disc
                            net += ext
                            items.append(dict(INVOICE_NO=inv, PRACTICE_ID=prac, LINE_NO=str(ln_no), ITEM_CODE=code,
                                              DESCRIPTION=DESCR[s].upper(), QTY=str(qty), UNIT_PRICE=f"{price / 100:.2f}",
                                              DISCOUNT=f"{disc / 100:.2f}", EXTENDED=f"{ext / 100:.2f}"))
                        total = round(net * (1 + tax))
                        if R.random() < 0.025:
                            total += R.choice([-500, -250, 300, 1000])  # manual adjustment at the front desk
                        state = "P" if R.random() > 0.015 else "V"
                        cs_inv.append(dict(INVOICE_NO=inv, PRACTICE_ID=prac, CLIENT_ID=ids["cs"]["client"], PATIENT_ID=pet_sys["cs"],
                                           INVOICE_DATE=local.strftime("%m/%d/%Y"), TOTAL=f"${total / 100:,.2f}", STATUS=state,
                                           EXTRACTED_AT=extract_times_cs[-1].isoformat()))
                        cs_items.extend(items)
                        if state == "V":  # re-issued correctly
                            inv2 = cs_id("inv")
                            cs_inv.append(dict(INVOICE_NO=inv2, PRACTICE_ID=prac, CLIENT_ID=ids["cs"]["client"], PATIENT_ID=pet_sys["cs"],
                                               INVOICE_DATE=local.strftime("%m/%d/%Y"), TOTAL=f"${round(net * (1 + tax)) / 100:,.2f}", STATUS="P",
                                               EXTRACTED_AT=extract_times_cs[-1].isoformat()))
                            cs_items.extend([dict(it, INVOICE_NO=inv2) for it in items])
                else:
                    agid = uid()
                    start_utc = local_to_utc(local, tz)
                    st_map = {"completed": "Completed", "no_show": "NoShow", "cancelled": "Cancelled", "booked": "Booked"}
                    versions = [("Booked", start_utc - timedelta(days=R.randint(3, 30)))]
                    if final != "booked":
                        versions.append((st_map[final], start_utc + timedelta(hours=R.randint(1, 8))))
                    stale_feed = (prac == "AD-91c2")
                    for st, upd in versions:
                        if upd > NOW - (timedelta(days=3) if stale_feed else timedelta(0)):
                            continue
                        ad_appts.append(dict(appointmentGuid=agid, practiceId=prac, patientGuid=pet_sys["ad"],
                                             startAt=start_utc.strftime("%Y-%m-%dT%H:%M:%SZ"), durationMinutes=R.choice([15, 30, 45, 60]),
                                             type=kind, status=st, source="import:cornerstone" if imported else "native",
                                             updatedAt=upd.isoformat()))
                    if final == "completed" and lines and not imported:
                        inv_lines, net = [], 0
                        for s in lines:
                            sku = R.choice(SERVICES[s][1])
                            price = int(SERVICES[s][2] * R.uniform(0.85, 1.25))
                            disc = 0 if R.random() > 0.08 else int(price * 0.1)
                            net += price - disc
                            inv_lines.append(dict(sku=sku, description=DESCR[s], quantity=1, unitPriceCents=price, discountCents=disc))
                        posted = start_utc + timedelta(hours=R.randint(1, 3))
                        if stale_feed and posted > NOW - timedelta(days=3):
                            continue
                        ad_inv.append(dict(invoiceGuid=uid(), practiceId=prac, clientGuid=ids["ad"]["client"], patientGuid=pet_sys["ad"],
                                           postedAt=posted.isoformat(), totalCents=net + (0 if R.random() > 0.01 else 199),
                                           taxCents=round(net * tax), state="posted" if R.random() > 0.012 else "voided",
                                           lines=inv_lines, updatedAt=posted.isoformat()))

# ---------------------------------------------------------------- app reference tables
app_clinics = [dict(clinic_id=CLINIC_IDS[c[0]], name=c[1], timezone=c[4], sales_tax_rate=c[5],
                    onboarded_at=(START - timedelta(days=R.randint(100, 400))).isoformat()) for c in CLINICS]
links = []
for c in CLINICS:
    if c[2] == "migrated":
        links.append(dict(clinic_id=CLINIC_IDS[c[0]], pims="cornerstone", practice_id=MAPLE_CS, active_from=(START - timedelta(days=400)).isoformat(), active_to=(CUTOVER - timedelta(days=1)).isoformat()))
        links.append(dict(clinic_id=CLINIC_IDS[c[0]], pims="allydvm", practice_id=MAPLE_AD, active_from=CUTOVER.isoformat(), active_to=""))
    else:
        links.append(dict(clinic_id=CLINIC_IDS[c[0]], pims=c[2], practice_id=c[3], active_from=(START - timedelta(days=400)).isoformat(), active_to=""))


def wcsv(name, rows):
    with open(os.path.join(OUT, name), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)


def wjsonl(name, rows):
    with open(os.path.join(OUT, name), "w") as f:
        for r in rows: f.write(json.dumps(r) + "\n")


R.shuffle(cs_appts)
wcsv("cornerstone_clients.csv", cs_clients); wcsv("cornerstone_patients.csv", cs_patients)
wcsv("cornerstone_appointments.csv", cs_appts); wcsv("cornerstone_invoices.csv", cs_inv); wcsv("cornerstone_invoice_items.csv", cs_items)
wjsonl("allydvm_clients.jsonl", ad_clients); wjsonl("allydvm_patients.jsonl", ad_patients)
wjsonl("allydvm_appointments.jsonl", ad_appts); wjsonl("allydvm_invoices.jsonl", ad_inv)
wcsv("app_members.csv", members); wcsv("app_pets.csv", app_pets); wcsv("app_memberships.csv", memberships)
wcsv("app_payments.csv", payments); wcsv("app_clinics.csv", app_clinics); wcsv("app_clinic_pims_links.csv", links)
with open(os.path.join(OUT, "_manifest.json"), "w") as f:
    json.dump(dict(generated_at=NOW.isoformat(), seed=a.seed, scale=a.scale, window_start=START.isoformat(), cutover=CUTOVER.isoformat()), f)

print(f"cornerstone: {len(cs_clients)} clients, {len(cs_patients)} patients, {len(cs_appts)} appointment rows, {len(cs_inv)} invoices, {len(cs_items)} lines")
print(f"allydvm:     {len(ad_clients)} clients, {len(ad_patients)} patients, {len(ad_appts)} appointment rows, {len(ad_inv)} invoices")
print(f"app:         {len(members)} members, {len(app_pets)} pets, {len(memberships)} memberships, {len(payments)} payments")
