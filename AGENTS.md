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
- Commit authored `.llm-wiki/wiki/**` changes (including new `wiki_observe` /
  `wiki_retro` source pages) in the same commit as the code they describe, so
  the knowledge lands alongside the change. `meta/`, `raw/`, `outputs/`, and
  `.discoveries/` are gitignored and stay out of commits.
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

## Agent Memory

- Do not commit unless the user explicitly asks. Default workflow: complete the
  work, leave changes unstaged in the working tree, and let the user review
  before any commit. This is the standing pattern unless the user says otherwise
  for a given task.
- `PLAN.md` is a Pantheon/deepwork plan-gate artifact tied to whatever work is
  in flight; keep it uncommitted. Do not add it to this repo's `.gitignore` -
  the ignore rule belongs in the upstream shared repo that feeds this and other
  repos. Leave `PLAN.md` untracked here.
