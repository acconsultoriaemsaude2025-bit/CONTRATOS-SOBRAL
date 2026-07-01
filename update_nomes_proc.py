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
            ProducaoSIA.nome_proc == cod
        ).update({"nome_proc": nome})
        if n:
            print(f"  {cod}: {n} registros → {nome[:50]}")
            atualizados += n
    db.session.commit()
    print(f"\nTotal atualizado: {atualizados} registros")
