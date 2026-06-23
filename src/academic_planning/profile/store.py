"""Persistence helpers for student profile."""

from __future__ import annotations

from copy import deepcopy


def default_profile():
    return {
        "name": "",
        "email": "",
        "academic_level": "",
        "timezone": "America/Guatemala",
        "study_preferences": "",
    }

def load_profile(store):
    profile = deepcopy(default_profile())
    raw_profile = store.get("profile", {})
    if isinstance(raw_profile, dict):
        profile.update({k: raw_profile.get(k, v) for k, v in profile.items()})

    # Legacy compatibility with old "student" structure.
    legacy = store.get("student", {})
    if isinstance(legacy, dict):
        if not profile["name"]:
            profile["name"] = str(legacy.get("name", "") or "").strip()
        if not profile["academic_level"]:
            career = str(legacy.get("career", "") or "").strip()
            semester = str(legacy.get("semester", "") or "").strip()
            if career and semester:
                profile["academic_level"] = f"{career} - {semester}"
            else:
                profile["academic_level"] = career or semester
        if not profile["timezone"]:
            profile["timezone"] = str(legacy.get("timezone", "") or "").strip() or "America/Guatemala"

    store["profile"] = profile
    sync_legacy_student_profile(store)
    return profile


def save_profile(store, profile):
    safe = deepcopy(default_profile())
    if isinstance(profile, dict):
        for key in safe:
            if key in profile:
                safe[key] = profile.get(key, safe[key])
    safe["name"] = str(safe["name"] or "").strip()
    safe["email"] = str(safe["email"] or "").strip()
    safe["academic_level"] = str(safe["academic_level"] or "").strip()
    safe["timezone"] = str(safe["timezone"] or "").strip() or "America/Guatemala"
    safe["study_preferences"] = str(safe["study_preferences"] or "").strip()
    store["profile"] = safe
    sync_legacy_student_profile(store)
    return safe


def sync_legacy_student_profile(store):
    profile = store.get("profile", {})
    legacy = store.get("student", {})
    if not isinstance(legacy, dict):
        legacy = {}
    legacy.setdefault("name", "")
    legacy.setdefault("career", "")
    legacy.setdefault("semester", "")
    legacy.setdefault("timezone", "America/Guatemala")
    if isinstance(profile, dict):
        legacy["name"] = str(profile.get("name", "") or "").strip()
        legacy["timezone"] = str(profile.get("timezone", "") or "").strip() or "America/Guatemala"
        level = str(profile.get("academic_level", "") or "").strip()
        if " - " in level:
            career, semester = level.split(" - ", 1)
            legacy["career"] = career.strip()
            legacy["semester"] = semester.strip()
        else:
            legacy["career"] = level
            legacy["semester"] = legacy.get("semester", "")
    store["student"] = legacy
    return legacy
