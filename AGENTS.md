## Project Wiki

This project keeps durable knowledge in `.llm-wiki/` (an Obsidian-compatible LLM
wiki). Treat it as the source of truth for decisions, architecture, and hard-won
findings.

- At task start, read relevant pages under `.llm-wiki/wiki/`.
- At task end, record durable decisions and findings as pages under
  `.llm-wiki/wiki/`: one page per thing, kebab-case filenames, cross-link with
  `[[folder/page]]`, and cite sources.
- Never edit `.llm-wiki/raw/**` (immutable captures) or `.llm-wiki/meta/**`
  (generated index). `meta/` is gitignored and rebuilt locally.
- With the `@zosmaai/pi-llm-wiki` extension, prefer its tools (`wiki_recall`,
  `wiki_retro`, `wiki_ensure_page`); they maintain `meta/` automatically.
  Without it, edit the markdown directly and leave `meta/` alone.
