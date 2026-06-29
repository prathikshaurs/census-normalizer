"""
Generate synthetic broker census files in deliberately messy, inconsistent formats.

Every broker sends employee census data differently. So this script fabricates that
chaos with 100% synthetic data (Faker) so the normalizer has realistic inputs to
clean, and so we never touch the treal PHI.

Each generated file mimics a different real-world broker quirk:
  - broker_a: tidy-ish but uses abbreviations (EE/SP/CH), M/F gender
  - broker_b: verbose headers, full words, dates as MM/DD/YYYY strings
  - broker_c: messy, mixed date formats, ZIPs missing leading zeros, blank cells,
              duplicate rows, an impossible DOB, a dependent with no matching employee
  - broker_d: Excel export with trailing whitespace, gender as 1/2, salary with $ and commas
"""

import os
import random
from datetime import date, timedelta

import pandas as pd
from faker import Faker

fake = Faker("en_US")
Faker.seed(42)
random.seed(42)

RAW_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "raw")
os.makedirs(RAW_DIR, exist_ok=True)


def _person(min_age=18, max_age=70):
    dob = fake.date_of_birth(minimum_age=min_age, maximum_age=max_age)
    return {
        "first": fake.first_name(),
        "last": fake.last_name(),
        "dob": dob,
        "zip": fake.zipcode(),
        "state": fake.state_abbr(),
    }


def _household(emp_id):
    # an employee plus 0-3 dependents that share a household id
    members = []
    emp = _person(22, 64)
    emp["emp_id"] = emp_id
    emp["relationship"] = "employee"
    emp["gender"] = random.choice(["M", "F"])
    members.append(emp)

    n_dep = random.choices([0, 1, 2, 3], weights=[40, 25, 20, 15])[0]
    if n_dep >= 1 and random.random() > 0.3:
        sp = _person(22, 64)
        sp["emp_id"] = emp_id
        sp["relationship"] = "spouse"
        sp["gender"] = "F" if emp["gender"] == "M" else "M"
        sp["last"] = emp["last"]
        sp["zip"] = emp["zip"]
        sp["state"] = emp["state"]
        members.append(sp)
    for _ in range(max(0, n_dep - 1)):
        ch = _person(0, 25)
        ch["emp_id"] = emp_id
        ch["relationship"] = "child"
        ch["gender"] = random.choice(["M", "F"])
        ch["last"] = emp["last"]
        ch["zip"] = emp["zip"]
        ch["state"] = emp["state"]
        members.append(ch)
    return members


def _base_population(n_employees):
    pop = []
    for i in range(1, n_employees + 1):
        pop.extend(_household(f"E{i:04d}"))
    return pop


# ---------- Broker A: abbreviations, M/F, ISO dates ----------
def broker_a(n=40):
    rows = []
    for m in _base_population(n):
        rel = {"employee": "EE", "spouse": "SP", "child": "CH"}[m["relationship"]]
        rows.append({
            "EmpID": m["emp_id"],
            "First Name": m["first"],
            "Last Name": m["last"],
            "DOB": m["dob"].isoformat(),       # 1985-03-12
            "Gender": m["gender"],             # M / F
            "Relationship": rel,               # EE / SP / CH
            "Zip": m["zip"],
            "State": m["state"],
        })
    return pd.DataFrame(rows)


# ---------- Broker B: verbose headers, full words, US date strings ----------
def broker_b(n=35):
    rows = []
    for m in _base_population(n):
        rows.append({
            "Employee Identifier": m["emp_id"],
            "Member First Name": m["first"],
            "Member Last Name": m["last"],
            "Date of Birth": m["dob"].strftime("%m/%d/%Y"),   # 03/12/1985
            "Sex": "Male" if m["gender"] == "M" else "Female",
            "Relationship to Subscriber": m["relationship"].capitalize(),
            "Zip Code": m["zip"],
            "Home State": m["state"],
        })
    return pd.DataFrame(rows)


# ---------- Broker C: maximally messy ----------
def broker_c(n=30):
    rows = []
    pop = _base_population(n)
    for m in pop:
        # mixed date formats within the same file
        fmt = random.choice(["%m/%d/%Y", "%m-%d-%Y", "%d/%m/%Y", "%Y/%m/%d"])
        zip_val = m["zip"]
        # simulate Excel dropping leading zeros on NE/MA zips
        if zip_val.startswith("0"):
            zip_val = str(int(zip_val))
        rows.append({
            "id": m["emp_id"],
            "fname": m["first"],
            "lname": m["last"],
            "birth_date": m["dob"].strftime(fmt),
            "gender": random.choice([m["gender"], m["gender"].lower()]),
            "rel": {"employee": "EE", "spouse": "Spouse", "child": "Dependent"}[m["relationship"]],
            "zipcode": zip_val,
            "st": m["state"],
        })

    df = pd.DataFrame(rows)

    # injecting realistic data-quality problems:
    # 1) a couple of fully duplicated rows
    df = pd.concat([df, df.iloc[[0, 5]]], ignore_index=True)
    # 2) a blank gender + blank zip
    df.loc[3, "gender"] = ""
    df.loc[7, "zipcode"] = None
    # 3) an impossible / future DOB
    df.loc[10, "birth_date"] = (date.today() + timedelta(days=365)).strftime("%m/%d/%Y")
    # 4) an orphan dependent: child pointing at an employee id that isn't present
    orphan = df.iloc[[2]].copy()
    orphan["id"] = "E9999"
    orphan["rel"] = "Dependent"
    df = pd.concat([df, orphan], ignore_index=True)
    return df


# ---------- Broker D: Excel cruft, gender 1/2, salary strings ----------
def broker_d(n=35):
    rows = []
    for m in _base_population(n):
        rows.append({
            "  Emp_ID  ": m["emp_id"],
            "  Name First ": "  " + m["first"] + " ",
            " Name Last ": m["last"] + "  ",
            "Birthdate": m["dob"].strftime("%Y-%m-%d"),
            "Gender Code": "1" if m["gender"] == "M" else "2",   # 1=male 2=female
            "Coverage Tier": {"employee": "Employee Only", "spouse": "Employee+Spouse",
                              "child": "Employee+Child"}[m["relationship"]],
            "Annual Salary": f"${random.randint(35,180)*1000:,}",
            "ZIP": m["zip"],
            "State": m["state"].lower(),
        })
    return pd.DataFrame(rows)


def main():
    broker_a().to_csv(os.path.join(RAW_DIR, "broker_a_census.csv"), index=False)
    broker_b().to_csv(os.path.join(RAW_DIR, "broker_b_census.csv"), index=False)
    broker_c().to_csv(os.path.join(RAW_DIR, "broker_c_census.csv"), index=False)
    broker_d().to_excel(os.path.join(RAW_DIR, "broker_d_census.xlsx"), index=False)
    print("Generated 4 synthetic census files in data/raw/:")
    for f in sorted(os.listdir(RAW_DIR)):
        print("  -", f)


if __name__ == "__main__":
    main()
