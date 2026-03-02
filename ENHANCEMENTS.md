# PyWiki — Enhancements for Consideration

Items are grouped by theme and loosely prioritised within each group.
Update status with: `[ ]` pending · `[~]` in progress · `[x]` done


---

## Markup & Rendering

- [ ] **Wikitext → Markdown/RST conversion tool** — one-shot converter to migrate
      existing wikitext pages to Markdown or RST; expose as an admin API endpoint
      and a UI button on the edit page.
- [ ] **Math rendering** — LaTeX via MathJax or KaTeX for `$...$` / `$$...$$` (Markdown) and `:math:` role (RST).
- [ ] **Page history** — view revision history and restore previous versions.
- [ ] **Macro system** - Implement a macro framework that allows users to create custom macros.


---

## Page Management

- [ ] **Wikitext-to-Markdown migration** — admin batch job to convert all wikitext pages in a namespace to Markdown.
- [ ] **Page locking** — allow admins to mark a page as read-only.
- [ ] **Page protection levels** — per-page edit permission: any user / logged-in / admin only.
- [ ] **Soft delete / undelete** — mark pages as deleted rather than hard-removing them; admin UI to restore.


---

## Authentication & Users

- [ ] **Per-namespace permissions** — grant read/write access per user or group.
- [ ] **OAuth / SSO login** — GitHub, Google, or generic OIDC provider.
- [ ] **API tokens** — long-lived personal access tokens for scripting/bots.


---

## Attachments

- [ ] **Attachment versioning** — keep old file versions on re-upload rather than overwriting.
- [ ] **S3 / object-storage backend** — configurable storage driver so attachments
      can be stored in S3-compatible stores instead of local filesystem.
- [ ] **Virus scan hook** — pluggable pre-upload scanner.


---

## UI / UX

- [ ] **Breadcrumb navigation** — namespace → page → section.
- [ ] **WYSIWYG editor option** — optional rich-text editor (e.g. ProseMirror) that serialises back to Markdown.
- [ ] **Dark mode** — CSS media-query-aware theme toggle.
- [ ] **Recent changes RSS/Atom feed** — `/recent.xml`.
- [ ] **Watch page** — users can watch pages and receive notifications on change.
- [ ] **Diff improvements** — side-by-side diff view in addition to unified diff.
- [ ] **Mobile-responsive editor** — improve the textarea editor on narrow screens.


---

## API & Integrations

- [ ] **Search by category** — `Category:Foo` query syntax.
- [ ] **Search filters** — filter results by author, date range, format.
- [ ] **Search result ranking** — score by title match > snippet match > recency.
- [ ] **Webhooks** — fire a configurable HTTP POST on page create/update/delete.
- [ ] **Bot API** — rate-limited write endpoints with bot-flagged edits.
- [ ] **Export** — download a namespace as a ZIP of raw source files or HTML.


---

## Operations & Quality

- [ ] **Structured logging** — replace print/uvicorn default logging with structlog.
- [ ] **Docker / docker-compose** — add `Dockerfile` and `docker-compose.yml` for one-command local development.
- [ ] **Test coverage** — target ≥ 80 % line coverage; add attachment and UI route tests.
- [ ] **Caching layer** — Redis-backed cache for rendered HTML (invalidate on page update).
- [ ] **Rate limiting** — per-IP and per-user request throttling via a middleware.
- [ ] **Health check endpoint improvements** — include DB connectivity and version info in `/api/health`.
- [ ] **CI pipeline** — GitHub Actions workflow: lint → type-check → test.
- [ ] **Type annotations** — run `mypy` in strict mode; fix remaining gaps.
- [ ] **OpenAPI docs polish** — add response examples and tag descriptions.


---
