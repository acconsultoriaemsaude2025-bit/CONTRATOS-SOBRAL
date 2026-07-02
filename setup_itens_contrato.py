"""Importa itens do Contrato Estado 1199/2025 — C A DE SOUSA REZENDE."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app import app, db
from models import ItemContrato

ITENS = [
    # (forma_org, cod_catalogo, cod_sigtap, descricao, valor_unit, meta_anual_val)
    ("03.01.01 - CONSULTA",             "1990719",  "03.01.01.007-2", "CONSULTA MÉDICA EM ATENÇÃO ESPECIALIZADA",                        102.70,  24648.00),
    ("04.05.01 - PÁLPEBRAS E VIAS LACRIMAIS", "1990729", "04.05.01.001-0", "CORREÇÃO CIRÚRGICA DE ENTRÓPIO E ECTRÓPIO",                 296.37,  0),
    ("04.05.01 - PÁLPEBRAS E VIAS LACRIMAIS", "1990759", "04.05.01.007-9", "EXERESE DE CALÁZIO E OUTRAS PEQUENAS LESÕES DA PÁLPEBRA",  114.55,  0),
    ("04.05.01 - PÁLPEBRAS E VIAS LACRIMAIS", "1990779", "04.05.01.011-7", "RECONSTITUIÇÃO DE CANAL LACRIMAL",                         1003.21, 0),
    ("04.05.01 - PÁLPEBRAS E VIAS LACRIMAIS", "1990789", "04.05.01.014-1", "SIMBLEFAROPLASTIA",                                         296.37,  0),
    ("04.05.01 - PÁLPEBRAS E VIAS LACRIMAIS", "1990799", "04.05.01.016-8", "SONDAGEM DE VIAS LACRIMAIS",                                59.60,   0),
    ("04.05.01 - PÁLPEBRAS E VIAS LACRIMAIS", "1990813", "04.05.01.013-3", "RECONSTITUIÇÃO TOTAL DE PÁLPEBRA",                         1656.34, 0),
    ("04.05.01 - PÁLPEBRAS E VIAS LACRIMAIS", "19912210","04.05.01.003-6", "DACRIOCISTORRINOSTOMIA",                                    991.88,  0),
    ("04.05.01 - PÁLPEBRAS E VIAS LACRIMAIS", "19912310","04.05.01.015-0", "SONDAGEM DE CANAL LACRIMAL SOB ANESTESIA GERAL",            295.53,  80836.99),
    ("04.05.05 - CONJUNTIVA, CÓRNEA, CÂMARA", "1991479", "04.05.05.002-0", "CAPSULECTOMIA A YAG LASER",                                124.86,  0),
    ("04.05.05 - CONJUNTIVA, CÓRNEA, CÂMARA", "1992044", "04.05.05.008-9", "EXERESE DE TUMOR DE CONJUNTIVA",                           213.88,  0),
    ("04.05.05 - CONJUNTIVA, CÓRNEA, CÂMARA", "1991897", "04.05.05.012-7", "FOTOTRABECULOPLASTIA A LASER",                             112.86,  0),
    ("04.05.05 - CONJUNTIVA, CÓRNEA, CÂMARA", "1992084", "04.05.05.021-6", "RECOBRIMENTO CONJUNTIVAL",                                  250.59,  0),
    ("04.05.05 - CONJUNTIVA, CÓRNEA, CÂMARA", "1992129", "04.05.05.037-2", "FACOEMULSIFICAÇÃO COM IMPLANTE DE LENTE INTRAOCULAR DOBRÁVEL", 771.60, 0),
    ("04.05.05 - CONJUNTIVA, CÓRNEA, CÂMARA", "1992149", "04.05.05.040-2", "RADIAÇÃO PARA CROSS LINKING CORNEANO",                     1321.52, 0),
    ("04.05.05 - CONJUNTIVA, CÓRNEA, CÂMARA", "1992159", "04.05.05.014-3", "IMPLANTE INTRA-ESTROMAL",                                   1576.17, 77899.45),
    ("04.05.02 - MÚSCULOS OCULOMOTORES",       "1992169", "04.05.02.001-5", "CORREÇÃO CIRÚRGICA DE ESTRABISMO (ACIMA DE 2 MÚSCULOS)",   1827.70, 0),
    ("04.05.02 - MÚSCULOS OCULOMOTORES",       "1992179", "04.05.02.002-3", "CORREÇÃO CIRÚRGICA DO ESTRABISMO (ATÉ 2 MÚSCULOS)",        1284.43, 15560.65),
]

with app.app_context():
    inseridos = 0
    for i, (forma, cat, sigtap, desc, vunit, meta) in enumerate(ITENS):
        existe = ItemContrato.query.filter_by(cod_sigtap=sigtap).first()
        if existe:
            print(f"  já existe: {sigtap} — {desc[:40]}")
            continue
        item = ItemContrato(
            contrato_nome="Contrato Estado CE 1199/2025",
            forma_org=forma,
            cod_catalogo=cat,
            cod_sigtap=sigtap,
            descricao=desc,
            valor_unit=vunit,
            meta_anual_val=meta,
            ativo=True,
            ordem=i+1,
        )
        db.session.add(item)
        inseridos += 1
        print(f"  inserido: {sigtap} — {desc[:45]} — R$ {vunit:,.2f}")
    db.session.commit()
    print(f"\nTotal inserido: {inseridos} itens")
    print(f"Valor global: R$ {sum(v for *_, v, _ in ITENS if v > 0):,.2f}")
