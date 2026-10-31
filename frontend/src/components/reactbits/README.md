# React Bits components

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
