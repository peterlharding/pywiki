# PyWiki — Feature Backlog

Items are grouped by theme and loosely prioritised within each group.
Update status with: `[ ]` pending · `[~]` in progress · `[x]` done

---

## Markup & Rendering

- [ ] **Wikitext → Markdown/RST conversion tool** — one-shot converter to migrate
      existing wikitext pages to Markdown or RST; expose as an admin API endpoint
      and a UI button on the edit page.
- [ ] **Wikitext: tables** — `{| ... |}` MediaWiki table syntax rendered to `<table>`.
- [ ] **Wikitext: `<ref>` / `<references />`** — inline footnote/citation support.
- [ ] **Wikitext: `<code>` and `<pre>` blocks** — verbatim / syntax-highlighted blocks.
- [ ] **Syntax highlighting** — integrate Pygments or highlight.js for fenced code
      blocks in Markdown and `<pre>` blocks in wikitext/RST.
- [ ] **Math rendering** — LaTeX via MathJax or KaTeX for `$...$` / `$$...$$`
      (Markdown) and `:math:` role (RST).
- [ ] **Wikitext: image embedding** — `[[File:name.png|thumb|Caption]]` syntax.
- [ ] **Live preview debounce** — reduce preview API calls; currently fires on every
      keystroke.

---

## Page Management

- [ ] **Wikitext-to-Markdown migration** — admin batch job to convert all wikitext
      pages in a namespace to Markdown.
- [ ] **Page move / redirect** — when a page is renamed, leave a redirect stub at
      the old slug so existing links continue to resolve.
- [ ] **Page locking** — allow admins to mark a page as read-only.
- [ ] **Page protection levels** — per-page edit permission: any user / logged-in /
      admin only.
- [ ] **Soft delete / undelete** — mark pages as deleted rather than hard-removing
      them; admin UI to restore.
- [ ] **Namespace default format** — honour `Namespace.default_format` when pre-
      filling the format selector on the Create Page form.
- [ ] **Bulk import** — accept a ZIP of `.md` / `.rst` / `.wiki` files and create
      pages from them.

---

## Search

- [x] **Category pages** — `[[Category:Name]]` tags on any page (all three formats)
      create a auto-generated `/category/{name}` page listing all tagged pages
      alphabetically, with namespace and last-edited date. Category links appear
      in a footer bar on every page that declares them.
- [ ] **Full-text search index** — replace `ILIKE` with PostgreSQL `tsvector` / FTS5
      for SQLite when running in production.
- [ ] **Search by category** — `Category:Foo` query syntax.
- [ ] **Search filters** — filter results by author, date range, format.
- [ ] **Search result ranking** — score by title match > snippet match > recency.

---

## Authentication & Users

- [ ] **OAuth / SSO login** — GitHub, Google, or generic OIDC provider.
- [ ] **Email verification** — send verification link on registration.
- [ ] **Password reset** — forgot-password flow via email.
- [ ] **User profile page** — display name, avatar, contribution history.
- [ ] **Per-namespace permissions** — grant read/write access per user or group.
- [ ] **API tokens** — long-lived personal access tokens for scripting/bots.

---

## Attachments

- [ ] **Image gallery on page** — display inline thumbnails of attached images.
- [ ] **Attachment versioning** — keep old file versions on re-upload rather than
      overwriting.
- [ ] **S3 / object-storage backend** — configurable storage driver so attachments
      can be stored in S3-compatible stores instead of local filesystem.
- [ ] **Virus scan hook** — pluggable pre-upload scanner.

---

## UI / UX

- [ ] **Dark mode** — CSS media-query-aware theme toggle.
- [ ] **Table of contents** — auto-generate TOC from headings (all three formats).
- [ ] **Breadcrumb navigation** — namespace → page → section.
- [ ] **Recent changes RSS/Atom feed** — `/recent.xml`.
- [ ] **Watch page** — users can watch pages and receive notifications on change.
- [ ] **Diff improvements** — side-by-side diff view in addition to unified diff.
- [ ] **Mobile-responsive editor** — improve the textarea editor on narrow screens.
- [ ] **WYSIWYG editor option** — optional rich-text editor (e.g. ProseMirror) that
      serialises back to Markdown.

---

## API & Integrations

- [ ] **OpenAPI docs polish** — add response examples and tag descriptions.
- [ ] **Webhooks** — fire a configurable HTTP POST on page create/update/delete.
- [ ] **Bot API** — rate-limited write endpoints with bot-flagged edits.
- [ ] **Export** — download a namespace as a ZIP of raw source files or HTML.

---

## Operations & Quality

- [ ] **Alembic migrations** — replace `create_all` startup with proper versioned
      migrations; add initial migration for current schema.
- [ ] **PostgreSQL support** — test and document running against PostgreSQL in
      production (async driver: `asyncpg`).
- [ ] **Caching layer** — Redis-backed cache for rendered HTML (invalidate on
      page update).
- [ ] **Rate limiting** — per-IP and per-user request throttling via a middleware.
- [ ] **Structured logging** — replace print/uvicorn default logging with structlog.
- [ ] **Health check endpoint improvements** — include DB connectivity and version
      info in `/api/health`.
- [ ] **Docker / docker-compose** — add `Dockerfile` and `docker-compose.yml` for
      one-command local development.
- [ ] **CI pipeline** — GitHub Actions workflow: lint → type-check → test.
- [ ] **Type annotations** — run `mypy` in strict mode; fix remaining gaps.
- [ ] **Test coverage** — target ≥ 80 % line coverage; add attachment and UI route
      tests.
