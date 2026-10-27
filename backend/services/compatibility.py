"""Medical compatibility rules for blood and organ matching.

These are simplified rules for an academic prototype. They are not a
substitute for clinical cross-matching.
"""

BLOOD_GROUPS = ("O-", "O+", "A-", "A+", "B-", "B+", "AB-", "AB+")

# For every recipient group, the donor groups whose red cells are safe to give.
_RBC_DONORS = {
    "O-": {"O-"},
    "O+": {"O-", "O+"},
    "A-": {"O-", "A-"},
    "A+": {"O-", "O+", "A-", "A+"},
    "B-": {"O-", "B-"},
    "B+": {"O-", "O+", "B-", "B+"},
    "AB-": {"O-", "A-", "B-", "AB-"},
    "AB+": set(BLOOD_GROUPS),
}

# Organs only need ABO compatibility (Rh is ignored).
_ABO_DONORS = {
    "O": {"O"},
    "A": {"O", "A"},
    "B": {"O", "B"},
    "AB": {"O", "A", "B", "AB"},
}

# Approximate cold ischemia windows in hours: how long an organ stays usable.
ORGAN_WINDOWS_H = {"heart": 4, "lung": 6, "liver": 12, "pancreas": 12, "kidney": 36}


def check_group(group):
    """Return the group if valid, otherwise raise ValueError."""
    if group not in BLOOD_GROUPS:
        raise ValueError(f"Unknown blood group: {group!r}")
    return group


def abo_of(group):
    return check_group(group)[:-1]


def can_donate_blood(donor_group, recipient_group):
    check_group(donor_group)
    return donor_group in _RBC_DONORS[check_group(recipient_group)]


def can_donate_organ(donor_group, recipient_group):
    return abo_of(donor_group) in _ABO_DONORS[abo_of(recipient_group)]
