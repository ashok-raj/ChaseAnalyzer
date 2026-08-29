"""
Shared credential helper for statement downloaders.

Lookup order for a given bank key (e.g. "chase_business"):
  1. OS keyring (macOS Keychain via the `keyring` package) - service name
     "chaseanalyzer-statements", username "<bank_key>_username" / "<bank_key>_password"
  2. `.env` file at downloaders/<bank_key>.env (gitignored) with
     <BANK_KEY>_USERNAME= / <BANK_KEY>_PASSWORD=
  3. Interactive prompt (and offer to save into keyring for next time)

Run this file directly to store/update credentials for a bank:
    python3 bank_credentials.py chase_business
    python3 bank_credentials.py chase_personal
    python3 bank_credentials.py bofa
"""

import getpass
import sys
from pathlib import Path

try:
    import keyring
    KEYRING_AVAILABLE = True
except ImportError:
    KEYRING_AVAILABLE = False

SERVICE_NAME = "chaseanalyzer-statements"
ENV_DIR = Path(__file__).resolve().parent

BANKS = {
    "chase_business": "Chase Business (card ending 0801)",
    "chase_personal": "Chase Personal (card ending 5136)",
    "bofa": "Bank of America (account ending 1250)",
}


def _env_path(bank_key: str) -> Path:
    return ENV_DIR / f"{bank_key}.env"


def _read_env_file(bank_key: str):
    path = _env_path(bank_key)
    if not path.exists():
        return None, None
    values = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        values[key.strip()] = val.strip().strip('"').strip("'")
    prefix = bank_key.upper()
    return values.get(f"{prefix}_USERNAME") or None, values.get(f"{prefix}_PASSWORD") or None


def _write_env_file(bank_key: str, username: str, password: str):
    path = _env_path(bank_key)
    prefix = bank_key.upper()
    path.write_text(
        f"# {BANKS.get(bank_key, bank_key)} login credentials\n"
        f"# LOCAL ONLY - gitignored, never commit\n"
        f"{prefix}_USERNAME={username}\n"
        f"{prefix}_PASSWORD={password}\n"
    )
    path.chmod(0o600)


def get_credentials(bank_key: str):
    """Return (username, password) for bank_key, or (None, None) if not found anywhere."""
    if bank_key not in BANKS:
        raise ValueError(f"Unknown bank_key '{bank_key}'. Choices: {list(BANKS)}")

    if KEYRING_AVAILABLE:
        username = keyring.get_password(SERVICE_NAME, f"{bank_key}_username")
        password = keyring.get_password(SERVICE_NAME, f"{bank_key}_password")
        if username and password:
            return username, password

    username, password = _read_env_file(bank_key)
    if username and password:
        return username, password

    return None, None


def save_credentials(bank_key: str, username: str, password: str):
    """Save credentials to keyring if available, else to the .env fallback file."""
    if KEYRING_AVAILABLE:
        try:
            keyring.set_password(SERVICE_NAME, f"{bank_key}_username", username)
            keyring.set_password(SERVICE_NAME, f"{bank_key}_password", password)
            return "keyring"
        except Exception as e:
            print(f"Warning: keyring save failed ({e}), falling back to .env file")

    _write_env_file(bank_key, username, password)
    return "env"


def prompt_and_save(bank_key: str):
    label = BANKS.get(bank_key, bank_key)
    print(f"\nSetting up credentials for: {label}")
    username = input("  Username: ").strip()
    password = getpass.getpass("  Password: ")
    backend = save_credentials(bank_key, username, password)
    where = "macOS Keychain" if backend == "keyring" else f".env file ({_env_path(bank_key)})"
    print(f"  Saved to {where}.")
    return username, password


def get_mfa_phone_last4(bank_key: str):
    """Return the last-4 digits of the phone number to use for SMS MFA, if saved."""
    if KEYRING_AVAILABLE:
        val = keyring.get_password(SERVICE_NAME, f"{bank_key}_mfa_phone_last4")
        if val:
            return val
    _, _ = get_credentials(bank_key)  # no-op, keeps parity with env fallback pattern
    path = _env_path(bank_key)
    if path.exists():
        for line in path.read_text().splitlines():
            if line.strip().startswith(f"{bank_key.upper()}_MFA_PHONE_LAST4="):
                return line.split("=", 1)[1].strip().strip('"').strip("'") or None
    return None


def save_mfa_phone_last4(bank_key: str, last4: str):
    if KEYRING_AVAILABLE:
        try:
            keyring.set_password(SERVICE_NAME, f"{bank_key}_mfa_phone_last4", last4)
            return "keyring"
        except Exception as e:
            print(f"Warning: keyring save failed ({e}), falling back to .env file")
    path = _env_path(bank_key)
    prefix = bank_key.upper()
    existing = path.read_text() if path.exists() else ""
    existing = "\n".join(l for l in existing.splitlines() if not l.startswith(f"{prefix}_MFA_PHONE_LAST4="))
    path.write_text(existing.rstrip("\n") + f"\n{prefix}_MFA_PHONE_LAST4={last4}\n")
    path.chmod(0o600)
    return "env"


def get_or_prompt_mfa_phone_last4(bank_key: str):
    last4 = get_mfa_phone_last4(bank_key)
    if last4:
        return last4
    last4 = input(f"Last 4 digits of the phone number to use for {BANKS.get(bank_key, bank_key)} SMS MFA: ").strip()
    save_mfa_phone_last4(bank_key, last4)
    return last4


def get_or_prompt_credentials(bank_key: str):
    """Used by the downloader scripts at runtime."""
    username, password = get_credentials(bank_key)
    if username and password:
        return username, password
    print(f"No stored credentials found for {BANKS.get(bank_key, bank_key)}.")
    return prompt_and_save(bank_key)


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in BANKS:
        print("Usage: python3 bank_credentials.py <bank_key>")
        print(f"  bank_key one of: {list(BANKS)}")
        sys.exit(1)

    bank_key = sys.argv[1]
    existing_user, existing_pass = get_credentials(bank_key)
    if existing_user:
        print(f"Existing credentials found for {BANKS[bank_key]} (username: {existing_user}).")
        resp = input("Overwrite? (y/n, default: n): ").strip().lower()
        if resp != "y":
            print("Left unchanged.")
            sys.exit(0)

    prompt_and_save(bank_key)
