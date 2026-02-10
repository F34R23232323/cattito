import os

# ------------------------------
# REQUIRED
# ------------------------------

# Discord bot token
TOKEN = os.environ.get("TOKEN", "(YOUR TOKEN HERE)")
# DB password for postgres
DB_PASS = os.environ.get("psql_password", "(YOUR PSQL PASSWORD HERE)")
BACKUP_ID = os.environ.get("BACKUP_ID", "(YOUR BACKUP CHANNEL ID (DISCORD) ID)")

# Push these into os.environ so anything else reading env vars works
os.environ.setdefault("TOKEN", TOKEN)
os.environ.setdefault("psql_password", DB_PASS)
os.environ.setdefault("BACKUP_ID", BACKUP_ID)

# ------------------------------
# OPTIONAL
# ------------------------------

SENTRY_DSN = os.environ.get("sentry_dsn", "(YOUR SENTRY DSN LINK)")
WEBHOOK_VERIFY = os.environ.get("webhook_verify", "(YOUR TOP.GG WEBHOOK VERIFY TOKEN)")
TOP_GG_TOKEN = os.environ.get("top_gg_token", "(YOUR TOP.GG TOKEN)")
WORDNIK_API_KEY = os.environ.get("wordnik_api_key", "(YOUR WORDNIK API KEY)")

os.environ.setdefault("sentry_dsn", SENTRY_DSN)
os.environ.setdefault("webhook_verify", WEBHOOK_VERIFY)
os.environ.setdefault("top_gg_token", TOP_GG_TOKEN)
os.environ.setdefault("wordnik_api_key", WORDNIK_API_KEY)

# ------------------------------
# CONSTANTS (unchanged)
# ------------------------------

MIN_SERVER_SEND = 1
BACKUP_ID = 1
DONOR_CHANNEL_ID = 1
RAIN_CHANNEL_ID = 1
