# verify (round 2, 2026-10-17)

Spot-check: 3 filtered leads via `x.get_posts_by_ids` (post.fields=entities,created_at,note_tweet).
Spill: `581ee5c2-7ce3-419c-9d6c-bc74348da26f.txt`.

- id=2111212840807751758: found=True created_at_match=True text_prefix_ok=True
  lead_created_at=2026-10-16T21:49:00.000Z spot_created_at=2026-10-16T21:49:00.000Z
- id=2111212090014740840: found=True created_at_match=True text_prefix_ok=True
  lead_created_at=2026-10-16T21:46:01.000Z spot_created_at=2026-10-16T21:46:01.000Z
- id=2111208065559069107: found=True created_at_match=True text_prefix_ok=True
  lead_created_at=2026-10-16T21:30:01.000Z spot_created_at=2026-10-16T21:30:01.000Z

Result: 3/3 found with matching created_at.
