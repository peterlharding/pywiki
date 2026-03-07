# Colouring Text in PyWiki

PyWiki supports coloured text in all three markup formats via inline HTML.
CSS utility classes are provided in `wiki.css` for convenience, and all colours
adapt automatically to dark mode.

---

## Using CSS utility classes (recommended)

Wrap text in a `<span>` with a `.text-*` class. Works in Markdown, Wikitext,
and RST (via `.. raw:: html`).

| Class | Light colour | Dark colour |
|---|---|---|
| `.text-red` | `#cc3333` | `#f38ba8` |
| `.text-green` | `#228822` | `#a6e3a1` |
| `.text-blue` | `#3366cc` | `#89b4fa` |
| `.text-orange` | `#e65100` | `#fab387` |
| `.text-purple` | `#6a1a9a` | `#cba6f7` |
| `.text-teal` | `#00796b` | `#94e2d5` |
| `.text-grey` | `#72777d` | *(same)* |
| `.text-gold` | `#b8860b` | `#f9e2af` |
| `.text-muted` | CSS var `--muted` | adapts |
| `.text-accent` | CSS var `--accent` | adapts |
| `.text-danger` | CSS var `--danger` | adapts |
| `.text-success` | CSS var `--success` | adapts |
| `.text-warn` | CSS var `--warn` | adapts |

---

## Markdown

```markdown
<span class="text-red">This text is red.</span>

<span class="text-blue">This text is blue.</span>

<h2 class="text-green">Green heading</h2>

<p class="text-orange">An orange paragraph.</p>
```

Arbitrary inline styles also work:

```markdown
<span style="color: hotpink;">Custom colour</span>
```

---

## Wikitext

```wikitext
<span class="text-purple">Purple text in wikitext.</span>

<span style="color: darkorange;">Inline style.</span>
```

---

## RST

RST has no native colour directive. Use a raw HTML block:

```rst
.. raw:: html

   <p class="text-teal">Teal paragraph via RST.</p>

.. raw:: html

   <span class="text-red">Red inline text.</span> Normal text continues here.
```

---

## Notes

- All `.text-*` classes automatically switch to dark-mode-appropriate shades
  when `[data-theme="dark"]` is set or the OS `prefers-color-scheme: dark`
  media query fires.
- The theme-aware variable classes (`.text-accent`, `.text-danger`, etc.)
  are the most robust choice for content that should always look correct.
- Avoid hardcoding colours in `style=""` attributes for content that needs
  to work in both light and dark mode.
