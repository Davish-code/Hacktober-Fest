---
name: Technical Blueprint & Avionics Spec
colors:
  surface: '#fcf9f2'
  surface-dim: '#dcdad3'
  surface-bright: '#fcf9f2'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f6f3ec'
  surface-container: '#f1eee7'
  surface-container-high: '#ebe8e1'
  surface-container-highest: '#e5e2db'
  on-surface: '#1c1c18'
  on-surface-variant: '#5b4038'
  inverse-surface: '#31312c'
  inverse-on-surface: '#f3f0e9'
  outline: '#8f7067'
  outline-variant: '#e4beb3'
  surface-tint: '#ae3200'
  primary: '#ae3200'
  on-primary: '#ffffff'
  primary-container: '#ff5a1f'
  on-primary-container: '#541400'
  inverse-primary: '#ffb59e'
  secondary: '#5d5e63'
  on-secondary: '#ffffff'
  secondary-container: '#e2e2e8'
  on-secondary-container: '#636469'
  tertiary: '#615e55'
  on-tertiary: '#ffffff'
  tertiary-container: '#969288'
  on-tertiary-container: '#2d2b24'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#ffdbd0'
  primary-fixed-dim: '#ffb59e'
  on-primary-fixed: '#3a0b00'
  on-primary-fixed-variant: '#852400'
  secondary-fixed: '#e2e2e8'
  secondary-fixed-dim: '#c6c6cc'
  on-secondary-fixed: '#1a1c20'
  on-secondary-fixed-variant: '#45474b'
  tertiary-fixed: '#e7e2d7'
  tertiary-fixed-dim: '#cbc6bb'
  on-tertiary-fixed: '#1d1c15'
  on-tertiary-fixed-variant: '#49473f'
  background: '#fcf9f2'
  on-background: '#1c1c18'
  surface-variant: '#e5e2db'
typography:
  headline-xl:
    fontFamily: Space Grotesk
    fontSize: 38px
    fontWeight: '700'
    lineHeight: 44px
    letterSpacing: -0.03em
  headline-xl-mobile:
    fontFamily: Space Grotesk
    fontSize: 28px
    fontWeight: '700'
    lineHeight: 34px
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Space Grotesk
    fontSize: 28px
    fontWeight: '600'
    lineHeight: 36px
    letterSpacing: -0.02em
  headline-lg-mobile:
    fontFamily: Space Grotesk
    fontSize: 22px
    fontWeight: '600'
    lineHeight: 28px
    letterSpacing: -0.01em
  headline-md:
    fontFamily: Space Grotesk
    fontSize: 20px
    fontWeight: '600'
    lineHeight: 26px
    letterSpacing: -0.01em
  headline-sm:
    fontFamily: Space Grotesk
    fontSize: 16px
    fontWeight: '600'
    lineHeight: 22px
    letterSpacing: 0em
  body-lg:
    fontFamily: Space Grotesk
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  body-md:
    fontFamily: Space Grotesk
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  body-sm:
    fontFamily: Space Grotesk
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 16px
  label-lg:
    fontFamily: JetBrains Mono
    fontSize: 13px
    fontWeight: '500'
    lineHeight: 18px
    letterSpacing: 0.04em
  label-md:
    fontFamily: JetBrains Mono
    fontSize: 11px
    fontWeight: '500'
    lineHeight: 16px
    letterSpacing: 0.06em
  label-sm:
    fontFamily: JetBrains Mono
    fontSize: 10px
    fontWeight: '500'
    lineHeight: 14px
    letterSpacing: 0.08em
  code-body:
    fontFamily: JetBrains Mono
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 18px
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  gutter: 1rem
  gutter-lg: 1.5rem
  margin: 1rem
  margin-md: 1.5rem
  margin-lg: 2rem
  space-xs: 0.25rem
  space-sm: 0.5rem
  space-md: 0.75rem
  space-lg: 1rem
  space-xl: 1.5rem
  space-2xl: 2rem
---

## Brand & Style

The design system models itself after high-reliability operational consoles, flight checklists, and aerospace schematics. It operates on the thesis that autonomous AI systems propose non-deterministic intent, but deterministic code strictly governs execution. The interface serves engineers, systems operators, and infrastructure leads who require total state observability, precise verification steps, and unyielding determinism before dispatching commands.

The visual style blends **Technical Blueprint Precision** with an **Aerospace Checklist Minimalist** framework:
- Surfaces emulate warm, matte technical draughting parchment rather than sterile clinical gray.
- Interfaces abandon ambient drop shadows, blurred overlays, and decorative pill roundings in favor of 1px hairline registers, crosshair intersection markers (`+`), step coordinates (e.g., `S-01`, `AX-904`), and strict spatial metering.
- Emotional tone: Authoritative, calm under load, meticulously verifiable, and uncompromisingly direct.

## Colors

The system uses a tightly controlled palette derived from physical engineering paper and high-visibility safety telemetry:

- **Canvas & Surface (Warm Technical Paper):** Base background `#F4F1EA` paired with structural borders `#D8D3C8` (primary grid) and `#E2DDD3` (subtle dividers). Raised cards sit on `#FAF8F5`, while active telemetry panels drop into high-contrast `#14161A` (Ink-Black).
- **Ink & Typography:** Primary text `#14161A`, muted drafting annotations `#5A5852`, and disabled/coordinate labels `#8C877D`.
- **Primary Signal Accent (Safety Orange):** `#FF5A1F` functions strictly as an operational dispatch trigger, active execution indicator, and critical breaker. It is never used for trivial decoration.
- **Strict Semantic Status Engine:**
  - **Read-Only / Validated Intent:** Green `#1B683B` text/border on `#EBF5EE` wash.
  - **Sandboxed Write / Warning Caution:** Amber `#A35200` text/border on `#FEF4E6` wash.
  - **External Mutation / Critical Halt:** Red `#B82424` text/border on `#FDF0F0` wash.
  - **System Standby / Nominal Log:** Deep Ink `#22252A` on `#ECE7DD`.

## Typography

The typographic hierarchy pairs structural geometric authority with monospaced instrumentation:

- **Headlines & Interface Narrative (Space Grotesk):** Delivers clean technical posture without feeling generic. Used for component titles, panel IDs, and workflow headings. Numbers within headlines should invoke tabular layout features where available.
- **Telemetry, Parameters, Coordinates & Logs (JetBrains Mono):** Drives operational data, parameter diffs, machine coordinates (`PIPELINE-V2.4`, `NODE_0x7A`), timestamps, status badges, and execution steps. Monospaced type ensures vertical alignment of step matrices and bit-level changes.
- **Letter Spacing:** All monospaced labels and status indicators use uppercase casing with deliberate letter-spacing (`0.04em` to `0.08em`) to mimic stamped avionics chassis placards.

## Layout & Spacing

The layout model simulates an 8px technical drafting grid:

- **Grid Framework:** A 12-column rigid fluid grid for desktop and tablet, collapsing to a single-column sequence on mobile. Columns are separated by explicit 1px `#D8D3C8` hairline dividers rather than arbitrary white space.
- **Faint Grid Background:** Main viewport surfaces carry an 8px SVG dot matrix (`rgba(20, 22, 26, 0.05)`) calibrated to align with major card origins.
- **Corner Register Glyphs:** Outer container cards and modular control panels display hairline corner crosses (`+`) at layout intersections.
- **Breakpoints:**
  - `Desktop (>= 1200px)`: Fixed-margin 12-column layout with pinned inspection and timeline telemetry sidebars.
  - `Tablet (768px - 1199px)`: 8-column layout, collateral parameter inspector collapses into bottom-anchored drawer.
  - `Mobile (< 768px)`: 4-column linear execution flow; secondary technical coordinates truncate or hide.

## Elevation & Depth

This design system rejects blurred, soft drop shadows entirely. Depth is achieved via strict planar layering and hairline framing:

- **Flat Registration:** All cards, wells, and inputs occupy coordinate planes delineated by 1px solid hairlines (`#D8D3C8` on light canvas, `#22252A` on dark surfaces).
- **Hard Technical Shadow (Interactive State):** Primary buttons and focused command cards use a zero-blur, solid offset shadow: `box-shadow: 2px 2px 0px #14161A`. Active or depressed states shift `translate(1px, 1px)` with `1px 1px 0px #14161A`.
- **Tonal Well Depressions:** Code blocks, log terminals, and parameter diff wells employ internal inset backgrounds (`#ECE7DD` on light, `#0D0E11` on dark) framed with a 1px border.
- **Dashed Connectors:** Relationships between pipeline nodes and subsequent steps utilize 1px dashed hairline rules (`stroke-dasharray: 4, 4` in `#8C877D`).

## Shapes

The geometric framework is uncompromisingly industrial and rigid:

- **Corner Radii:** Strictly limited to `2px` (`roundedness: 1` scaled to a precise physical hairline radius of `2px` across all structural containers, buttons, tags, and form fields). Under no circumstances are circular pill buttons or soft, sweeping radii permitted.
- **Notched & Ruled Accents:** Critical action drawers may feature 45-degree chamfered corners (4px clip-path) or 2px thick safety-orange top indicator bars to signify terminal dispatch readiness.

## Components

### Buttons & Triggers
- **Primary Dispatch (`#FF5A1F`):** Background `#FF5A1F`, foreground `#FFFFFF`, 1px border `#14161A`, 2px hard black offset shadow. Font: Space Grotesk Bold, 13px, uppercase. Focused on irreversible execution.
- **Secondary / Step Button:** Background `#FAF8F5`, foreground `#14161A`, 1px border `#D8D3C8`. Hover state swaps background to `#ECE7DD`.
- **Destructive Breakout:** Background `#B82424`, foreground `#FFFFFF`, 1px border `#14161A`.

### Status Badges & Chips
- Monospaced 10px uppercase string framed with 1px border. No pill shapes; strictly 2px radius.
- **Read-Only:** Green `#1B683B` text, `#EBF5EE` fill, `#1B683B` border. Prefixed with `[RO]`.
- **Sandboxed Write:** Amber `#A35200` text, `#FEF4E6` fill, `#A35200` border. Prefixed with `[SBX]`.
- **Side-Effect / Mutation:** Red `#B82424` text, `#FDF0F0` fill, `#B82424` border. Prefixed with `[MUT]`.

### Form Inputs & Parameter Fields
- Background `#FAF8F5`, 1px border `#D8D3C8`, text `#14161A`. JetBrains Mono typography for value parsing.
- Active/Focus: 1px outline with `#FF5A1F` border ring and no glow.
- Inline coordinate prefix labels (e.g., `PAR-01:`, `PORT:`) render in muted `#8C877D` mono.

### Checkboxes & Binary Toggle Gates
- Square 14px boxes with 1px `#14161A` borders, 2px radius. Checked state displays a solid ink `#14161A` square block or cross (`✕`), avoiding rounded checkmarks.

### Cards & Execution Panels
- Background `#FAF8F5`, 1px border `#D8D3C8`. Header regions separated by a horizontal 1px divider with an integrated monospaced breadcrumb tracker (`MODULE::VERIFY_STAGING // 0x4F`).
- Card headers optionally host crosshair glyphs (`+`) positioned at top-left and top-right bounding limits.

### Log Windows & Diff Terminals
- Deep ink `#14161A` background with crisp `#D8D3C8` muted text, line numbers rendered in `#5A5852`, and highlighted dispatch signals in vivid `#FF5A1F`.