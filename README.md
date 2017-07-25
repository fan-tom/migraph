Migraph creates graph of migrations in django project

How to run:

```python main.py "/path/to/django/project"```

It requires escaping of backslashes on Windows

As a result script produces dot file called "migrations" and renders it to png

Migrations are named according to their file names and grouped by application name

Script searches migration files using glob ```"/path/to/django/project/**/migrations/*.py"```

Requirements: graphviz python package and installed graphviz binaries