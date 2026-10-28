import os, sys
sys.path.insert(0, "/app")
os.chdir("/app")
from sqlalchemy import create_engine, text
from tests.conftest import dsn_psycopg
u = os.environ["DATABASE_URL"]
dsn = dsn_psycopg(u)
print("dsn db:", dsn.rsplit("/",1)[-1])
eng = create_engine(dsn)
q = ("SELECT count(*) FROM batches b WHERE b.origin = 'demo' AND b.safety_status = 'pass' "
     "AND NOT EXISTS (SELECT 1 FROM jsonb_array_elements(coalesce(b.temperature_log, '[]'::jsonb)) e "
     "WHERE (e->>'timestamp') ~ '^[0-9]{4}-' AND (e->>'timestamp')::timestamptz > now() - interval '6 hours')")
with eng.begin() as c:
    print("stale pass:", c.execute(text(q)).scalar_one())
    print("total demo:", c.execute(text("select count(*) from batches where origin='demo'")).scalar_one())
