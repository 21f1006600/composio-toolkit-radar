import re
from pathlib import Path

FILES = [
    Path("data/research_results.json"),
    Path("data/analytics.json"),
    Path("docs/index.html"),
]

PATTERNS = {
    "Discord Bot Token": (
        r"[A-Za-z0-9_-]{20,30}\."
        r"[A-Za-z0-9_-]{6,8}\."
        r"[A-Za-z0-9_-]{25,110}"
    ),
    "Discord MFA Token": r"mfa\.[A-Za-z0-9_-]{50,120}",
    "Google API Key": r"AIza[0-9A-Za-z_-]{35}",
    "Tavily API Key": r"tvly-[A-Za-z0-9_-]{15,}",
    "Secret API Key": r"sk_[A-Za-z0-9_-]{20,}",
}

for path in FILES:
    if not path.exists():
        continue

    content = path.read_text(encoding="utf-8")
    total = 0

    for name, pattern in PATTERNS.items():
        content, count = re.subn(
            pattern,
            "[REDACTED_CREDENTIAL]",
            content,
        )

        if count:
            print(f"{path}: {name}: {count} redacted")

        total += count

    if total:
        path.write_text(content, encoding="utf-8")

    print(f"{path}: {total} total redactions")

print("Sanitization complete.")