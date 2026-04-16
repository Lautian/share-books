Before committing code changes for an issue, run these CI-quality checks from the repository root:

1. `python -m compileall .` (simple Python syntax/bytecode compilation check)
2. `python manage.py check`
3. `python manage.py makemigrations --check --dry-run`
4. `python manage.py test`

Only commit after all checks pass.
