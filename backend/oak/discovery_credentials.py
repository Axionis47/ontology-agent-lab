"""Keep tool credentials on the server and expose only scoped references."""

from uuid import UUID, uuid4

from cryptography.fernet import Fernet

from oak.discovery_validation import SECRET_KEYS

PREFIX = "oak-secret:"


class Credentials:
    def __init__(self, settings, table="discovery_credentials"):
        self.settings = settings
        if table not in {"discovery_credentials", "training_credentials"}:
            raise ValueError("Unknown credential store.")
        self.table = table

    async def capture(self, db, run_id, connection_id, value, sensitive=False):
        if isinstance(value, dict):
            return {
                key: await self.capture(
                    db, run_id, connection_id, item, sensitive or bool(SECRET_KEYS.search(key))
                )
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [
                await self.capture(db, run_id, connection_id, item, sensitive) for item in value
            ]
        if not sensitive or not isinstance(value, str) or not value:
            return value
        reference, encrypted, vault_id = uuid4(), None, None
        if self.settings.secret_backend == "vault":
            result = await (
                await db.execute("SELECT vault.create_secret(%s) AS id", (value,))
            ).fetchone()
            vault_id = result["id"]
        else:
            encrypted = (
                Fernet(self.settings.local_secret_key.encode()).encrypt(value.encode()).decode()
            )
        await db.execute(
            f"INSERT INTO {self.table}(id,run_id,connection_id,encrypted_value,vault_id) "
            "VALUES (%s,%s,%s,%s,%s)",
            (reference, run_id, connection_id, encrypted, vault_id),
        )
        return PREFIX + str(reference)

    async def resolve(self, db, run_id, connection_id, value):
        if isinstance(value, dict):
            return {
                key: await self.resolve(db, run_id, connection_id, item)
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [await self.resolve(db, run_id, connection_id, item) for item in value]
        if not isinstance(value, str) or not value.startswith(PREFIX):
            return value
        try:
            reference = UUID(value[len(PREFIX) :])
        except ValueError:
            raise ValueError("The credential reference is invalid.") from None
        row = await (
            await db.execute(
                f"SELECT encrypted_value,vault_id FROM {self.table} "
                "WHERE id=%s AND run_id=%s AND connection_id=%s",
                (reference, run_id, connection_id),
            )
        ).fetchone()
        if not row:
            raise ValueError("The credential reference does not belong to this run and connection.")
        if row["vault_id"]:
            result = await (
                await db.execute(
                    "SELECT decrypted_secret AS value FROM vault.decrypted_secrets WHERE id=%s",
                    (row["vault_id"],),
                )
            ).fetchone()
            if not result:
                raise ValueError("The credential reference has expired.")
            return result["value"]
        return (
            Fernet(self.settings.local_secret_key.encode())
            .decrypt(row["encrypted_value"].encode())
            .decode()
        )

    async def clear(self, db, run_id):
        rows = await (
            await db.execute(
                f"DELETE FROM {self.table} WHERE run_id=%s RETURNING vault_id", (run_id,)
            )
        ).fetchall()
        for row in rows:
            if row["vault_id"]:
                await db.execute("DELETE FROM vault.secrets WHERE id=%s", (row["vault_id"],))

    async def scrub(self, db, run_id, value):
        rows = await (
            await db.execute(
                f"SELECT id,connection_id FROM {self.table} WHERE run_id=%s", (run_id,)
            )
        ).fetchall()
        secrets = [
            await self.resolve(db, run_id, row["connection_id"], PREFIX + str(row["id"]))
            for row in rows
        ]

        def clean(item):
            if isinstance(item, dict):
                return {key: clean(child) for key, child in item.items()}
            if isinstance(item, list):
                return [clean(child) for child in item]
            if isinstance(item, str) and not item.startswith(PREFIX):
                for secret in sorted(secrets, key=len, reverse=True):
                    item = item.replace(secret, "[redacted]")
            return item

        return clean(value)
