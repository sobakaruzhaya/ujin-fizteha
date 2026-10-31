# React Bits components

ScrubField (JS/CSS) is installed from the official registry:
https://reactbits.dev/r/ScrubField-JS-CSS.json
https://reactbits.dev/micro/scrub-field
Device settings use its drag, keyboard and direct text entry with automatic
saving on commit. Local additions: stable input IDs and accessible names,
Russian drag hint, strict finite-number parsing (including decimal commas),
and preserving typed input after keyboard adjustments. Colors follow the app palette.

CountUp, Dither, DarkVeil and SpotlightCard are installed from the official
React Bits registry: https://reactbits.dev/r/{name}-JS-CSS.json.

Upstream project: https://github.com/DavidHDev/react-bits (MIT + Commons Clause;
see the attached LICENSE.md).
The downloaded source components are retained here with their original APIs.

The project registry is configured in `/components.json`. The shadcn MCP server
is configured in `/.mcp.json` and in the local Codex configuration. Run
`npm run mcp:check` for a real stdio handshake and registry search.

Reduced motion disables the canvas layers and uses static values instead of
CountUp. The product images and all device controls work without WebGL.

Home hero: FadeContent and BlurText use the official React Bits source:
https://github.com/DavidHDev/react-bits/tree/main/src/content/Animations/FadeContent
https://github.com/DavidHDev/react-bits/tree/main/src/content/TextAnimations/BlurText
PixelSwap now handles the home photograph's pixel entrance and hover transition
to a brighter close-up of the same scene. Its JS/CSS source retains the official API:
https://github.com/DavidHDev/react-bits/tree/main/src/content/Animations/PixelSwap
The hero renders a static image when reduced motion is enabled.
BlurText adds an optional `as` prop (default `p`) for valid semantic heading spans.

SwipeToast (JS/CSS) was installed from the official registry:
https://reactbits.dev/r/SwipeToast-JS-CSS.json
Documentation: https://reactbits.dev/micro/swipe-toast
The local source adds optional `role` and `closeLabel` props for accessible
critical alerts and a Russian close button. Escape also prevents the native
dialog's default close action when dismissing a focused toast. Other APIs and swipe/timer behavior
are retained; existing Motion and Hugeicons dependencies are reused.
