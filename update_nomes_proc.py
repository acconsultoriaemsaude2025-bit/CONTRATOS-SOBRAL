"""Atualiza nome_proc nos registros onde o nome é igual ao código."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app import app, db
from models import ProducaoSIA
from scraper.siasus import _PROC_NOMES_FALLBACK

with app.app_context():
    atualizados = 0
    for cod, nome in _PROC_NOMES_FALLBACK.items():
        n = ProducaoSIA.query.filter(
            ProducaoSIA.proc_id == cod,
            db.or_(
                ProducaoSIA.nome_proc == cod,
                ProducaoSIA.nome_proc == None,
                ProducaoSIA.nome_proc == "",
            )
        ).update({"nome_proc": nome}, synchronize_session=False)
        if n:
            print(f"  {cod}: {n} registros → {nome[:50]}")
            atualizados += n
    db.session.commit()
    print(f"\nTotal atualizado: {atualizados} registros")
