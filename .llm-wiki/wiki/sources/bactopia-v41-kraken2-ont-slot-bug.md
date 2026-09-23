---
type: source
title: Bactopia v4.1 Kraken2 ONT slot bug
status: insight
category: devops
created: 2026-09-16
updated: 2026-09-16
slug: bactopia-v41-kraken2-ont-slot-bug
---

# Bactopia v4.1 Kraken2 ONT slot bug

The v4.1 Kraken2 tool found the completed sample output through an EFS-local `--bactopia` path, but `KRAKEN2:KRAKEN2_MODULE` generated a command ending in `--paired null null` and failed with `FileNotFoundError: null`. The v4 input plugin correctly identifies ONT reads as `lr` from `<sample>/main/qc/<sample>_ONT.fastq.gz` and `main/assembler/supplemental/ont.txt`, but `modules/kraken2/main.nf` only considers `se`, `r1`, and `r2` when setting `meta.single_end` and `read_inputs`; it ignores `lr`. V3.2 treated ONT reads as its single-end input and succeeded. This is a concrete v4.1 Kraken2 ONT compatibility bug/limitation. A proper fix should make `lr` a valid single-read input, or the team can use a validated temporary input-shape workaround while evaluating Bactopia 4.1.

*Category: devops*

---
*Captured: 2026-09-16*

## Related

_Add links to related pages._
