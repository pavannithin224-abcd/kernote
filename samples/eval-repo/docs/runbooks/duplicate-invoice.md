# Runbook: A customer was invoiced twice

## Cause

Almost always a manual replay of the invoice stream. See
`docs/runbooks/redis-down.md`.

## Fix

1. Find both invoices: `SELECT * FROM invoices WHERE order_id = :id`.
2. Void the later one with `python -m lanternfish.billing.void <invoice_id>`.
   Never delete an invoice row; the tax export reads voided rows too.
3. Notify the customer from the template in the billing shared drive.
