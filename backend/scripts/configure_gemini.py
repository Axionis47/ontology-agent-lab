"""Add local Gemini settings without replacing existing configuration."""

import argparse
import json
from decimal import Decimal
from pathlib import Path

from dotenv import dotenv_values


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project")
    parser.add_argument("--check-budget", type=Decimal, default=Decimal("0"))
    args = parser.parse_args()
    if not args.check_budget.is_finite() or not 0 <= args.check_budget <= Decimal("0.10"):
        parser.error("Use a check budget from 0 through 0.10 USD.")
    backend = Path(__file__).resolve().parents[1]
    target = backend / ".env"
    current = dotenv_values(target)
    if current.get("OAK_ENVIRONMENT") != "local":
        raise SystemExit("Configure the local backend before adding Gemini settings.")
    project = args.project or current.get("OAK_GEMINI_PROJECT")
    profile = backend / ".local/gemini-auth.json"
    if not project and profile.exists():
        project = json.loads(profile.read_text()).get("project")
    if not project or any(
        char not in "abcdefghijklmnopqrstuvwxyz0123456789-:." for char in project
    ):
        raise SystemExit("Supply a valid Google Cloud project with --project.")
    settings = {
        "OAK_GEMINI_PROJECT": project,
        "OAK_GEMINI_LOCATION": "global",
        "OAK_GEMINI_MODEL": "gemini-3.8-flash",
        "OAK_GEMINI_TIMEOUT": "25",
        "OAK_GEMINI_MAX_OUTPUT_TOKENS": "4096",
        "OAK_GEMINI_CHECK_BUDGET_USD": str(args.check_budget),
    }
    additions = {key: value for key, value in settings.items() if key not in current}
    if additions:
        with target.open("a") as stream:
            stream.write("\n" + "".join(f"{key}={value}\n" for key, value in additions.items()))
        target.chmod(0o600)
    print("Local Gemini settings are configured. Existing values were preserved.")
    print("Restart the backend. Open an agent and select Check connection.")


if __name__ == "__main__":
    main()
