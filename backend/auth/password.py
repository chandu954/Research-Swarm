"""Password hashing and verification using bcrypt."""
from __future__ import annotations

import bcrypt


def hash_password(password: str) -> str:
    """Hash a plaintext password with a salt."""
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plaintext: str, hashed: str) -> bool:
    """Verify a plaintext password against a bcrypt hash."""
    return bcrypt.checkpw(plaintext.encode("utf-8"), hashed.encode("utf-8"))
