import datetime as dt
from config import Config
from models import db, Contrato, Empenho, Liquidacao, Pagamento
from scraper import portal


def sync_contrato(numero, orgao):
    base = Config.PORTAL_BASE
    url = f"{base}/contrato/detail/numero:{numero}/orgao:{orgao}"
    dados = portal.parse_contrato(portal.fetch(url), base)

    contrato = Contrato.query.filter_by(numero=numero).first()
    if not contrato:
        contrato = Contrato(numero=numero)
        db.session.add(contrato)
    contrato.orgao = orgao
    contrato.secretaria = dados.get("secretaria")
    contrato.unidade = dados.get("unidade")
    contrato.objeto = dados.get("objeto")
    contrato.fornecedor = dados.get("fornecedor")
    contrato.cnpj = dados.get("cnpj")
    contrato.favorecido_codigo = dados.get("favorecido_codigo")
    contrato.data_assinatura = dados.get("data_assinatura")
    contrato.data_inicial = dados.get("data_inicial")
    contrato.data_final = dados.get("data_final")
    contrato.valor_inicial = dados.get("valor_inicial") or 0
    contrato.url = url
    db.session.flush()

    novidades = []
    ano_corrente = dt.date.today().year

    for emp_url in dados["empenho_urls"]:
        existente = Empenho.query.filter_by(url=emp_url).first()
        if existente and not _precisa_reraspar(existente, ano_corrente):
            continue

        edata = portal.parse_empenho(portal.fetch(emp_url))
        if not edata.get("numero"):
            continue

        empenho = Empenho.query.filter_by(numero=edata["numero"]).first()
        if not empenho:
            empenho = Empenho(numero=edata["numero"])
            db.session.add(empenho)
        empenho.contrato_id = contrato.id
        empenho.orgao = orgao
        empenho.data = edata.get("data")
        empenho.valor_empenhado = edata.get("valor_empenhado") or 0
        empenho.descricao = edata.get("descricao")
        empenho.natureza = edata.get("natureza")
        empenho.fonte = edata.get("fonte")
        empenho.url = emp_url
        db.session.flush()

        novidades += _upsert_liquidacoes(empenho, edata["liquidacoes"])
        novidades += _upsert_pagamentos(empenho, edata["pagamentos"])

    db.session.commit()
    return contrato, novidades


def _precisa_reraspar(empenho, ano_corrente):
    if empenho.data and empenho.data.year >= ano_corrente:
        return True
    if empenho.saldo_a_pagar > 0.005:
        return True
    return False


def _upsert_liquidacoes(empenho, lista):
    novos = []
    for l in lista:
        existe = Liquidacao.query.filter_by(
            empenho_id=empenho.id, cod_liquidacao=l["cod_liquidacao"]
        ).first()
        if existe:
            continue
        liq = Liquidacao(
            empenho_id=empenho.id,
            cod_liquidacao=l["cod_liquidacao"],
            data=l.get("data"),
            valor=l.get("valor") or 0,
        )
        db.session.add(liq)
        novos.append(("liquidacao", empenho, liq))
    return novos


def _upsert_pagamentos(empenho, lista):
    novos = []
    for p in lista:
        existe = Pagamento.query.filter_by(
            empenho_id=empenho.id, doc=p.get("doc"), valor=p.get("valor") or 0
        ).first()
        if existe:
            continue
        pag = Pagamento(
            empenho_id=empenho.id,
            doc=p.get("doc"),
            data=p.get("data"),
            valor=p.get("valor") or 0,
            descricao=p.get("descricao"),
        )
        db.session.add(pag)
        novos.append(("pagamento", empenho, pag))
    return novos
