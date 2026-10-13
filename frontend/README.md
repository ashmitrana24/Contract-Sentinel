# ClauseGuard Review Workbench — Module 9

The ClauseGuard Review Workbench is a contract integrity and legal risk analysis interface built with Next.js 16, TypeScript, Tailwind CSS v4, and Radix UI. 

It is designed strictly as a **review workbench**: it assists human legal and compliance teams by showing what to examine and why. **It never asserts that a contract is legally fraudulent or valid.**

---

## 1. Review Philosophy & Principles

1. **Human-in-the-Loop Review**: The platform flags anomalies, inconsistencies, and structural deviations for human inspection. It does not provide legal advice or replace legal counsel.
2. **Transparent Risk Scoring**: Risk bands (`Low`, `Medium`, `High`) reflect the **recommended depth of human review**, not a fraud verdict:
   - **Low**: No significant structural tampering or internal contradictions detected.
   - **Medium**: Discrepancies detected (e.g. broken cross-references, minor amount variance); review recommended.
   - **High**: Severe anomalies detected (e.g. post-signing edits, invisible text, large figure/words divergence); careful review required.
3. **Data Privacy & Air-Gap Ready**:
   - Zero third-party network requests, tracking scripts, or analytics.
   - Zero external CDN dependencies: `pdf.js` worker is bundled locally.
   - Document PDFs stream inline exclusively from the local ClauseGuard API (`/v1/documents/{id}/file`).
   - Browser storage (`localStorage`) is used solely for the theme preference (`light` or `dark`). No document data is stored locally.

---

## 2. Technology Stack

- **Framework**: Next.js 16 (App Router) with React 19
- **Type Safety**: TypeScript strict mode with OpenAPI client types generated via `openapi-typescript` (`npm run gen:api`)
- **Styling**: Tailwind CSS v4 with semantic CSS variable tokens (Zinc neutrals, Indigo accent, WCAG AA severity colors)
- **UI Primitives**: Radix UI (`@radix-ui/react-tabs`, `@radix-ui/react-accordion`, `@radix-ui/react-dialog`)
- **State & Caching**: TanStack Query v5 with optimistic mutations and background polling
- **PDF Rendering**: `react-pdf` v11 with local `pdfjs-dist@6.3.289` worker bundled at `/pdf.worker.min.mjs`
- **Icons**: Lucide React
- **Testing**: Vitest + React Testing Library (Unit) and Playwright + `@axe-core/playwright` (E2E & Accessibility)

---

## 3. Core Screens & Workflows

### 3.1 Homepage (`/`)
- **File Ingestion Dropzone**: Drag-and-drop or file browser supporting PDF files up to 25 MB with client-side validation and friendly server error mapping.
- **Sample Contract Selector**: 3 built-in synthetic test contracts (`public/samples/`):
  1. `Clean Commercial Contract`: Low risk, zero issues.
  2. `Amount & Date Inconsistency`: Medium risk with figure/words and date conflicts.
  3. `Incremental PDF Tamper`: High risk with post-creation revisions.
- **Recent Documents Table**: Live-polled table displaying filename, size, upload timestamp, job processing status, risk score badge, and severity dots.
- **Document Management**: Kebab menu with cascading deletion confirmation modal (removes PostgreSQL rows and FileStore binary).

### 3.2 Processing Stepper (`/documents/[id]` during job execution)
- Centered status card polling job progress every 1.5 seconds.
- 6-stage vertical stepper:
  1. `Upload`: Ingestion and hash verification.
  2. `Parse`: PyMuPDF layout parsing and clause segmentation.
  3. `Forensics`: PDF byte-level revision, hidden text, and signature inspection.
  4. `Consistency`: Amounts, dates, cross-references, and party verification.
  5. `Clauses`: 45-class legal taxonomy classification and key-term extraction.
  6. `Summary`: Deterministic risk aggregation and highlight locator.
- Helpful error recovery for corrupted or password-protected PDFs.

### 3.3 Contract Report Workbench (`/documents/[id]`)
- **Sticky Header**: Navigation back to document list, filename, upload metadata, page count, and document deletion.
- **Summary Header Card**:
  - SVG animated semicircle score gauge ($0 - 100$).
  - Risk band badge with human-readable description.
  - Plain-English headline and up to 5 prioritized top reasons (click jumps directly to the finding card and PDF highlight).
  - Categorized summary tiles: *Tampering*, *Inconsistencies*, and *Minor notes*.
  - Expandable "Limited analysis" warning banner when coverage warnings exist (`needs_ocr`, low clause count, partial pipeline runs).
- **Split Review Workbench**:
  - Desktop: Resizable 55/45 split view container with drag handle.
  - Mobile (< 1024px): Seamless tabbed switching between "PDF Document" and "Analysis & Tabs".
- **PDF Viewer (Left Pane)**:
  - Continuous vertical page scroll with page index indicator.
  - Zoom controls: Zoom In, Zoom Out, and Fit-Width.
  - Top-left PyMuPDF bounding box coordinate overlays scaled dynamically to rendered canvas dimensions (`renderedWidth / page_width`).
  - Approximate clause-level headings styled with dashed borders.
  - Active finding highlight pulses with subtle animation; clicking a highlight selects its corresponding finding card.
- **Analysis Tabs (Right Pane)**:
  - **Findings Tab**: Filter by category (*All*, *Tampering*, *Inconsistencies*), severity multi-select (*Critical*, *High*, *Medium*, *Low*), and "Hide dismissed" toggle. Cards show severity pill, clause/page tags, plain explanation, evidence code snippet, actionable "What to check", and optimistic feedback toggling ("Confirm issue" / "Not an issue") with undo toasts.
  - **Clauses Tab**: Filterable search box, detected label pills, and document-ordered clause cards with preview and page jump navigation.
  - **Key Terms Tab**: 8 core commercial terms (*Governing law*, *Termination notice*, *Auto-renews*, *Renewal term*, *Non-renewal notice*, *Liability cap*, *Non-compete duration*, *Payment terms*) with source clause links.

---

## 4. Local Development

### 4.1 Prerequisites
- Node.js 20+ and npm 10+
- Running ClauseGuard backend API (port 8000)

### 4.2 Installation & Server
```bash
# Install dependencies
npm install

# Generate TypeScript types from running backend API
npm run gen:api

# Start development server
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

### 4.3 Environment Configuration
Create a `.env.local` file to customize API connection:
```ini
NEXT_PUBLIC_API_URL=http://localhost:8000
```

---

## 5. Testing & Quality Assurance

### 5.1 Unit Tests (Vitest)
Runs component tests, coordinate scaling math, and validation logic:
```bash
npm test
```
*18 tests passed across `components.test.tsx`, `pdf-coordinates.test.ts`, and `upload-validation.test.ts`.*

### 5.2 Linting & Formatting
```bash
npm run lint
```
*ESLint configured with React 19 hooks and TypeScript strict rules (0 errors, 0 warnings).*

### 5.3 End-to-End & Accessibility Tests (Playwright)
Validates real user workflows against the live stack:
```bash
npx playwright test
```
Includes:
- Ingestion and full processing of all 3 synthetic sample contracts.
- Verification of score gauge and finding cards.
- PDF viewer highlight coordinate bounds assertion.
- Feedback toggling and page reload persistence.
- Cascading document deletion.
- Automated WCAG AA accessibility audit via `@axe-core/playwright` across all primary views.

---

## 6. Production Container

The web application is containerized using a multi-stage Docker build:
```dockerfile
# Build image
docker build -t clauseguard-web .

# Run container on port 3000
docker run -p 3000:3000 -e NEXT_PUBLIC_API_URL=http://api:8000 clauseguard-web
```
Or launch as part of the full stack via root `docker compose up`.
