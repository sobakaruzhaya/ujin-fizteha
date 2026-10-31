# Telegram photos

JPEG versions of the existing project photographs, prepared for Bot API uploads.
All 15 device images are derived from `frontend/public/images/*.webp` without
changing their contents. `home.jpg` is derived from the generated
`frontend/public/images/home-hero-living.webp`.

Original image provenance and prompts:
`frontend/public/images/PHOTO_PROMPTS.md`, `SCENARIO_PREVIEWS.md`,
`HOME_HERO_PROMPT.md`. Template cards reuse the eight existing JPEG previews in
`frontend/public/images/scenario-templates/`.

These files are included in the repository; the bot needs no image conversion
library at runtime. JPEG output: quality 88, maximum 1200 × 1200, progressive.
Telegram file IDs are cached by content hash in the ignored bot state file.
