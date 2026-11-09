# Evaluation

Measured, not asserted. Regenerate with the **Run evaluation** button on the
Settings & Evaluation screen, or `POST /api/v1/evaluation/run`.

Corpus `../samples/eval-repo` — 51 memories from 30 fixture paths. 31 labelled questions: 25 answerable, 6 unanswerable.

## What these numbers are

The Day-25 acceptance criteria ask for **citation correctness** and
**useful-abstention rate**, not answer fluency, so those lead. Kernote
returns extracted evidence rather than composed prose; there is no
generated answer to score for fluency, deliberately.

## Results

| Measure | FTS5 keyword only | + MiniLM semantic (RRF) |
|---|---|---|
| Recall@1 | 0.560 | 0.660 |
| Recall@5 | 0.800 | 0.980 |
| Recall@10 | 0.840 | 0.980 |
| MRR | 0.638 | 0.777 |
| nDCG@10 | 0.707 | 0.838 |
| Citation correctness | 43.1% | 54.7% |
| Citation correctness (strict) | 34.3% | 43.4% |
| Useful abstention | 83.3% | 83.3% |
| False abstention | 20.0% | 20.0% |
| Retrieved an answering doc | 84.0% | 100.0% |
| ...and asserted it | 60.0% | 60.0% |
| Of the leads, right doc first | 0.0% | 20.0% |

Semantic indexing of this corpus took 4.7s on the development machine with `sentence-transformers/all-MiniLM-L6-v2` already cached.

### A real repository (proposal item Q2)

Every number above comes from a corpus written for this purpose, which bounds
regressions and says little about real projects. So the harness was pointed at
a sibling research project — 5955 files, mostly generated data, 7 Markdown
documents — with 13 labels verified against the repository before being written
(`eval/questions-ivforge.json`; the corpus itself is not in this repository).

It immediately broke two things the synthetic corpus could not see.

| Measure | Real repo, before | Real repo, after |
|---|---|---|
| Useful abstention | **0.0%** | **100.0%** |
| Wrongly asserted | 4 of 4 | **0** |
| False abstention | 11.1% | 11.1% |
| Answered | 7 | 7 |
| Retrieved an answering document | 88.9% | 88.9% |
| Citation correctness | 57.9% | 57.9% |
| Files ingested | 23 of 2941 | **2941** |
| Files refused as suspected secrets | **2918** | **0** |
| Scan time | 30.6s | **2.0s** |

Retrieval was *better* here than on the fixture — Recall@3 0.889, 88.9%
retrieval success — but the abstention guarantee, measured at 66.7% on the
fixture, was **0 of 4**. Two independent causes, both in ADR-0033 and
ADR-0020c:

* A share threshold can be cleared by **breadth**. "What is the monetary cost
  in dollars of one SPICE simulation run" matched five ordinary words and
  answered confidently, while `monetary` and `dollars` — the words that make it
  unanswerable — appear nowhere. A question is now refused outright when 30% or
  more of what it asks about occurs nowhere in the project.
* The secret scanner refused **2918 of 2938 files**, including three of the
  repository's seven Markdown documents, on `Hex High Entropy String` alone —
  because every hash in a JSON manifest is twenty-plus characters without a
  space. A digest, a UUID, a git object id and an API token are the same shape,
  so a low-precision hit now needs the *key name* to carry the signal.

The fixture's own numbers moved too: useful abstention 66.7% → 83.3%, at a cost
of false abstention 20.0% → 28.0%, with the answered count unchanged at 12. For
this product that is the right direction to trade — a confident wrong answer is
the failure the whole design exists to prevent — but it is a real cost and it is
recorded, not averaged away.

### Verdicts

| Verdict | Keyword | Hybrid | Meaning |
|---|---|---|---|
| `answered` | 15 | 15 | retrieved a document that answers it **and** asserted it |
| `lead_only` | 6 | 10 | retrieved it, then declined to call it an answer |
| `missed` | 4 | 0 | never retrieved it — the only unambiguous retrieval failure |
| `correctly_declined` | 5 | 5 | unanswerable, and it declined |
| `wrongly_asserted` | 1 | 1 | unanswerable, and it asserted an answer anyway |

## Per question (hybrid)

| # | Question | Outcome | Hit | Top source |
|---|---|---|---|---|
| q01 | What port does the API serve on when running locally? | evidence_found | yes | `README.md` |
| q02 | How do I install the project dependencies? | evidence_found | **no** | `docs/legacy-setup.md` |
| q03 | Which database does this project use and why was it chosen? | evidence_found | **no** | `CONTRIBUTING.md` |
| q04 | Why was MongoDB removed from the stack? | weak_evidence | **no** | `docs/adr/0006-deprecated-mongo.md` |
| q05 | Why does the queue use Redis streams instead of Celery? | evidence_found | yes | `docs/adr/0002-redis-queue.md` |
| q06 | How are operator login sessions stored? | evidence_found | **no** | `docs/runbooks/redis-down.md` |
| q07 | Why did the team decide against GraphQL? | weak_evidence | **no** | `docs/adr/0003-no-graphql.md` |
| q08 | In what timezone are timestamps stored? | evidence_found | yes | `docs/adr/0005-timezones.md` |
| q09 | Which module is allowed to convert time zones? | evidence_found | **no** | `docs/adr/0005-timezones.md` |
| q10 | What are the possible order statuses? | weak_evidence | **no** | `ARCHITECTURE.md` |
| q11 | Can an order be cancelled after it has shipped? | evidence_found | **no** | `ARCHITECTURE.md` |
| q12 | How do I deploy a new release? | evidence_found | yes | `docs/runbooks/deploy.md` |
| q13 | How do I roll back a bad deploy? | evidence_found | yes | `docs/runbooks/deploy.md` |
| q14 | What should I do if a customer was invoiced twice? | evidence_found | yes | `docs/runbooks/duplicate-invoice.md` |
| q15 | Is tax applied per invoice line or to the invoice total? | evidence_found | yes | `src/billing/invoice.py` |
| q16 | What is the maximum line length for code? | evidence_found | yes | `CONTRIBUTING.md` |
| q17 | How many approvals does a change to billing need? | evidence_found | yes | `CONTRIBUTING.md` |
| q18 | Can orders still be accepted while Redis is down? | evidence_found | yes | `docs/runbooks/redis-down.md` |
| q19 | Why do orders and billing share a single database? | evidence_found | yes | `ARCHITECTURE.md` |
| q20 | Is order status data cached? | evidence_found | yes | `ARCHITECTURE.md` |
| q21 | What is the contractual delivery SLA for next-day orders? | weak_evidence | yes | `docs/glossary.md` |
| q22 | Who manages the on-call rota? | weak_evidence | yes | `ARCHITECTURE.md` |
| q23 | What is the retention period for customer personal data? | weak_evidence | yes | `docs/glossary.md` |
| q24 | What is the password policy for operator accounts? | weak_evidence | yes | `CHANGELOG.md` |
| q25 | How do I add a new display language to the operator console? | weak_evidence | yes | `docs/adr/0003-no-graphql.md` |
| q26 | What is the monthly cost of the managed Redis instance? | evidence_found | **no** | `docs/adr/0001-postgresql.md` |
| q27 | Which data store holds the records? | evidence_found | **no** | `docs/adr/0005-timezones.md` |
| q28 | Once a parcel is on its way to the customer, can it still be stopped? | weak_evidence | **no** | `docs/glossary.md` |
| q29 | Where does the team write down why it picked one approach over another? | weak_evidence | **no** | `README.md` |
| q30 | What stops two couriers from being promised the same slot? | weak_evidence | **no** | `ARCHITECTURE.md` |
| q31 | How does the money owed get worked out including what the taxman takes? | weak_evidence | **no** | `src/billing/invoice.py` |

## Failures (missed or wrongly asserted)

- **q02** (answerable, evidence_found) — How do I install the project dependencies? Retrieved `docs/legacy-setup.md` instead.
- **q03** (answerable, evidence_found) — Which database does this project use and why was it chosen? Retrieved `CONTRIBUTING.md` instead. Label note: CHANGELOG.md mentions PostgreSQL three times and answers nothing. It is the distractor this question exists to catch.
- **q04** (answerable, weak_evidence) — Why was MongoDB removed from the stack? Retrieved `docs/adr/0006-deprecated-mongo.md` instead.
- **q06** (answerable, evidence_found) — How are operator login sessions stored? Retrieved `docs/runbooks/redis-down.md` instead.
- **q07** (answerable, weak_evidence) — Why did the team decide against GraphQL? Retrieved `docs/adr/0003-no-graphql.md` instead.
- **q09** (answerable, evidence_found) — Which module is allowed to convert time zones? Retrieved `docs/adr/0005-timezones.md` instead.
- **q10** (answerable, weak_evidence) — What are the possible order statuses? Retrieved `ARCHITECTURE.md` instead.
- **q11** (answerable, evidence_found) — Can an order be cancelled after it has shipped? Retrieved `ARCHITECTURE.md` instead.
- **q26** (unanswerable, evidence_found) — What is the monthly cost of the managed Redis instance? Retrieved `docs/adr/0001-postgresql.md` instead. Label note: ADR-0002 says Redis is operated and ADR-0001 mentions 'operational cost is a managed instance'. Close enough to be tempting, nowhere near an answer.
- **q27** (answerable, evidence_found) — Which data store holds the records? Retrieved `docs/adr/0005-timezones.md` instead. Label note: Paraphrase: the corpus says 'database' and 'PostgreSQL', never 'data store' or 'holds the records'.
- **q28** (answerable, weak_evidence) — Once a parcel is on its way to the customer, can it still be stopped? Retrieved `docs/glossary.md` instead. Label note: Paraphrase of 'can a shipped order be cancelled'. Avoids 'shipped' and 'cancelled' entirely.
- **q29** (answerable, weak_evidence) — Where does the team write down why it picked one approach over another? Retrieved `README.md` instead. Label note: Paraphrase: both files point at docs/adr/. The corpus word is 'architecture decision records'.
- **q30** (answerable, weak_evidence) — What stops two couriers from being promised the same slot? Retrieved `ARCHITECTURE.md` instead. Label note: Paraphrase: the corpus says 'exclusion constraints' and 'overlapping delivery windows'.
- **q31** (answerable, weak_evidence) — How does the money owed get worked out including what the taxman takes? Retrieved `src/billing/invoice.py` instead. Label note: Deliberately colloquial paraphrase of invoice totals and tax.
