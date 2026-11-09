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
| Recall@1 | 0.560 | 0.560 |
| Recall@5 | 0.600 | 0.700 |
| Recall@10 | 0.600 | 0.700 |
| MRR | 0.568 | 0.611 |
| nDCG@10 | 0.592 | 0.663 |
| Citation correctness | 41.9% | 51.1% |
| Citation correctness (strict) | 33.7% | 40.4% |
| Useful abstention | 66.7% | 66.7% |
| False abstention | 20.0% | 24.0% |
| Retrieved an answering doc | 60.0% | 72.0% |
| ...and asserted it | 48.0% | 48.0% |

Semantic indexing of this corpus took 4.6s on the development machine with `sentence-transformers/all-MiniLM-L6-v2` already cached.

### Verdicts

| Verdict | Keyword | Hybrid | Meaning |
|---|---|---|---|
| `answered` | 12 | 12 | retrieved a document that answers it **and** asserted it |
| `lead_only` | 3 | 6 | retrieved it, then declined to call it an answer |
| `missed` | 10 | 7 | never retrieved it — the only unambiguous retrieval failure |
| `correctly_declined` | 4 | 4 | unanswerable, and it declined |
| `wrongly_asserted` | 2 | 2 | unanswerable, and it asserted an answer anyway |

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
| q10 | What are the possible order statuses? | evidence_found | **no** | `ARCHITECTURE.md` |
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
| q22 | Who manages the on-call rota? | weak_evidence | yes | `README.md` |
| q23 | What is the retention period for customer personal data? | weak_evidence | yes | `docs/glossary.md` |
| q24 | What is the password policy for operator accounts? | weak_evidence | yes | `CONTRIBUTING.md` |
| q25 | How do I add a new display language to the operator console? | evidence_found | **no** | `docs/adr/0003-no-graphql.md` |
| q26 | What is the monthly cost of the managed Redis instance? | evidence_found | **no** | `docs/adr/0001-postgresql.md` |
| q27 | Which data store holds the records? | evidence_found | **no** | `docs/adr/0005-timezones.md` |
| q28 | Once a parcel is on its way to the customer, can it still be stopped? | weak_evidence | **no** | `docs/runbooks/redis-down.md` |
| q29 | Where does the team write down why it picked one approach over another? | weak_evidence | **no** | `ARCHITECTURE.md` |
| q30 | What stops two couriers from being promised the same slot? | weak_evidence | **no** | `CONTRIBUTING.md` |
| q31 | How does the money owed get worked out including what the taxman takes? | weak_evidence | **no** | `docs/runbooks/duplicate-invoice.md` |

## Failures (missed or wrongly asserted)

- **q02** (answerable, evidence_found) — How do I install the project dependencies? Retrieved `docs/legacy-setup.md` instead.
- **q03** (answerable, evidence_found) — Which database does this project use and why was it chosen? Retrieved `CONTRIBUTING.md` instead. Label note: CHANGELOG.md mentions PostgreSQL three times and answers nothing. It is the distractor this question exists to catch.
- **q04** (answerable, weak_evidence) — Why was MongoDB removed from the stack? Retrieved `docs/adr/0006-deprecated-mongo.md` instead.
- **q06** (answerable, evidence_found) — How are operator login sessions stored? Retrieved `docs/runbooks/redis-down.md` instead.
- **q07** (answerable, weak_evidence) — Why did the team decide against GraphQL? Retrieved `docs/adr/0003-no-graphql.md` instead.
- **q09** (answerable, evidence_found) — Which module is allowed to convert time zones? Retrieved `docs/adr/0005-timezones.md` instead.
- **q10** (answerable, evidence_found) — What are the possible order statuses? Retrieved `ARCHITECTURE.md` instead.
- **q11** (answerable, evidence_found) — Can an order be cancelled after it has shipped? Retrieved `ARCHITECTURE.md` instead.
- **q25** (unanswerable, evidence_found) — How do I add a new display language to the operator console? Retrieved `docs/adr/0003-no-graphql.md` instead.
- **q26** (unanswerable, evidence_found) — What is the monthly cost of the managed Redis instance? Retrieved `docs/adr/0001-postgresql.md` instead. Label note: ADR-0002 says Redis is operated and ADR-0001 mentions 'operational cost is a managed instance'. Close enough to be tempting, nowhere near an answer.
- **q27** (answerable, evidence_found) — Which data store holds the records? Retrieved `docs/adr/0005-timezones.md` instead. Label note: Paraphrase: the corpus says 'database' and 'PostgreSQL', never 'data store' or 'holds the records'.
- **q28** (answerable, weak_evidence) — Once a parcel is on its way to the customer, can it still be stopped? Retrieved `docs/runbooks/redis-down.md` instead. Label note: Paraphrase of 'can a shipped order be cancelled'. Avoids 'shipped' and 'cancelled' entirely.
- **q29** (answerable, weak_evidence) — Where does the team write down why it picked one approach over another? Retrieved `ARCHITECTURE.md` instead. Label note: Paraphrase: both files point at docs/adr/. The corpus word is 'architecture decision records'.
- **q30** (answerable, weak_evidence) — What stops two couriers from being promised the same slot? Retrieved `CONTRIBUTING.md` instead. Label note: Paraphrase: the corpus says 'exclusion constraints' and 'overlapping delivery windows'.
- **q31** (answerable, weak_evidence) — How does the money owed get worked out including what the taxman takes? Retrieved `docs/runbooks/duplicate-invoice.md` instead. Label note: Deliberately colloquial paraphrase of invoice totals and tax.
