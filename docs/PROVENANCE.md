# Code provenance

User permission: on 2026-10-25, the owner explicitly confirmed commercial reuse authorization for all project code. This record documents that statement; it is not an independent legal ownership opinion.

No third-party license rights are expanded by that confirmation. The original main bot carries a Daily BSD-2-Clause header; it was inspected but not copied into this product. Any later extraction must retain applicable notices.

| Original path | Product path | SHA-256 (both files) | Use |
|---|---|---|---|
| `redaction.py` | `app/reused/redaction.py` | `e895f0b40263735f1f457e4b51b1ef8a1691a1394696be0e387dae704cb6498f` | Active transcript privacy filter |
| `voicebot/server/voice_gate.py` | `optional/voice/voice_gate.py` | `eaf331d4207e8842ccb58ec8f00cdb28944d7dc49f5e070cfb089f11d0a3cd96` | Preserved optional component, not imported by demo |

These two files are exact, unmodified copies. No secrets or external service calls were found in them. The remainder of this product is newly authored code and synthetic demo content.

Dependencies are pinned in requirements.lock. Review and preserve each dependency’s distribution license before commercial redistribution. No blanket open-source license is assigned to owner code by this delivery.

## Adapted reuse: voicemail detection

`app/reused/voicemail.py` extracts `_VOICEMAIL_RE` and `is_voicemail_announcement` from original `guard_core.py`. AST-based extraction preserves executable behavior while dropping company incident comments/docstrings. No company endpoint or data dependency remains. This detector actively prevents a simulated recorded greeting from becoming a qualified/handoff outcome.

Original module SHA-256: `f8d02352d0af62229461654ef55b123a7b096e41021fa5944674901e25a72821`.
