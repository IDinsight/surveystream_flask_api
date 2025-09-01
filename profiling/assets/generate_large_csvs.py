import csv
import random
from collections import defaultdict

# Read all lines from the sample locations file
with open("profiling/assets/sample_locations_medium.csv", "r") as f:
    reader = csv.reader(f)
    header = next(reader)
    rows = list(reader)

# Extract unique district_ids and psu_ids
unique_district_ids = set()
unique_psu_ids = set()
for row in rows:
    district_id = row[0]
    psu_id = row[-1]
    unique_district_ids.add(district_id)
    unique_psu_ids.add(psu_id)
unique_district_ids = sorted(list(unique_district_ids))
unique_psu_ids = sorted(list(unique_psu_ids))


# --- New logic for enumerators_large.csv ---
enum_header = [
    "enumerator_id1",
    "name1",
    "email1",
    "mobile_primary1",
    "language1",
    "home_address1",
    "gender1",
    "enumerator_type1",
    "district_id1",
    "mobile_secondary1",
    "age1",
]
num_enumerators = 2000
district_count = len(unique_district_ids)
enumerators_per_district = num_enumerators // district_count
extra_enum = num_enumerators % district_count

enumerators = []
enum_id = 1000001
languages = ["English", "Hindi", "Telugu"]
genders = ["Male", "Female"]
types = ["surveyor", "monitor;surveyor"]
for i, district_id in enumerate(unique_district_ids):
    count = enumerators_per_district + (1 if i < extra_enum else 0)
    for j in range(count):
        name = f"Name_{enum_id}"
        email = f"utkarsh.gupta+{enum_id}@idinsight.org"
        mobile_primary = f"9{str(enum_id).zfill(9)}"
        language = languages[(enum_id - 1000001) % len(languages)]
        home_address = f"Address {enum_id}"
        gender = genders[(enum_id - 1000001) % len(genders)]
        enumerator_type = types[(enum_id - 1000001) % len(types)]
        mobile_secondary = f"91{str(enum_id).zfill(9)}"
        age = 25 + ((enum_id - 1000001) % 20)
        enumerators.append(
            [
                enum_id,
                name,
                email,
                mobile_primary,
                language,
                home_address,
                gender,
                enumerator_type,
                district_id,
                mobile_secondary,
                age,
            ]
        )
        enum_id += 1

with open("profiling/assets/sample_enumerators_large.csv", "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(enum_header)
    writer.writerows(enumerators)

# --- New logic for targets_large.csv ---
target_header = [
    "target_id1",
    "language1",
    "gender1",
    "psu_id1",
    "name1",
    "mobile_primary1",
    "address1",
]
num_targets = 14999
psu_count = len(unique_psu_ids)
targets_per_psu = num_targets // psu_count
extra_targets = num_targets % psu_count

targets = []
target_id = 1
for i, psu_id in enumerate(unique_psu_ids):
    count = targets_per_psu + (1 if i < extra_targets else 0)
    for j in range(count):
        language = languages[(target_id - 1) % len(languages)]
        gender = genders[(target_id - 1) % len(genders)]
        name = f"Name_{target_id}"
        mobile_primary = f"9{str(target_id).zfill(9)}"
        address = f"Address {target_id}"
        targets.append(
            [target_id, language, gender, psu_id, name, mobile_primary, address]
        )
        target_id += 1

with open("profiling/assets/sample_targets_large.csv", "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(target_header)
    writer.writerows(targets)
