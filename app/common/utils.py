import re


def slugify(value: str) -> str:
    """Convert arbitrary text into a lowercase URL-safe ASCII slug."""
    normalized = value.strip().lower()
    normalized = re.sub(r"[^a-z0-9\s_-]", "", normalized)
    normalized = re.sub(r"[\s_-]+", "-", normalized)
    return normalized.strip("-") or "course"


def calculate_completion_percentage(completed_lessons: int, total_lessons: int) -> float:
    """Compute course completion percentage rounded to two decimal places."""
    if total_lessons <= 0:
        return 0.0
    bounded_completed = max(0, min(completed_lessons, total_lessons))
    return round((bounded_completed / total_lessons) * 100.0, 2)


def validate_password_strength(password: str) -> str:
    """Validate password complexity: 8-128 chars, upper, lower, and digit."""
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters long")
    if len(password) > 128:
        raise ValueError("Password must be at most 128 characters long")
    if not any(ch.isupper() for ch in password):
        raise ValueError("Password must include at least one uppercase letter")
    if not any(ch.islower() for ch in password):
        raise ValueError("Password must include at least one lowercase letter")
    if not any(ch.isdigit() for ch in password):
        raise ValueError("Password must include at least one digit")
    return password
