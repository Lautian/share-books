# Plan of approach for Issue #51

## Goal
Track version history for `Item` and `BookStation` so edits are auditable, current state is queryable, and prior states can be restored or reviewed.

## Proposed model

### 1) Keep existing models as canonical current state
- `Item` (in `items` app)
- `BookStation` (in `book_stations` app)

These remain the source for normal reads/writes used by the app today.

### 2) Add append-only version models

#### `ItemVersion` (in `items` app)
- `id` (PK)
- `item` (FK → `Item`, indexed)
- `version_number` (positive integer, unique per `item`)
- Snapshot fields needed to reconstruct state at that time:
  - `title`, `author`, `thumbnail_url`, `description`
  - `item_type`, `status`
  - `current_book_station` (nullable FK)
  - `last_seen_at` (nullable FK)
  - `last_activity`
  - moderation fields currently on `Item` (copy as snapshot)
- Metadata:
  - `changed_at` (`DateTimeField(auto_now_add=True)`, indexed)
  - `changed_by` (nullable FK to user)
  - `change_source` (`CREATE|UPDATE|MODERATION|SYSTEM`)
  - `change_reason` (nullable short text)

Constraints/indexes:
- `UniqueConstraint(fields=["item", "version_number"])`
- Index on `("item", "-changed_at")`

#### `BookStationVersion` (in `book_stations` app)
- `id` (PK)
- `book_station` (FK → `BookStation`, indexed)
- `version_number` (positive integer, unique per `book_station`)
- Snapshot fields needed to reconstruct state at that time:
  - `name`, `description`, `location`, `location_plus_code`
  - `address`, `picture`
  - ownership/moderation fields currently on `BookStation` (copy as snapshot)
- Metadata:
  - `changed_at` (`DateTimeField(auto_now_add=True)`, indexed)
  - `changed_by` (nullable FK to user)
  - `change_source` (`CREATE|UPDATE|MODERATION|SYSTEM`)
  - `change_reason` (nullable short text)

Constraints/indexes:
- `UniqueConstraint(fields=["book_station", "version_number"])`
- Index on `("book_station", "-changed_at")`

## Lifecycle rules
1. On create of `Item`/`BookStation`, insert version `1` with `change_source=CREATE`.
2. On each `save()` (create or update) where any tracked snapshot field changes, insert the next version row after the write completes.
   - `Item`: `title`, `author`, `thumbnail_url`, `description`, `item_type`, `status`,
     `current_book_station`, `last_seen_at`, `last_activity`, and moderation/ownership fields.
   - `BookStation`: `name`, `description`, `location`, `location_plus_code`, `address`,
     `picture`, and moderation/ownership fields.
3. Version rows are immutable (append-only).
4. Current row stays denormalized for fast reads; history is in version tables.

## Why this shape
- Minimal disruption to existing URLs, templates, serializers, and foreign keys.
- Fast current-state reads (no "latest version" joins on every page).
- Full audit trail for moderation/history use-cases.
- Supports future rollback by copying a chosen version snapshot back to current row.

## Implementation order
1. Add version models + migrations.
2. Add service/helpers to snapshot models on create/update.
3. Wire creation points (forms, API, moderation flows).
4. Backfill version `1` for existing rows via data migration.
5. Add tests for snapshot creation, version ordering, and migration backfill; run full test suite.
6. Expose history in UI/API where needed.
