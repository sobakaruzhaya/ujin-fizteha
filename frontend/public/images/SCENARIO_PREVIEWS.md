# Scenario preview generation

Asset: `scenario-overload.png`
Scenario: `overload_protection` (Защита от перегрузки).
Generated with the built-in image_gen tool, then copied into this project.

Final prompt:

Use case: product-mockup. Generate a photorealistic wide landscape photo preview for a smart home automation card named overload protection. A white European smart plug connected to a black electric kettle on a dark modern kitchen counter, subtle amber status LED, clean practical contemporary apartment kitchen softly blurred in background. Calm safe everyday home atmosphere, warm neutral lighting, charcoal and warm beige palette matching a dark smart home dashboard. Premium editorial photography, realistic material texture, landscape composition with subject centered, suitable for cropping into a 460x160 card banner. No text, no typography, no logos, no watermark.

## Template scenario photos — 2026-10-31

Eight additional photos were generated individually with the built-in `image_gen`
tool for the template gallery. Full final prompts and original generation paths:
[`scenario-templates/GENERATION.json`](scenario-templates/GENERATION.json).

Final project assets are in `frontend/public/images/scenario-templates/`:

| Key / filename stem | Photo subject |
| --- | --- |
| `overload` | Smart plug and kettle on a dark kitchen counter |
| `leak` | Leak sensor and water on a bathroom floor |
| `fire` | Smoke detector above kitchen appliances |
| `fresh-air` | Ventilation unit and curtains in a fresh breeze |
| `warm-room` | Thermostat and a warm, cozy living room |
| `cool-room` | Thermostat and a cool living room |
| `cinema` | Television and dimmed evening lighting |
| `doorbell` | Video intercom beside an apartment entrance |

Each stem has a WebP version for the web gallery and a JPEG version for Telegram
photo uploads. Both are approximately 1280 × 720. No remote image hosting is
needed. The gallery uses full-width photos with a category badge; selecting a
Telegram template sends its photo before opening the editable draft. A failed
photo upload does not prevent scenario creation.

The existing saved-scenario stack keeps its original preview behavior.
