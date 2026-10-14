# Repeatable local promotion

Each new promotion owns a separate persistent business database, `urls_<run-id>`.
Greenfield creates an empty database, avoiding Flyway checksum conflicts with an
existing demonstration. Brownfield copies the last promoted greenfield database;
ambiguous enhancements copy the currently promoted database. The previous database
is retained, preserving its links and schema for rollback. A new greenfield run
intentionally starts a new link collection.

The orchestrator stops only its named local demo containers before cloning a
template. It never terminates arbitrary database connections. If another process
holds the template open, promotion fails safely. Database creation is atomic and
its validated name is reconciled before retry. Source/jar validation and release
approval remain mandatory before this operation. The promotion receipt records
the chosen database; startup reads it, so a restart retains the promoted data.

Live brownfield execution requires a newly promoted greenfield source/database
pair in this installation. Saved brownfield evidence is readable immediately.
Archived live runs predating this improvement used the original `urls` database;
they are not retrospectively represented as using database copies.

The URL role remains restricted to business data and cannot connect to engineering
state. Database names and migration defaults are local configuration, not model
provider credentials. A full documented reset removes this installation's database
volume; saved JSON evidence stays in the repository.
