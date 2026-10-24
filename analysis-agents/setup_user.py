"""Provision the single owner without sending an email or exposing a password."""

import argparse
from pathlib import Path
import secrets
from dotenv import set_key
from shared.db import get_client


def provision(email):
    path = Path(__file__).resolve().parents[1] / ".env"
    client = get_client()
    users = client.auth.admin.list_users()
    user = next((u for u in users if u.email == email), None)
    if user is None:
        password = secrets.token_urlsafe(24)
        # Save first so an interrupted request never loses the generated password.
        set_key(str(path), "DASHBOARD_EMAIL", email)
        set_key(str(path), "DASHBOARD_PASSWORD", password)
        user = client.auth.admin.create_user(
            {"email": email, "password": password, "email_confirm": True}
        ).user
    client.rpc("set_research_owner", {"p_user": str(user.id)}).execute()
    print("Owner configured. Login credentials are in the ignored root .env; no email sent.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--email", required=True)
    provision(parser.parse_args().email)
