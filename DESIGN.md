# NotebookLX Design System

**Version:** 1.0
**Last Updated:** 2025-04-08
**Status:** Living Document

---

# Catalog
  - Design principles (truth over flair, transparency builds trust)
  - Color system (neutral grays, semantic colors, accent blue)
  - Typography (Inter, JetBrains Mono for code)
  - Spacing system (Tailwind-based)
  - Component patterns (buttons, inputs, message bubbles, citations)
  - Interaction patterns (streaming states, status indicators, empty/error states)
  - Accessibility standards (WCAG 2.1 AA)
  - Motion & animation (150-300ms easing)
  - Specific features (query rewriting transparency UX, retrieval transparency)
  - Layout patterns (3-panel notebook detail, chat panel)
  - Voice & tone guidelines
  - Iconography (Lucide React)

## Design Principles

NotebookLX is a source-grounded notebook knowledge workspace. Every design decision reflects these core values:

1. **Truth over flair** — Citations and source grounding are primary. Visual polish supports credibility, never distracts from it.

2. **Respect for attention** — Users are here to learn from their sources. Efficient information hierarchy and clear interaction states honor their time.

3. **Transparency builds trust** — Show what the system is doing (retrieval, rewriting, processing). Invisible magic erodes trust; visible mechanics build it.

4. **Calm workspace, alive when it matters** — Default surfaces are minimal and focused. Activity indicators, streaming, and real-time updates provide aliveness without clutter.

5. **Sources first, always** — The notebook's sources are the truth boundary. Design reinforces that answers come from explicitly added content.

---

## Color System

### Primary Palette (Neutral Grays)

Based on Tailwind's gray scale. Cool-toned (slate/gray) for professional workspace feel.

```css
--gray-50:  #f8fafc   /* Page background */
--gray-100: #f1f5f9   /* Card background */
--gray-200: #e2e8f0   /* Borders, dividers */
--gray-300: #cbd5e1   /* Disabled states */
--gray-400: #94a3b8   /* Placeholder text */
--gray-500: #64748b   /* Secondary text */
--gray-600: #475569   /* Primary text */
--gray-700: #334155   /* Emphasized text */
--gray-800: #1e293b   /* Headings */
--gray-900: #0f172a   /* Deep backgrounds */
```

### Semantic Colors

```css
/* Success */
--success-bg: #dcfce7
--success-text: #166534
--success-border: #86efac

/* Warning / Processing */
--warning-bg: #fef9c3
--warning-text: #854d0e
--warning-border: #fde047

/* Error / Failure */
--error-bg: #fee2e2
--error-text: #991b1b
--error-border: #fca5a5

/* Info / Retrieval */
--info-bg: #dbeafe
--info-text: #075985
--info-border: #7dd3fc

/* Citations */
--citation-bg: #fef3c7
--citation-text: #92400e
--citation-border: #fcd34d
```

### Accent Color (CTA, Links)

```css
--accent: #2563eb       /* Blue-600 */
--accent-hover: #1d4ed8 /* Blue-700 */
--accent-light: #3b82f6 /* Blue-500 */
```

**Usage:** Reserve for primary actions (Send message, Add source). Avoid overuse — neutral grays should dominate.

---

## Typography

### Font Family

- **Primary:** Inter (system font stack fallback)
- **Monospace:** JetBrains Mono (for code, citations)

```css
font-family: 'Inter', system-ui, -apple-system, sans-serif;
font-family-mono: 'JetBrains Mono', 'SF Mono', Monaco, monospace;
```

### Type Scale

```css
--text-xs:   0.75rem    /* 12px - Labels, metadata */
--text-sm:   0.875rem   /* 14px - Body secondary, captions */
--text-base: 1rem       /* 16px - Body primary */
--text-lg:   1.125rem   /* 18px - Emphasized body */
--text-xl:   1.25rem    /* 20px - Subheadings */
--text-2xl:  1.5rem     /* 24px - Section headings */
--text-3xl:  1.875rem   /* 30px - Page headings */
```

### Font Weights

```css
--font-normal: 400
--font-medium: 500
--font-semibold: 600
--font-bold: 700
```

### Line Heights

```css
--leading-tight: 1.25    /* Headings */
--leading-normal: 1.5    /* Body text */
--leading-relaxed: 1.625 /* Comfortable reading */
```

---

## Spacing System

Based on Tailwind's 4px base unit scale.

```css
--space-1:  0.25rem   /* 4px */
--space-2:  0.5rem    /* 8px */
--space-3:  0.75rem   /* 12px */
--space-4:  1rem      /* 16px */
--space-5:  1.25rem   /* 20px */
--space-6:  1.5rem    /* 24px */
--space-8:  2rem      /* 32px */
--space-10: 2.5rem    /* 40px */
--space-12: 3rem      /* 48px */
```

**Usage defaults:**
- Component padding: `--space-3` to `--space-4`
- Section spacing: `--space-8` to `--space-12`
- Gap between related elements: `--space-2`

---

## Component Patterns

### Buttons

#### Primary Button

```css
background: var(--accent);
color: white;
padding: var(--space-2) var(--space-4);
border-radius: 6px;
font-weight: var(--font-medium);
transition: background 150ms ease;
```

States: Hover (`--accent-hover`), Active (slightly darker), Disabled (`--gray-300`)

#### Secondary Button

```css
background: var(--gray-100);
color: var(--gray-700);
border: 1px solid var(--gray-200);
padding: var(--space-2) var(--space-4);
border-radius: 6px;
font-weight: var(--font-medium);
```

#### Ghost Button (for tertiary actions)

```css
background: transparent;
color: var(--gray-600);
padding: var(--space-2) var(--space-3);
border-radius: 6px;
```

Hover state: `background: var(--gray-100)`

### Inputs

#### Text Input / Textarea

```css
background: white;
border: 1px solid var(--gray-200);
border-radius: 6px;
padding: var(--space-3);
font-size: var(--text-base);
color: var(--gray-700);
```

Focus state: `border-color: var(--accent); outline: 2px solid rgba(37, 99, 235, 0.1)`

Error state: `border-color: var(--error-border)`

### Cards

```css
background: white;
border: 1px solid var(--gray-200);
border-radius: 8px;
padding: var(--space-4);
box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
```

Elevated cards (modals, popovers): `box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1)`

### Message Bubbles (Chat)

#### User Message

```css
background: var(--accent);
color: white;
border-radius: 12px 12px 0 12px;
padding: var(--space-3) var(--space-4);
align-self: flex-end;
max-width: 80%;
```

#### Assistant Message

```css
background: var(--gray-100);
color: var(--gray-800);
border-radius: 12px 12px 12px 0;
padding: var(--space-3) var(--space-4);
align-self: flex-start;
max-width: 85%;
```

### Citation Markers

Inline citation badges within assistant messages:

```css
background: var(--citation-bg);
color: var(--citation-text);
border-radius: 4px;
padding: 2px 6px;
font-size: var(--text-xs);
font-weight: var(--font-medium);
font-family-mono: var(--font-mono);
cursor: pointer;
transition: background 150ms ease;
```

Hover state: `background: var(--citation-border)`

---

## Interaction Patterns

### Streaming States

When content streams in (SSE), show incremental updates with:

1. **Skeleton pulse** for initial loading state
2. **Typing indicator** (3 animated dots) before first token
3. **Incremental rendering** — append tokens as they arrive
4. **Fade-in animation** for completed content blocks

```css
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.6; }
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(4px); }
  to { opacity: 1; transform: translateY(0); }
}
```

### Status Indicators

#### Source Status Badges

- **Pending:** Gray badge, clock icon
- **Processing:** Blue badge, spinner animation
- **Ready:** Green badge, checkmark icon
- **Failed:** Red badge, error icon + error message

#### Chat Workflow States

Inline status below chat input:

- "Searching your sources..." (neutral)
- "Optimizing your question..." (during query rewrite)
- "Retrieved 12 chunks from 3 sources" (transparency)

### Empty States

Every empty state includes:

1. **Warm heading** — friendly, not technical
2. **Context** — why is this empty?
3. **Primary action** — what should the user do next?
4. **Supporting visual** — simple illustration or icon

Example (chat with no sources):
```
┌─────────────────────────────────────────┐
│   No sources yet                        │
│                                         │
│   Add sources to this notebook to      │
│   start asking questions.               │
│                                         │
│   [Add Source]                          │
└─────────────────────────────────────────┘
```

### Error States

All errors include:

1. **User-friendly message** — what went wrong (in plain language)
2. **Context** — why did this happen?
3. **Recovery action** — what can the user do now?
4. **Secondary option** — retry, skip, contact support

#### Error Card Format

```
┌─────────────────────────────────────────┐
│  ⚠️  Couldn't process your source       │
│                                         │
│  The PDF file may be corrupted or      │
│  password-protected.                    │
│                                         │
│  [Try Again]  [Upload Different File]   │
└─────────────────────────────────────────┘
```

---

## Accessibility Standards

### WCAG 2.1 AA Compliance (Minimum)

- **Color contrast:** 4.5:1 for normal text, 3:1 for large text (18px+)
- **Touch targets:** Minimum 44×44px for interactive elements
- **Keyboard navigation:** All functionality accessible via Tab, Enter, Escape
- **Focus indicators:** Visible 2px outline on all focusable elements
- **Screen readers:** Proper ARIA labels, roles, and live regions

### Focus Management

```css
:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
  border-radius: 4px;
}
```

### ARIA Live Regions

For streaming content and status updates:

```html
<div role="status" aria-live="polite" aria-atomic="true">
  Searching for: 'machine learning algorithms...'
</div>
```

- **`polite`** for status updates (searching, processing)
- **`assertive`** only for errors and critical alerts
- **`atomic="true"`** when entire content replaces (not appends)

---

## Motion & Animation

### Principles

1. **Purposeful motion** — Every animation serves a function (guides attention, confirms action, indicates state)
2. **Subtle over showy** — Prefer 150-300ms easing functions
3. **Respect prefers-reduced-motion** — Disable all motion when user prefers static

### Duration Scale

```css
--duration-fast:   150ms   /* Hover states, toggles */
--duration-base:   300ms   /* Modal open/close */
--duration-slow:   500ms   /* Page transitions */
```

### Easing Functions

```css
--ease-out: cubic-bezier(0, 0, 0.2, 1)     /* Most common */
--ease-in-out: cubic-bezier(0.4, 0, 0.2, 1) /* Modal transitions */
```

### Animation Examples

#### Fade In (Content appearing)

```css
.fade-in {
  animation: fadeIn var(--duration-base) var(--ease-out);
}
```

#### Slide Up (Modals, sheets)

```css
.slide-up {
  animation: slideUp var(--duration-base) var(--ease-out);
}

@keyframes slideUp {
  from { transform: translateY(100%); opacity: 0; }
  to { transform: translateY(0); opacity: 1; }
}
```

#### Pulse (Processing indicators)

```css
.pulse {
  animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}
```

---

## Specific Features

### Query Rewriting Transparency

**Decision:** Variant C — Full Transparency with Toggle

#### Behavior

1. **When user sends a message:**
   - Show inline status below input: "📝 Rewriting: [original] → [rewritten]"
   - Include info icon with tooltip: "Improved for better source matching"
   - Auto-collapse after 3 seconds to: "Searching for: '[rewritten]'"

2. **Settings toggle:**
   - Location: Settings panel (notebook-level or account-level)
   - Label: "Always show rewritten queries"
   - Default: Off (auto-collapse behavior)

3. **Error handling:**
   - If rewrite fails: Silently fall back to original query
   - Show: "Searching for: '[original query]'"
   - No error message to user (graceful degradation)

#### UI Specification

```typescript
// Rewritten query display (inline status)
<div className="flex items-center gap-2 text-sm text-gray-600">
  <span className="text-gray-500">📝 Rewrote:</span>
  <span className="line-through opacity-60">"{original}"</span>
  <span>→</span>
  <span className="italic">"{rewritten}"</span>
  <InfoIcon tooltip="Improved for better source matching" />
</div>

// Collapsed state (after 3s)
<div className="text-sm text-gray-500 italic">
  Searching for: '{rewritten}'
</div>

// Settings toggle
<Switch
  label="Always show rewritten queries"
  description="See how questions are optimized for your sources"
  defaultChecked={false}
/>
```

#### Accessibility

- Screen reader announcement: `"Rewrote your question. Searching for: {rewritten}"`
- Keyboard: Tab to expand/collapse, Enter to toggle
- Auto-collapse respects `prefers-reduced-motion`

### Retrieval Transparency

#### Chunk Count Display

When retrieval completes, show:

```
Retrieved 12 chunks from 3 sources
```

- **Chunk count:** Number of chunks used for generation
- **Source count:** Number of unique sources referenced
- **Placement:** Below input, replaces search status when retrieval completes

#### Chunk-to-Source Panel

Expandable panel showing which chunks came from which sources:

```
┌─────────────────────────────────────────┐
│  Sources used (12 chunks)              │
│                                         │
│  📄 Research Paper.pdf (8 chunks)      │
│     • Page 3: "Methodology section..." │
│     • Page 7: "Algorithm comparison..." │
│                                         │
│  📄 Notes.txt (4 chunks)                │
│     • "Key findings from experiment..." │
└─────────────────────────────────────────┘
```

---

## Layout Patterns

### Notebook Detail Page (3-Panel Layout)

```
┌────────────────┬───────────────────┬─────────────────┐
│                │                    │                 │
│  Source List   │  Notebook Summary  │   Chat Panel    │
│                │                    │                 │
│  - Sources     │  - Overview        │   - Messages    │
│  - Status      │  - Key Topics       │   - Citations   │
│  - Actions     │  - Generated Assets │   - Input       │
│                │                    │                 │
└────────────────┴───────────────────┴─────────────────┘
```

**Responsive behavior:**
- Desktop (>1024px): 3 panels visible
- Tablet (768-1024px): Sources collapsible, chat always visible
- Mobile (<768px): Single panel with bottom navigation

### Chat Panel (Always Visible)

- **Fixed position** on desktop (right side)
- **Full height** minus header
- **Input always visible** at bottom (sticky)
- **Messages scroll** above input
- **Auto-scroll** to latest message when user sends

---

## Voice & Tone

### Copy Guidelines

1. **Source-oriented language:** "Your sources show..." rather than "I found..."
2. **Confidence calibration:** "Based on your sources..." for answers, "I don't have enough information" for gaps
3. **Action-oriented CTAs:** "Add source" not "Manage sources"
4. **Process transparency:** "Searching your sources..." "Retrieving relevant chunks..." "Reading your PDF..."

### Error Messages

**Avoid technical jargon.** Replace with user-friendly alternatives:

- ❌ "SSE connection timeout" → ✅ "Connection interrupted. Please check your internet."
- ❌ "Embedding generation failed" → ✅ "Couldn't process this source. Try uploading again."
- ❌ "Retrieval returned zero chunks" → ✅ "No relevant information found in your sources. Try rephrasing your question."

---

## Iconography

### Icon Library

Use **Lucide React** (already included with shadcn/ui)

### Common Icons

- **Citation:** `Quote` or `FileText`
- **Source types:** `File` (PDF), `Globe` (URL), `FileText` (plain text)
- **Status:** `CheckCircle` (ready), `Clock` (pending), `Loader` (processing), `XCircle` (failed)
- **Actions:** `Plus` (add), `Trash` (delete), `Refresh` (retry), `Settings` (config)
- **Info:** `Info` (tooltip help), `AlertTriangle` (warning), `HelpCircle` (guidance)

### Icon Sizing

```css
--icon-xs:   14px   /* Inline with text-xs */
--icon-sm:   16px   /* Default, inline with body text */
--icon-base: 20px   /* Section headings */
--icon-lg:   24px   /* Feature emphasis */
```

---

## Breaking Changes & Versioning

This DESIGN.md is versioned. When making breaking changes:

1. Increment version number (1.0 → 1.1 → 2.0)
2. Document what changed and why
3. Update migration notes for existing code

**Version 1.0 — 2025-04-08**
- Initial design system
- Established from existing chat UI patterns
- Query rewriting transparency UX defined
- Accessibility baseline: WCAG 2.1 AA

---

## Future Considerations

### Planned Additions (Phase 4+)

- **Notebook summary UI** (Feature 4.1)
- **Key topics as tags/chips** (Feature 4.2)
- **Generated assets viewer** (FAQ, study guides, timelines)
- **Source overlap visualization** (Venn diagram, network graph)

### Deferred

- **Dark mode** — Evaluate demand before implementing
- **Custom themes** — Low priority, neutral grays work for most use cases
- **Advanced animations** — Keep motion subtle; avoid over-engineering

---

## Design Review Process

Before implementing new UI:

1. **Check DESIGN.md first** — Does this fit existing patterns?
2. **Reuse components** — shadcn/ui has most building blocks
3. **Sketch states** — Empty, loading, error, success — not just happy path
4. **Test accessibility** — Keyboard nav, screen reader, contrast
5. **Get review** — Run `/plan-design-review` before implementing

---

**Ownership:** This design system is maintained by the NotebookLX team. Proposed changes should be reviewed via `/plan-design-review` before implementation.

**Questions?** Refer to CLAUDE.md for project context, or run `/design-consultation` to establish new patterns.
