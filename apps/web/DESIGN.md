# NotebookLX Design System

**Version:** 1.1
**Last Updated:** April 8, 2026
**Status:** Living Document

---

## Catalog

- Design principles
- Responsive foundation and breakpoint map
- Color system
- Typography
- Spacing, radius, and elevation
- Component patterns
- Layout patterns
- Interaction and transparency patterns
- Accessibility standards
- Motion and animation
- Voice and tone
- Iconography
- Version history and review process

---

## Design Principles

NotebookLX is a source-grounded notebook knowledge workspace. Every surface should reinforce the same product truths:

1. **Truth over flair**  
   Citations and source boundaries are the product. Visual polish should support trust, not compete with it.

2. **Respect for attention**  
   Layout, spacing, and copy should help users move quickly from source review to grounded answers.

3. **Transparency builds trust**  
   Retrieval, query rewriting, streaming, and processing states should be visible in plain language.

4. **Calm by default, active when necessary**  
   Most surfaces should feel quiet and neutral. Motion and color only become prominent when the system is working or the user needs to act.

5. **Responsive reading is a product requirement**  
   Mobile and iPad layouts are not reduced desktop versions. Reading, scanning citations, and sending questions must stay comfortable at every width.

---

## Responsive Foundation

### Breakpoint Map

NotebookLX should use these layout ranges:

| Range | Width | Intent |
| --- | --- | --- |
| Mobile compact | `0px-479px` | Single-column reading, stacked actions, no cramped sidebars |
| Mobile large | `480px-767px` | Single-column layout with small multi-column utilities where safe |
| Tablet / iPad | `768px-1199px` | Stacked major panels, wider cards, two-up support blocks |
| Desktop | `1200px+` | Persistent two-column workspace with chat sidebar |

### Tailwind Breakpoint Aliases

Use these aliases in `apps/web`:

```ts
xs: "480px"
tablet: "768px"
desktop: "1200px"
```

### Responsive Rules

1. **Do not force desktop sidebars below `1200px`.**  
   On mobile and tablet, the notebook detail page should read top-to-bottom:
   - notebook header
   - chat
   - source workspace

2. **Prefer stacked action groups on narrow screens.**  
   Primary and secondary actions should become full width before they become too small to tap.

3. **Only introduce multi-column cards when the content still reads cleanly.**  
   Timing tiles, metadata blocks, and summary cards can move to 2 columns at `xs` or `tablet`, but source rows and evidence quotes should stay readable first.

4. **Avoid horizontal scrolling in product UI.**  
   Wrap metadata chips, stack action rows, and allow long identifiers to break.

5. **Keep chat input near the user’s current reading position.**  
   On mobile and tablet, the composer should appear before long transparency diagnostics.

6. **No bottom navigation for the current app shell.**  
   The earlier desktop-only draft suggested a mobile bottom nav. The current product should instead use a stacked document flow.

### Page-Level Behavior

#### Notebook List

- Mobile and tablet: hero, stats, CTA, then notebook cards in 1-2 columns
- Desktop: hero content and CTA cluster can sit side by side

#### Notebook Detail

- Mobile and tablet: header card, chat panel, source workspace
- Desktop: left content column plus right sticky chat panel

#### Dialogs

- Mobile: nearly full-width centered sheet
- Tablet and desktop: standard modal width with generous padding

---

## Color System

### Primary Palette

NotebookLX uses cool neutral grays with blue reserved for primary actions and links.

```css
--gray-50:  #f8fafc
--gray-100: #f1f5f9
--gray-200: #e2e8f0
--gray-300: #cbd5e1
--gray-400: #94a3b8
--gray-500: #64748b
--gray-600: #475569
--gray-700: #334155
--gray-800: #1e293b
--gray-900: #0f172a
```

### Semantic Colors

```css
--success-bg: #dcfce7
--success-text: #166534
--success-border: #86efac

--warning-bg: #fef9c3
--warning-text: #854d0e
--warning-border: #fde047

--error-bg: #fee2e2
--error-text: #991b1b
--error-border: #fca5a5

--info-bg: #dbeafe
--info-text: #075985
--info-border: #7dd3fc

--citation-bg: #fef3c7
--citation-text: #92400e
--citation-border: #fcd34d
```

### Accent Color

```css
--accent: #2563eb
--accent-hover: #1d4ed8
--accent-light: #3b82f6
```

**Usage:** Accent blue is for the main CTA, focused links, and key active states. The workspace should still look primarily neutral.

---

## Typography

### Font Families

- **Primary:** Inter, then system sans fallback
- **Monospace:** JetBrains Mono, then system mono fallback

### Core Type Scale

| Token | Size | Usage |
| --- | --- | --- |
| `text-xs` | `12px` | Labels, metadata, chips |
| `text-sm` | `14px` | Secondary body text, helper copy |
| `text-base` | `16px` | Primary body text |
| `text-lg` | `18px` | Emphasized body |
| `text-xl` | `20px` | Subheadings |
| `text-2xl` | `24px` | Section titles |
| `text-3xl` | `30px` | Mobile page headings |
| `text-4xl` | `36px` | Large tablet headings |
| `text-5xl` | `48px` | Desktop page headings |

### Responsive Type Guidance

- Mobile page title: `text-3xl`
- Large mobile / tablet page title: `text-4xl`
- Desktop page title: `text-5xl` when the surface has enough room
- Dense diagnostic surfaces should stay at `text-sm`
- Quotes and citations can use `13px` mono text for scanability

### Weights and Leading

```css
--font-normal: 400
--font-medium: 500
--font-semibold: 600
--font-bold: 700

--leading-tight: 1.25
--leading-normal: 1.5
--leading-relaxed: 1.625
```

---

## Spacing, Radius, and Elevation

### Spacing

Use Tailwind’s 4px base scale.

```css
--space-1:  0.25rem
--space-2:  0.5rem
--space-3:  0.75rem
--space-4:  1rem
--space-5:  1.25rem
--space-6:  1.5rem
--space-8:  2rem
--space-10: 2.5rem
--space-12: 3rem
```

### Radius

- Standard input/button radius: `rounded-xl`
- Primary cards: `rounded-3xl`
- Dense subcards and diagnostics: `rounded-2xl`

### Elevation

- Base cards: soft border + minimal shadow
- Hero cards and major workspace shells: deeper but still diffused shadow
- Avoid heavy shadow stacks on mobile

---

## Component Patterns

### Buttons

#### Primary

- Blue background
- White text
- Medium weight
- Minimum 44px touch target

#### Secondary / Outline

- Neutral background or border
- Slate text
- Used for refresh, toggles, and supporting actions

#### Responsive Rules

- On narrow screens, action groups should stack to full width before becoming cramped
- On card surfaces, do not hide the only access to important actions behind hover-only states on touch devices

### Inputs and Textareas

- White fill
- Soft neutral border
- Blue focus ring
- Rounded corners
- Textareas should remain large enough to type comfortably on mobile

### Cards

- White or nearly-white background
- Neutral border
- Rounded large corners
- Slight blur and shadow for workspace shells

### Notebook Cards

- Show notebook name, creation date, description, and “open workspace” affordance
- Edit/delete actions should be visible on mobile and tablet touch surfaces
- Footer metadata wraps instead of squeezing

### Source Rows

- Title
- Source type and date metadata
- Status badge
- Delete action
- Progress or error block

Responsive rules:

- Mobile: stack source info and actions vertically
- Tablet and desktop: allow split header row
- Never truncate away the only actionable status information

### Chat Bubbles

#### User

- Blue surface
- Right aligned
- Short label and readable line height
- Slightly wider max width on phones than on desktop

#### Assistant

- Neutral surface
- Left aligned
- Citation markers inline with answer text

### Citation Markers

- Inline amber badge
- Mono numerals
- Clearly focusable and clickable

### Transparency Panels

These include:

- query rewrite
- chat timing
- retrieved evidence
- citation detail

Responsive rules:

- Mobile: single column, stacked cards, comfortable vertical spacing
- Large mobile: simple 2-up tile grids only for short metrics
- Tablet and desktop: 2-up metric tiles are acceptable

---

## Layout Patterns

### Notebook List Page

Structure:

1. hero card
2. notebook count / CTA cluster
3. notebook grid or empty state

Responsive behavior:

- Mobile: single column
- Tablet: notebook cards can move to 2 columns
- Desktop: notebook cards can move to 3 columns

### Notebook Detail Page

The current product layout is:

#### Mobile and Tablet

1. back navigation
2. notebook header card
3. chat panel
4. source workspace

#### Desktop

1. back navigation
2. left content column:
   - notebook header card
   - source workspace
3. right column:
   - sticky chat panel

### Chat Panel

Core rules:

- header remains visible and compact
- messages scroll independently
- input stays easy to reach
- diagnostics remain available without blocking the conversation flow

Responsive behavior:

- Mobile and tablet: composer appears before long diagnostics
- Desktop: diagnostics can sit above the composer inside the persistent panel
- Keep the panel tall enough to feel like a workspace, not a short widget

### Reserved Content Cards

Summary and generated-assets placeholders should stack on mobile and go 2-up on tablet and desktop.

---

## Interaction and Transparency Patterns

### Streaming States

When content streams:

1. show an initial working state
2. expose notebook-grounded status copy
3. render deltas incrementally
4. preserve the answer in a single assistant bubble

### Chat Workflow States

Use notebook-grounded language:

- “Working through notebook sources”
- “Searching this notebook’s sources”
- “Waiting for the first answer chunk from the model”
- “Grounded answer ready”

### Query Rewriting Transparency

Behavior:

- Default to collapsed details
- Explain what changed in plain language
- Expose original query, standalone question, retrieval searches, and strategy

### Retrieval Transparency

Always support:

- chunk count
- source count
- per-source grouping
- quote inspection
- score or page metadata when available

### Empty States

Every empty state should include:

1. a friendly heading
2. context about why the area is empty
3. the next action
4. a lightweight supporting visual or icon

### Error States

Every error should include:

1. what went wrong
2. plain-language context
3. recovery guidance
4. a retry path when retry is safe

---

## Accessibility Standards

NotebookLX targets **WCAG 2.1 AA** at minimum.

### Requirements

- Color contrast: `4.5:1` for standard text
- Touch targets: minimum `44x44px`
- Visible focus states on all interactive elements
- Keyboard access for dialogs, toggles, citations, and chat controls
- ARIA live regions for streaming or status updates

### Focus Treatment

```css
:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}
```

### Mobile Accessibility Notes

- Do not rely on hover-only disclosure for critical actions
- Avoid tiny close buttons or icon-only actions without labels
- Let long notebook IDs and URLs wrap instead of overflow

---

## Motion and Animation

### Principles

1. purposeful
2. subtle
3. disabled or reduced when the user prefers less motion

### Duration Scale

```css
--duration-fast: 150ms
--duration-base: 300ms
--duration-slow: 500ms
```

### Motion Guidance

- Hover and tap feedback: fast
- Modal entry and exit: base
- Streaming indicators: restrained pulse only
- Avoid theatrical transitions on workspace screens

---

## Voice and Tone

### Copy Rules

1. Say “your sources” or “this notebook” instead of implying general web knowledge.
2. Be specific about what the system is doing.
3. Prefer calm, plain language over clever phrasing.
4. Keep CTAs action-oriented: “Add source”, “Refresh”, “Try again”.

### Error Copy

- Avoid provider or infrastructure jargon when the user does not need it.
- State whether notebook data is safe.
- Tell the user what to do next.

---

## Iconography

Use **Lucide React**.

Recommended mappings:

- Citation: `Quote`, `FileText`
- Source type: `File`, `Globe`, `FileText`
- Ready: `CheckCircle`
- Pending: `Clock`
- Processing: `Loader`
- Failed: `XCircle`, `AlertTriangle`
- Add: `Plus`
- Delete: `Trash`
- Refresh: `RefreshCw`
- Help or context: `Info`, `HelpCircle`

### Sizing

```css
--icon-xs: 14px
--icon-sm: 16px
--icon-base: 20px
--icon-lg: 24px
```

---

## Version History

### Version 1.1 — April 8, 2026

- Refactored the document structure
- Replaced desktop-only layout guidance with explicit mobile, tablet, and desktop behavior
- Standardized responsive breakpoint aliases for `apps/web`
- Updated notebook detail guidance to match the current stacked mobile/tablet flow and desktop sticky chat layout

### Version 1.0 — April 8, 2025

- Initial design system draft
- Established neutral-gray workspace, transparency UX, and accessibility baseline

---

## Design Review Process

Before shipping new UI:

1. Check `DESIGN.md` first.
2. Reuse existing shared primitives where possible.
3. Review empty, loading, success, and error states.
4. Verify mobile, tablet, and desktop behavior explicitly.
5. Check keyboard access, focus states, and contrast.

**Ownership:** NotebookLX team  
**Related docs:** `CLAUDE.md`, `AGENTS.md`, `DEVELOPMENT_PLAN.md`
