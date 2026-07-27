"""Sync GEMINI_* from workspace .env into apps/backend/.env."""

from __future__ import annotations

from pathlib import Path

# scripts/ -> backend/ -> apps/ -> repo root
ROOT = Path(__file__).resolve().parents[3]
ROOT_ENV = ROOT / ".env"
BACKEND_ENV = ROOT / "apps" / "backend" / ".env"


def main() -> None:
    values = {
        "GEMINI_ENABLED": "true",
        "GEMINI_API_KEY": "",
        "GEMINI_MODEL_ID": "gemini-3.5-flash",
        "GEMINI_MAX_TOKENS": "1536",
    }
    if ROOT_ENV.exists():
        for line in ROOT_ENV.read_text(encoding="utf-8-sig").splitlines():
            if not line or line.strip().startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            key = key.strip()
            if key in values:
                values[key] = val.strip()

    lines: list[str] = []
    if BACKEND_ENV.exists():
        for line in BACKEND_ENV.read_text(encoding="utf-8-sig").splitlines():
            if line.startswith("GEMINI_"):
                continue
            lines.append(line)
    while lines and not lines[-1].strip():
        lines.pop()

    lines.extend(
        [
            "",
            "# Google Gemini (synced from workspace .env)",
            f"GEMINI_ENABLED={values['GEMINI_ENABLED']}",
            f"GEMINI_API_KEY={values['GEMINI_API_KEY']}",
            f"GEMINI_MODEL_ID={values['GEMINI_MODEL_ID']}",
            f"GEMINI_MAX_TOKENS={values['GEMINI_MAX_TOKENS']}",
        ]
    )
    BACKEND_ENV.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(
        "synced",
        BACKEND_ENV,
        "enabled=",
        values["GEMINI_ENABLED"],
        "key_set=",
        bool(values["GEMINI_API_KEY"]),
        "model=",
        values["GEMINI_MODEL_ID"],
    )


if __name__ == "__main__":
    main()
