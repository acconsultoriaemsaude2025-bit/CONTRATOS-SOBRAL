"""
Script para inserir pactuacoes federais Eletivas 2026.
Executar no Railway Console: cd /app && python ../setup_eletivas.py
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app import app, db
from models import PactuacaoFederal

FACO = ("0405050372", "FACOEMULSIFICACAO C/ IMPLANTE DE LENTE INTRA-OCULAR DOBRAVEL", 1543.20)
CAPS = ("0405050020", "CAPSULOTOMIA A YAG LASER", 112.77)

# (municipio, proc_cod, proc_nome, valor_unit, qtd_fisica)
pactuacoes = [
    ("SOBRAL",             FACO[0], FACO[1], FACO[2], 70),
    ("SOBRAL",             CAPS[0], CAPS[1], CAPS[2], 24),
    ("MASSAPE",            FACO[0], FACO[1], FACO[2], 31),
    ("MASSAPE",            CAPS[0], CAPS[1], CAPS[2], 100),
    ("GROAIRAS",           FACO[0], FACO[1], FACO[2], 5),
    ("SANTANA DO ACARAU",  FACO[0], FACO[1], FACO[2], 10),
    ("SANTANA DO ACARAU",  CAPS[0], CAPS[1], CAPS[2], 2),
    ("ALCANTARAS",         FACO[0], FACO[1], FACO[2], 45),
    ("ALCANTARAS",         CAPS[0], CAPS[1], CAPS[2], 21),
    ("FORQUILHA",          FACO[0], FACO[1], FACO[2], 20),
    ("FORQUILHA",          CAPS[0], CAPS[1], CAPS[2], 11),
]

with app.app_context():
    inseridos = 0
    for mun, cod, nome, vunit, qtd in pactuacoes:
        existe = PactuacaoFederal.query.filter_by(
            ano=2026, municipio=mun, proc_cod=cod
        ).first()
        if existe:
            print(f"  ja existe: {mun} / {cod}")
            continue
        p = PactuacaoFederal(
            ano=2026,
            municipio=mun,
            proc_cod=cod,
            proc_nome=nome,
            valor_unit=vunit,
            valor_total=round(vunit * qtd, 2),
            competencia_ini="202507",
            competencia_fim="202512",
            ativo=True,
        )
        db.session.add(p)
        inseridos += 1
        print(f"  inserido: {mun} / {nome[:30]} — qtd {qtd} — R$ {p.valor_total:,.2f}")
    db.session.commit()
    print(f"\nTotal inserido: {inseridos} pactuacoes")
