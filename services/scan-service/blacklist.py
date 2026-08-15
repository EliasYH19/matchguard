"""
Signature data used by the scan-service.

This is intentionally simple - we are a course project, not a real
kernel-level anti-cheat vendor. The "product" here is a verification layer:
tournament organizers ask players to export a process/log snapshot from
their PC (a .txt/.json file) before a match, upload it through MatchGuard,
and we flag anything that matches a list of known cheat tool names or
known-bad file hashes. Silver/Gold packages unlock the keyword scan on top
of the basic hash check that Bronze gets.

Author: Elias
"""

# Known cheat-tool process / file name fragments (case-insensitive).
# A real product would pull this from a threat-intel feed and update it
# constantly - here it's a static list which is good enough to demo the
# feature end to end.
KEYWORD_SIGNATURES = [
    "cheatengine",
    "cheat engine",
    "aimbot",
    "wallhack",
    "wall hack",
    "esp overlay",
    "injector.dll",
    "artmoney",
    "speedhack",
    "unknowncheats",
    "trigger bot",
    "triggerbot",
    "no recoil",
    "norecoil",
    "aimjunkies",
]

# Toy list of known-bad SHA256 file hashes. In the demo data (tests /
# seed data) one of the sample uploads deliberately matches this so the
# "flagged" path is exercised without needing a real cheat binary.
KNOWN_BAD_HASHES = {
    "6b1e7a2f0e6a2ac2b3e2e8f5f8b0f4b2a1c9d7e6f5a4b3c2d1e0f9a8b7c6d5e4": "Known 'InjectorX' loader hash",
}


def scan_text_for_keywords(text):
    """Returns a list of matched signature strings found in the given text."""
    lowered = text.lower()
    return [sig for sig in KEYWORD_SIGNATURES if sig in lowered]


def check_hash(sha256_hex):
    return KNOWN_BAD_HASHES.get(sha256_hex)
