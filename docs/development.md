# Plateform AI Development Workflow

## Branches

- `main`: stable and demonstrable checkpoints
- `v2-development`: active V2 integration branch

## Pre-Push Validation

```bash
./scripts/pre-push-security-check.sh
git diff --cached --check
```

Expected result:

```text
PRE-PUSH SECURITY CHECK PASSED
REPOSITORY READY FOR COMMIT
```

## Sensitive Files

Never commit `.env` files, private keys, passwords, API tokens, real Kubernetes Secret manifests, audit exports or local backups.

## Development Workflow

```bash
git checkout v2-development
git add -A
./scripts/pre-push-security-check.sh
git commit -m "..."
git push origin v2-development
```

## Promotion to main

```bash
git checkout main
git pull --ff-only origin main
git merge --no-ff v2-development
git push origin main
```
