# AGENTS.md

This repository contains a Django 6 project.

Purpose
-------
This project implements a platform for listing real-world (free book exchange) toy libraries. It includes the locations and inventory of the libraries, as well
as user management and features for tracking books and bookmarks across different libraries.

Tech stack
----------
- Python 3.x
- Django 6
- SQLite (development)
- GitHub Codespaces used for development

Project structure
-----------------

share_books/
    settings.py       → Django project configuration
    urls.py           → root URL routing
    asgi.py
    wsgi.py

manage.py
.gitignore

Apps live at the repository root:

users/
    models.py         → user models / authentication
    admin.py
    apps.py
    views.py
    urls.py
    tests.py

book_exchange/
    models.py         → toy library models
    admin.py
    apps.py
    views.py
    urls.py
    tests.py
    templates/

Common Django commands
----------------------

Start dev server:

    python manage.py runserver

Create migrations:

    python manage.py makemigrations

Apply migrations:

    python manage.py migrate

Create admin user:

    python manage.py createsuperuser

General development rules
-------------------------

Follow normal Django conventions.

Prefer:
- class-based views for complex views
- function views for simple endpoints
- Django ORM (avoid raw SQL)

Avoid:
- editing migration files manually
- modifying Django internal apps
- committing secrets

When adding models
------------------

1. Add model to `models.py`
2. Run:

       python manage.py makemigrations
       python manage.py migrate

3. Register model in `admin.py` if appropriate.

URLs
----

Each app should define its own `urls.py`.

The project `urls.py` should include app URLs using:

    path("appname/", include("appname.urls"))

Templates
---------

Templates should live in:

    app/templates/app/

Example:

    book_exchange/templates/book_exchange/book_exchange_detail.html

Testing
-------

Tests should be added in:

    app/tests.py

Git workflow
------------

Typical development loop:

    git add .
    git commit -m "describe change"
    git push

Important notes for agents
--------------------------

- Do not modify `settings.py` unless necessary.
- Do not delete migrations.
- Keep changes minimal and localized to relevant apps.
- Prefer editing existing files rather than creating new top-level modules.

Python dependencies
-------------------

Dependencies are managed with `requirements.txt`.

The development environment (including GitHub Codespaces) installs
dependencies using:

    pip install -r requirements.txt

Therefore:

- Whenever adding a Python package, update `requirements.txt`.
- Whenever upgrading a package, update `requirements.txt`.
- Do not install packages without updating this file.

Preferred workflow when adding a dependency:

    pip install <package>
    pip freeze | grep <package> >> requirements.txt

If multiple dependencies change, regenerate the file:

    pip freeze > requirements.txt

Important:
- Django version must remain pinned unless intentionally upgraded.
- Avoid unnecessary dependencies.

Environment assumptions
-----------------------

The project runs in GitHub Codespaces using the devcontainer configuration.

Environment setup automatically runs:

    pip install -r requirements.txt

Do not introduce other dependency managers (poetry, pipenv, etc.)
without updating the devcontainer configuration.