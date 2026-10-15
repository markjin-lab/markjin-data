# verify (round 2, 2026-10-16)

Spot-check: 3 random filtered leads via `x.get_posts_by_ids` (post.fields=entities,created_at,note_tweet).
Spill: `eebfced4-5b84-4b09-b557-2edc82faf4c7.txt`.

- id=2110844231585870138: found=True created_at_match=True text_prefix_ok=True
  lead_created_at=2026-10-15T21:24:17.000Z spot_created_at=2026-10-15T21:24:17.000Z
- id=2110841738361286751: found=True created_at_match=True text_prefix_ok=True
  lead_created_at=2026-10-15T21:14:22.000Z spot_created_at=2026-10-15T21:14:22.000Z
- id=2110841080065261906: found=True created_at_match=True text_prefix_ok=True
  lead_created_at=2026-10-15T21:11:45.000Z spot_created_at=2026-10-15T21:11:45.000Z

Result: 3/3 found with matching created_at.
