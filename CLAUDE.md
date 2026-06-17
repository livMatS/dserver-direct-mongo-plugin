# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A plugin for [dservercore](https://github.com/livMatS/dservercore) (the dtool lookup server). It exposes two HTTP routes that let clients submit **raw MongoDB queries and aggregation pipelines** directly against the metadata collection, rather than only the structured search the core offers. It is registered with the host server via the `dservercore.extension` entry point declared in `pyproject.toml`.

## Commands

```bash
# Install for development (pulls in dservercore + sibling mongo plugins)
pip install -e .[test]

# Run all tests (requires a running MongoDB on localhost:27017)
pytest -sv

# Run a single test file / single test
pytest -sv tests/test_mongo_routes.py
pytest -sv tests/test_mongo_routes.py::test_mongo_query_route

# Lint (same checks as CI; syntax/undefined-name errors are build-breaking)
flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
flake8 . --count --exit-zero --max-complexity=10 --max-line-length=127 --statistics
```

Tests require an actual MongoDB instance — each test fixture creates and drops a randomly named database on `mongodb://localhost:27017/`. The CI matrix (`.github/workflows/test.yml`) also installs `dservercore`, `dserver-search-plugin-mongo`, and `dserver-retrieve-plugin-mongo` from their `main` branches; do the same locally if pip cannot resolve them from PyPI.

The build backend is `flit_scm`. Versioning is automatic via `setuptools_scm` from git tags, written to `dserver_direct_mongo_plugin/version.py` at build time (do not edit that file; it is gitignored).

## Architecture

The plugin is a single `ExtensionABC` subclass plus three small modules.

- **`__init__.py`** — defines the `mongo_bp` Flask-smorest Blueprint (`/mongo/query`, `/mongo/aggregate`) and the `DirectMongoExtension` class. The host server calls `init_app()` (wiring the Mongo client), `get_blueprint()`, `get_config()`, and `register_dataset()`.
- **`config.py`** — `Config` reads `DSERVER_MONGO_URI` / `DSERVER_MONGO_DB` / `DSERVER_MONGO_COLLECTION` and the two feature toggles `DSERVER_ALLOW_DIRECT_QUERY` / `DSERVER_ALLOW_DIRECT_AGGREGATION` from the environment.
- **`utils.py`** — the query-construction logic; converts the structured query dict and the embedded raw mongo into a final mongo query / aggregation pipeline, plus `_register_dataset_descriptive_metadata` which parses the README YAML and upserts the dataset document.
- **`schemas.py`** — `QueryDatasetSchema` (marshmallow); request bodies are validated against it with `partial=True`.

### The security model (most important thing to understand)

Routes are JWT-protected (`@jwt_required()`). Access control is **not** done at the Mongo level — it is enforced by injecting the user's permitted base URIs into the query:

1. `server_utils.preprocess_query_base_uris(username, query)` replaces `query["base_uris"]` with only the base URIs the user may read. An empty result → return `[]` (user sees nothing).
2. `_dict_to_mongo` builds the structured part of the query from the whitelisted keys in `VALID_MONGO_QUERY_KEYS` (anything else is stripped by `_sanitise`).
3. `_dict_to_mongo_query` wraps the user's raw `query` dict in an `$and` together with the permission-derived clauses — so **direct queries still respect per-user access**.
4. `_dict_to_mongo_aggregation` only prepends a `$match` permission stage; **subsequent aggregation pipeline stages can bypass it** and even write to the DB. This is why `ALLOW_DIRECT_AGGREGATION` defaults to `False` and must not be enabled in production. When editing aggregation handling, preserve this invariant and the warning in `config.py`.

Both `ALLOW_DIRECT_*` flags are checked redundantly (in the route via `abort(404)` and again in the `*_by_user` helper); keep both checks when modifying.

### Class-level Mongo handle

`DirectMongoExtension.client/db/collection` are **class variables**, deliberately, so the module-level route functions can reach the collection configured inside `init_app()`. This is an intentional workaround for the plugin lifecycle (see the NOTE comment in `__init__.py`) — don't "fix" it into instance state without understanding the route access pattern.

### Result serialization

Mongo `datetime` values for `created_at`/`frozen_at` are converted to float timestamps via `dtoolcore.utils.timestamp` before JSON serialization. For queries, `readme`/`manifest`/`annotations`/`_id` are projected out; for aggregations the pipeline author is responsible for projecting fields (only `_id` is always `$unset`).

## Testing notes

Test fixtures live in `tests/conftest.py`: `tmp_app_with_users` / `tmp_app_with_data` build a `dservercore` app on an in-memory SQLite DB + temp Mongo DB, registering users (`snow-white` admin, `grumpy`, `sleepy`) and permissions. `tmp_app_with_data_and_relaxed_security` flips both `ALLOW_DIRECT_*` flags on for aggregation tests. JWTs are validated with the fixed `JWT_PUBLIC_KEY` in `conftest.py`; the corresponding signed tokens (`grumpy_token`, etc.) come from `tests/__init__.py`.
