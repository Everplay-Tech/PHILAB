# Phi-2 Atlas manual schema migrations

The Atlas database typically uses SQLite via SQLAlchemy. To add the newly required
columns to an existing database without rebuilding from scratch, run the
following SQL statements against your Atlas database (adjust the path if your
`atlas.path` configuration points elsewhere):

```bash
sqlite3 ./phi2_lab/atlas/data/atlas_db.sqlite <<'SQL'
ALTER TABLE head_info ADD COLUMN importance JSON DEFAULT '{}';
ALTER TABLE head_info ADD COLUMN behaviors JSON DEFAULT '[]';
ALTER TABLE experiment_record ADD COLUMN result_path VARCHAR(512) DEFAULT '';
ALTER TABLE experiment_record ADD COLUMN key_findings TEXT DEFAULT '';
ALTER TABLE experiment_record ADD COLUMN tags JSON DEFAULT '[]';
ALTER TABLE semantic_code ADD COLUMN payload_ref VARCHAR(256) DEFAULT '';
ALTER TABLE semantic_code ADD COLUMN tags JSON DEFAULT '[]';
SQL
```

After the columns are added, SQLAlchemy will automatically start reading and
writing the extended records. If you maintain the Atlas data in another
RDBMS, run the equivalent `ALTER TABLE ... ADD COLUMN` statements above using
that backend's syntax.

If you do not have any important state in your Atlas yet, you can instead drop
and rebuild the database using the usual ingestion or snapshot tooling, and the
new schema will be created automatically.
