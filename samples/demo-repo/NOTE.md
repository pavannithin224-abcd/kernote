# About this demo repository

`samples/demo-repo` is a tiny fake project used for reproducible
demonstrations and tests, so the walkthrough never depends on private code.

**There is deliberately no `.env` committed here.** Kernote's root
`.gitignore` refuses `.env` files, and committing even a fake credential to
demonstrate secret refusal would be the wrong habit. To see refusal by hand:

```bash
printf 'SECRET_TOKEN=not-a-real-secret\n' > samples/demo-repo/.env
```

Then scan, and the Dashboard will list it under "Why files were not imported"
as *refused as possible secret — never read*.

The automated tests do not rely on that file: `backend/tests/conftest.py`
generates a hostile fixture (fake `.env`, fake private key, binary, oversized
file, CRLF file, gitignored file) in a temporary directory instead.
