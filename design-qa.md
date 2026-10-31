# Home hero design QA

Source visual: `C:/Users/igd12/AppData/Local/Temp/codex-clipboard-58ef1ea5-7f6d-43ef-bcb6-305466046cab.png`.

Scope: adapt the user's split photo/text reference to the existing UjinFizteha
dashboard and add genuine React Bits DitherVeil and BlurText. The user asked for
inspiration, not a Yandex clone. Existing Play typography, warm dark palette,
header, dashboard controls and data are intentional product constraints.

Browser: Codex in-app browser, separate isolated UI runtime at port 8898;
production home remains at port 8787. Generated photo:
`frontend/public/images/home-hero-living.webp` (1600 × 1402 WebP, 224 KB).
Prompts and tool provenance: `frontend/public/images/HOME_HERO_PROMPT.md`.

## Iteration 1

Evidence:

- `app/data/home-hero-wide-v1.jpg`: desktop CSS viewport 1898 × 785.
- `app/data/home-hero-desktop-v1.jpg`: normal in-app CSS viewport 1101 × 884.
- `app/data/home-hero-reveal-v1.jpg`: actual pointer/click reveal in DitherVeil.
- `app/data/home-hero-comparison-v1.jpg`: reference and rendered desktop captured
  together on one comparison board, normalized to the same 1100px display width.
- `app/data/home-hero-mobile-full-v1.jpg` and `home-hero-mobile-crop-v1.jpg`:
  actual mobile rendering at 390 × 844, full-page capture cropped to the first
  1100px for review. Viewport-only capture after override was incorrectly scaled
  by the browser backend; it was discarded as mobile comparison evidence.

Fonts/typography: readable Play, one semantic H1, large two-line title.
Spacing/layout: balanced photo/copy split, direct dashboard CTAs, live state below.
Colors/tokens: existing charcoal/olive and amber preserved; purple is intentionally
not copied. Image quality: original generated interior, no placeholders.
Copy/content: original Russian product copy; no Yandex names or sample values.

P2: a narrow viewport with a fine pointer still mounted the WebGL layer and
displayed a mouse hint. Fix: require a viewport wider than 600px in addition to
fine pointer, WebGL and motion preferences. Use the photograph on smaller screens.

Navigation review: disambiguated the hero's scenario link with the accessible
label “Открыть сценарии”; the main navigation retains its existing label.

Iteration 1 result: blocked pending the mobile fix.

## Iteration 2 — verified

Post-fix evidence:

- `app/data/home-hero-wide-v2.jpg` and `home-hero-comparison-v2.jpg`: re-captured
  desktop and combined reference/implementation comparison after the fix.
- `app/data/home-hero-mobile-full-v2.jpg` and `home-hero-mobile-v2.jpg`: the mobile
  photograph is now full color, without the canvas or mouse hint.
- `app/data/home-hero-final.jpg`: normal stand, completed first screen.
- `app/data/home-hero-live.jpg`: updated real home, including its existing active
  protection alert above the hero. No real device state was changed by QA.

Source image: 1898 × 786 pixels. Desktop comparison viewport: 1898 × 785 CSS px;
browser capture is 1883 × 779 image pixels after capture backend cropping/scaling.
Normal in-app viewport: 1101 × 884 CSS px, capture 1086 × 872 pixels. Mobile:
390 × 844 CSS px, full-page capture 375 × 9413 image pixels, cropped to its first
1100px for the mobile evidence. The 15px scrollbar/capture trim is not a layout
defect. Source and desktop capture were normalized to 1100px width on the same
comparison board. The difference in source height is immaterial to the adapted
composition. No pixel-perfect Yandex fidelity is claimed.

The P2 mobile issue is resolved: DOM checks at both 390px and 320px confirmed no
hero canvas and no horizontal overflow. The photo loads correctly. Desktop keeps
the genuine DitherVeil canvas and its pointer/click color reveal. All five fidelity
surfaces were checked again: typography, spacing, palette, image quality and copy.
Focused extra crops were unnecessary: this simple hero's title, body and CTAs
are legible in the raw desktop capture and the mobile crop, with no dense detail
hidden in the overview comparison.

Interactions verified in the in-app browser on the isolated stand:

- “Управлять домом” scrolls to devices and focuses the devices H2.
- Kitchen room filter shows six devices; “Все” restores the collection.
- Light switch executes and returns aria-checked=true; device dialog opens/closes.
- Hero “Открыть сценарии” reaches the scenarios page; the hero and its canvas
  unmount, then return on home navigation.
- Viewports 1898, 1101, 390 and 320px have no horizontal overflow.
- Console warning/error logs are empty in both the stand and the real home.
- Build, typecheck and diff whitespace checks passed.

Motion preference and unavailable-WebGL fallbacks were reviewed in source; OS
preferences and GPU availability were not changed on the user's computer.
Existing dashboard colors, Play font, functional controls and photo/text split
fit the requested adaptation. No actionable P0/P1/P2 findings remain.

final result: passed
