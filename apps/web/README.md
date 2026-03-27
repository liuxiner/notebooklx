# NotebookLX Web Application

Next.js frontend for NotebookLX - a source-grounded notebook knowledge workspace.

## Setup

### 1. Install Dependencies

```bash
pnpm install
```

### 2. Environment Variables

Create a `.env.local` file:

```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### 3. Run Development Server

```bash
pnpm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

## Features Implemented

### ✅ Feature 1.2: Notebook UI (Frontend)

All acceptance criteria met:
- ✅ Notebook list page shows all user notebooks
- ✅ Create notebook button opens modal/form
- ✅ Can create notebook with name (required) and description (optional)
- ✅ Notebook cards show name, description preview, and created date
- ✅ Click notebook card navigates to notebook detail page
- ✅ Edit/delete actions available on notebook cards
- ✅ Loading states while fetching notebooks
- ✅ Empty state when no notebooks exist
- ✅ Responsive design works on mobile and desktop

## Project Structure

```
apps/web/
├── app/                      # Next.js App Router
│   ├── notebooks/            # Notebooks pages
│   │   ├── [id]/             # Dynamic notebook detail page
│   │   │   └── page.tsx
│   │   └── page.tsx          # Notebooks list page
│   ├── layout.tsx            # Root layout
│   ├── page.tsx              # Home page (redirects to /notebooks)
│   └── globals.css           # Global styles
├── components/               # React components
│   ├── notebooks/            # Notebook-specific components
│   │   ├── delete-dialog.tsx
│   │   ├── empty-state.tsx
│   │   ├── notebook-card.tsx
│   │   └── notebook-form-dialog.tsx
│   └── ui/                   # Reusable UI components
│       ├── button.tsx
│       ├── card.tsx
│       ├── dialog.tsx
│       ├── input.tsx
│       ├── label.tsx
│       ├── spinner.tsx
│       └── textarea.tsx
├── lib/                      # Utility functions
│   ├── api.ts                # API client for backend
│   ├── toast.tsx             # Toast notification system
│   └── utils.ts              # Utility functions (cn)
└── package.json
```

## Available Scripts

- `pnpm run dev` - Start development server
- `pnpm run build` - Build for production
- `pnpm start` - Start production server
- `pnpm run lint` - Run ESLint

## Technology Stack

- **Next.js 14** - React framework with App Router
- **React 18** - UI library
- **TypeScript** - Type safety
- **Tailwind CSS** - Utility-first CSS
- **Radix UI** - Headless UI components
- **Lucide React** - Icon library

## API Integration

The frontend communicates with the FastAPI backend via the API client (`lib/api.ts`).

Endpoints used:
- `GET /api/notebooks` - List all notebooks
- `POST /api/notebooks` - Create notebook
- `GET /api/notebooks/{id}` - Get single notebook
- `PATCH /api/notebooks/{id}` - Update notebook
- `DELETE /api/notebooks/{id}` - Delete notebook

## Design System

The UI follows a consistent design system using CSS variables:
- Color themes (light/dark mode ready)
- Typography scale
- Spacing system
- Component variants (primary, secondary, destructive, ghost, outline)

All colors are defined in `app/globals.css` using HSL values for easy theming.

## Responsive Design

The application is fully responsive:
- **Mobile**: Single column grid, touch-friendly buttons
- **Tablet**: 2-column grid
- **Desktop**: 3-column grid, hover states

## Accessibility

- Semantic HTML
- ARIA labels for screen readers
- Keyboard navigation support
- Focus visible states
- Color contrast compliance

## Next Steps

- [ ] Implement notebook detail page
- [ ] Add source upload UI
- [ ] Add chat interface
- [ ] Add search functionality
- [ ] Add dark mode toggle
