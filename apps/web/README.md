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

• Routes / 页面与组件（apps/web/app）

  - /：仅做跳转 → redirect("/notebooks")（apps/web/app/page.tsx）
  - /notebooks：Notebook 列表页（apps/web/app/notebooks/page.tsx）
      - 功能：加载列表、展示数量；新建/编辑/删除 notebook；点击进入详情
      - 关键组件：NotebookCard、EmptyState、NotebookFormDialog、DeleteDialog + Button/Spinner + Toast
  - /notebooks/[id]：Notebook 工作台（apps/web/app/notebooks/[id]/page.tsx）
      - 布局：左侧“Notebook workspace”信息卡 + Sources 工作区；右侧固定 ChatPanel
      - 关键组件：NotebookWorkspace（sources 管理/入库/预览/删除）+ ChatPanel（对话与可解释性面板）
  - /evaluation：Evaluation Dashboard（apps/web/app/evaluation/page.tsx）
      - 功能：按 notebook / 时间范围 / 指标过滤；查看汇总与 runs 表；创建并运行评测；导出 CSV
      - 关键组件：EvaluationFilterControls、MetricsOverview、EvaluationRunsTable、CreateEvaluationDialog

• UI 基建（components/ui + layout）

- 全局：ToastProvider 包裹全站（apps/web/app/layout.tsx）
- 基础 UI：Button/Card/Dialog/Input/Label/Textarea/Spinner/ScrollArea/Checkbox（apps/web/components/ui/*）

核心工作流（Workflow 概括）

- Notebook CRUD：notebooksApi.list/create/update/delete → 列表状态更新 + toast 提示（apps/web/lib/api.ts）
- Sources 管理与入库（NotebookWorkspace）
    - 添加来源：上传 PDF/TXT（支持批量≤50）、粘贴文本、URL（SourceManagementDialog）
    - 入库：对单个 sourcesApi.ingest 或批量 sourcesApi.bulkIngest；用 bulkStatus 轮询（默认 1.5s）直到 ready/failed
    - 预览：source ready 后拉取 getSnapshotSummary 做快照摘要展示
    - 删除：sourcesApi.delete
- Chat（ChatPanel + chat-stream）
    - 提交问题 + top_k → POST /api/notebooks/{id}/chat/stream（SSE）
    - 事件流：status/metrics/query_rewrite/retrieval/citations/answer_delta/answer/done/error；UI 同步展示透明度信息（检索分组、引用卡、指标等）
- Evaluation
    - 过滤条件变化触发 evaluationApi.list(filters)
    - 创建评测：选择 notebook + query + 可选 ground truth chunks（ChunkSelector → evaluationApi.getNotebookChunks）→ create 后自动 start
    - 导出：evaluationApi.exportCsv(filters) 下载 CSV


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
