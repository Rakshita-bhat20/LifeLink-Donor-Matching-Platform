"""Application configuration, read from environment variables with safe dev defaults."""
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


class Config:
    SECRET_KEY = os.environ.get("LIFELINK_SECRET", "dev-only-change-me")
    DATABASE = os.environ.get("LIFELINK_DB", os.path.join(BASE_DIR, "lifelink.db"))
    TOKEN_TTL_SECONDS = int(os.environ.get("LIFELINK_TOKEN_TTL", "28800"))
    MAX_MATCH_RESULTS = 10
