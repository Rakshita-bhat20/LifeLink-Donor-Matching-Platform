"""Load demo data:  python -m backend.seed

Demo logins (password in brackets):
    admin@lifelink.test    (Admin@1234)
    hospital@lifelink.test (Hospital@123)   - Victoria Hospital, Bengaluru
    donor@lifelink.test    (Donor@1234)     - a donor with a ready profile
"""
from datetime import date, timedelta

from werkzeug.security import generate_password_hash

from .app import create_app
from .models import repo
from .models.db import get_db
from .services import audit

CITIES = {
    "Bengaluru": (12.9716, 77.5946), "Whitefield": (12.9698, 77.7500),
    "Jayanagar": (12.9250, 77.5938), "Yelahanka": (13.1007, 77.5963),
    "Hosur": (12.7409, 77.8253), "Tumakuru": (13.3379, 77.1173),
    "Mysuru": (12.2958, 76.6394), "Mangaluru": (12.9141, 74.8560),
    "Chennai": (13.0827, 80.2707), "Hyderabad": (17.3850, 78.4867),
}

# name, group, age, kg, type, organs, hla, city, days since last blood donation (None = never)
DONORS = [
    ("Asha Rao", "O+", 29, 62, "both", ["kidney", "liver"], "A2,A24,B7,B8,DR3,DR4", "Bengaluru", 200),
    ("Imran Pasha", "A+", 34, 78, "blood", [], "", "Whitefield", 120),
    ("Divya Nair", "O-", 26, 55, "blood", [], "", "Jayanagar", None),
    ("Karthik S", "B+", 41, 82, "both", ["kidney"], "A1,A3,B7,B35,DR1,DR4", "Yelahanka", 95),
    ("Meera Iyer", "A-", 31, 58, "blood", [], "", "Bengaluru", 300),
    ("Rohan Gowda", "AB+", 38, 74, "organ", ["kidney", "liver", "heart"], "A2,A11,B7,B44,DR3,DR7", "Tumakuru", None),
    ("Sana Khan", "O+", 24, 60, "both", ["kidney", "lung"], "A2,A24,B7,B35,DR4,DR11", "Hosur", 40),
    ("Vikram Shetty", "A+", 45, 85, "both", ["liver", "heart"], "A2,A3,B7,B8,DR3,DR15", "Mysuru", 150),
    ("Latha M", "B-", 36, 59, "blood", [], "", "Mysuru", None),
    ("Arjun Reddy", "O+", 30, 76, "both", ["kidney", "heart", "liver"], "A2,A24,B7,B8,DR3,DR4", "Hyderabad", 400),
    ("Fatima Z", "A+", 28, 54, "blood", [], "", "Chennai", 110),
    ("Naveen K", "O-", 33, 80, "both", ["kidney", "liver"], "A1,A2,B8,B44,DR3,DR4", "Mangaluru", None),
    ("Pooja Hegde", "AB-", 27, 57, "blood", [], "", "Bengaluru", 250),
    ("Suresh P", "B+", 52, 79, "both", ["kidney"], "A24,A30,B7,B13,DR7,DR11", "Chennai", 180),
    ("Ananya D", "A+", 22, 52, "both", ["kidney", "liver", "lung"], "A2,A24,B7,B35,DR1,DR4", "Jayanagar", None),
    ("Mohan Raj", "O+", 47, 90, "blood", [], "", "Whitefield", 60),
]


def seed(app):
    with app.app_context():
        db = get_db()
        if repo.user_by_email(db, "admin@lifelink.test"):
            return False
        repo.create_user(db, "LifeLink Admin", "admin@lifelink.test", generate_password_hash("Admin@1234"), "admin")
        hospital_id = repo.create_user(db, "Victoria Hospital", "hospital@lifelink.test",
                                       generate_password_hash("Hospital@123"), "hospital")
        for i, (name, group, age, kg, kind, organs, hla, city, ago) in enumerate(DONORS):
            email = "donor@lifelink.test" if i == 0 else f"donor{i}@lifelink.test"
            uid = repo.create_user(db, name, email, generate_password_hash("Donor@1234"), "donor")
            lat, lng = CITIES[city]
            last = (date.today() - timedelta(days=ago)).isoformat() if ago is not None else None
            repo.save_donor(db, uid, dict(
                blood_group=group, age=age, weight_kg=kg, donor_type=kind, organs_pledged=organs,
                hla=hla, city=city, lat=lat, lng=lng, last_donation_date=last, available=True))
        demo_requests = [
            dict(patient_ref="PT-10231", kind="blood", organ=None, blood_group="A+", urgency=5,
                 units_needed=2, patient_age=None, hla="", city="Bengaluru", lat=12.9716, lng=77.5946),
            dict(patient_ref="PT-10244", kind="organ", organ="kidney", blood_group="O+", urgency=4,
                 units_needed=1, patient_age=32, hla="A2,A24,B7,B8,DR3,DR4", city="Bengaluru",
                 lat=12.9716, lng=77.5946),
            dict(patient_ref="PT-10250", kind="organ", organ="heart", blood_group="A+", urgency=5,
                 units_needed=1, patient_age=44, hla="A2,A3,B7,B8,DR3,DR15", city="Bengaluru",
                 lat=12.9716, lng=77.5946),
        ]
        for data in demo_requests:
            repo.create_request(db, hospital_id, data)
        audit.append(db, "system", "seed.loaded", {"donors": len(DONORS), "requests": len(demo_requests)})
        db.commit()
        return True


if __name__ == "__main__":
    created = seed(create_app())
    print("Demo data loaded." if created else "Demo data already present.")
