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

## Deployment Preparation

CAPE Cod deploys live, shared infrastructure. Agents never run `pulumi up` or
any deploy/destroy - the real deploy is the user's step. As a normal part of
preparing (and doing) a deploy together, run `pulumi preview --diff` against the
target stack and evaluate the output before the user deploys:

- Run `pulumi preview --diff -s <stack>` (e.g. `cape-cod-dev`). The `--diff`
  flag expands per-resource property changes so create/update/replace/delete and
  the specific fields are visible, not just a summary count.
- Reconcile every planned action against the changes actually made in the
  branch. Each create/update should trace to a real edit; unexplained churn is a
  stop-and-investigate signal.
- Treat replacements or deletions of shared/stateful resources (buckets,
  databases, queues) as destructive until proven otherwise; understand why
  before the user deploys.
- Only once the diff is understood and matches the intended scope does the user
  run the deploy. See
  `.llm-wiki/wiki/concepts/testing-and-pulumi-preview-workflow.md`.
