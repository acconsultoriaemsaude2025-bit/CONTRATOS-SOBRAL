import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))
from app import app, db

with app.app_context():
    rows = db.session.execute(
        db.text('SELECT DISTINCT proc_id, nome_proc FROM producao_sia ORDER BY proc_id LIMIT 30')
    ).fetchall()
    for r in rows:
        print(repr(r[0]), '|', r[1])
