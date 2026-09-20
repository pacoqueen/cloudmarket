# AGENTS.md

## Project
Python 3.13 venv, Django web app ("cloudmarket", wishlist/gift tracker), legacy cookiecutter-django DNA.
Use `bin/python` / `bin/django-admin` / `bin/pytest` from the repo-root venv — a bare `python3` cannot find Django.
Installed Django is 6.1.1; `requirements/*.txt` pins (>=1.11.18, test_plus 1.0.17, …) are stale. Do not bulk-upgrade deps.

## Commands
- Run tests: `bin/python manage.py test`  (manage.py defaults to `config.settings.local`; pytest.ini points at `local` too)
- Single app: `bin/python manage.py test gifts`
- Single test: `bin/python manage.py test gifts.tests.ItemMethodTests` / use `-k <name>` with `manage.py test`
- NOTE: `bin/python -m pytest` is currently broken (installed `pytest-django==3.1.2` still uses removed `pytest.config`); use `manage.py test`.
- Coverage: `coverage run bin/python manage.py test` then `coverage html` (reads .coveragerc)
- Flake8, max-line-length 120 (setup.cfg)

## Settings
- Split settings: `config/settings/{common,local,test,production}.py`, via django-environ; `env.example` lists the vars.
- DB from `DATABASE_URL`; its default in common.py points at a local Postgres on localhost:5432 — tests need that Postgres running (the runner creates a test DB).
- `production.py` is only used in prod; dev/tests always use `local`.

## Architecture
- Two apps: `gifts` (repo root; models Gift/Person/Item, own templates + static) and `cloudmarket.users` (custom user model, `AUTH_USER_MODEL='users.User'`).
- URLs via legacy `re_path` in `config/urls.py` (gifts/, users/, adminpanel/) — fine on Django 6.
- Auth is django-allauth: `LOGIN_URL='account_login'`, `ACCOUNT_EMAIL_VERIFICATION='mandatory'`. Login-gate views with `LoginRequiredMixin` (users app is the reference); use `force_login()` in tests.

## Gotchas
- Legacy `ugettext_lazy` imports only resolve after Django settings are configured — expected, not an error to "fix".
- `.gitignore` currently contains only `*`, so new files won't show in `git status`; stage with `git add -f` or track explicitly.
- WSGI entrypoint is `config.wsgi` (Procfile: `gunicorn config.wsgi:application`).