"""Create local configuration without printing credentials or replacing existing files."""

import argparse
import secrets
from pathlib import Path

from cryptography.fernet import Fernet

parser = argparse.ArgumentParser()
parser.add_argument("--database-url", default="postgresql://oak:oak-local-only@127.0.0.1:55432/oak")
args = parser.parse_args()
root = Path(__file__).resolve().parents[2]
backend, frontend = root / "backend/.env", root / "frontend/.env.local"
if backend.exists() or frontend.exists():
    raise SystemExit("Configuration already exists. Edit the existing files.")
key = secrets.token_urlsafe(32)
backend.write_text(
    f"OAK_ENVIRONMENT=local\nOAK_DATABASE_URL={args.database_url}\nOAK_API_KEY={key}\n"
    "OAK_PUBLIC_API_URL=http://localhost:8047\nOAK_FRONTEND_URL=http://localhost:3047\n"
    "OAK_SECRET_BACKEND=local\nOAK_ALLOW_LOCAL_MCP=true\n"
    f"OAK_LOCAL_SECRET_KEY={Fernet.generate_key().decode()}\n"
)
frontend.write_text(
    f"OAK_API_URL=http://127.0.0.1:8047\nOAK_API_KEY={key}\n"
    "OAK_LOCAL_PREVIEW=true\nOAK_PREVIEW_USER=oak\n"
    f"OAK_PREVIEW_PASSWORD={secrets.token_urlsafe(24)}\n"
)
for path in [backend, frontend]:
    path.chmod(0o600)
print("Created backend/.env and frontend/.env.local. Keep these files private.")
