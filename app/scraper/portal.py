import re
import time
import datetime as dt
import requests
from bs4 import BeautifulSoup
from config import Config

_session = requests.Session()
_session.headers.update({"User-Agent": Config.USER_AGENT, "Accept-Language": "pt-BR"})


def fetch(url):
    time.sleep(Config.REQUEST_DELAY)
    r = _session.get(url, timeout=Config.REQUEST_TIMEOUT)
    r.raise_for_status()
    r.encoding = r.apparent_encoding or "utf-8"
    return r.text


def brl(texto):
    if not texto:
        return 0.0
    m = re.search(r"([\d\.]+,\d{2})", texto)
    if not m:
        return 0.0
    return float(m.group(1).replace(".", "").replace(",", "."))


def data_br(texto):
    if not texto:
        return None
    m = re.search(r"(\d{2})/(\d{2})/(\d{4})", texto)
    if not m:
        return None
    d, mth, y = map(int, m.groups())
    try:
        return dt.date(y, mth, d)
    except ValueError:
        return None


def _linhas(soup):
    txt = soup.get_text("\n")
    return [l.strip() for l in txt.split("\n") if l.strip()]


def _campos(linhas, rotulos):
    out = {}
    for i, linha in enumerate(linhas):
        for chave, alvo in rotulos.items():
            if linha == alvo and chave not in out and i + 1 < len(linhas):
                out[chave] = linhas[i + 1]
    return out


def parse_contrato(html, base):
    soup = BeautifulSoup(html, "lxml")
    linhas = _linhas(soup)
    c = _campos(
        linhas,
        {
            "secretaria": "Secretaria",
            "unidade": "Unidade Orçamentária",
            "numero": "Número",
            "objeto": "Objeto",
            "data_assinatura": "Data Assinatura",
            "data_inicial": "Data Inicial",
            "data_final": "Data Final",
            "fornecedor": "Fornecedor",
            "cnpj": "Fornecedor CPF/CNPJ",
            "valor_inicial": "Valor Inicial",
        },
    )
    dados = {
        "secretaria": c.get("secretaria"),
        "unidade": c.get("unidade"),
        "numero": c.get("numero"),
        "objeto": c.get("objeto"),
        "fornecedor": c.get("fornecedor"),
        "cnpj": c.get("cnpj"),
        "data_assinatura": data_br(c.get("data_assinatura")),
        "data_inicial": data_br(c.get("data_inicial")),
        "data_final": data_br(c.get("data_final")),
        "valor_inicial": brl(c.get("valor_inicial")),
    }
    a = soup.find("a", href=re.compile(r"/favorecido/detail/codigo:"))
    if a:
        m = re.search(r"codigo:(\d+)", a["href"])
        dados["favorecido_codigo"] = m.group(1) if m else None

    empenho_urls = []
    for a in soup.find_all("a", href=re.compile(r"/empenho/detail/numero:")):
        href = a["href"]
        if href.startswith("/"):
            href = base + href
        elif not href.startswith("http"):
            href = base + "/" + href
        if href not in empenho_urls:
            empenho_urls.append(href)
    dados["empenho_urls"] = empenho_urls
    return dados


def parse_empenho(html):
    soup = BeautifulSoup(html, "lxml")
    linhas = _linhas(soup)
    c = _campos(
        linhas,
        {
            "numero": "Número",
            "data": "Data",
            "valor": "Valor",
            "natureza": "Natureza",
            "fonte": "Fonte",
            "descricao": "Descrição/Objeto do Empenho",
        },
    )
    dados = {
        "numero": c.get("numero"),
        "data": data_br(c.get("data")),
        "valor_empenhado": brl(c.get("valor")),
        "natureza": c.get("natureza"),
        "fonte": c.get("fonte"),
        "descricao": c.get("descricao"),
        "liquidacoes": _liquidacoes(soup),
        "pagamentos": _pagamentos(soup),
    }
    return dados


def _liquidacoes(soup):
    texto = soup.get_text("\n")
    out = []
    partes = re.split(r"Cód\.?\s*Liquida[cç][aã]o\s*:?", texto)[1:]
    for parte in partes:
        cod = re.search(r"\s*(\d+)", parte)
        data = re.search(r"Data\s*:?\s*(\d{2}/\d{2}/\d{4})", parte)
        valor = re.search(r"Valor\s*:?\s*(R\$\s*[\d\.]+,\d{2})", parte)
        if cod:
            out.append(
                {
                    "cod_liquidacao": cod.group(1),
                    "data": data_br(data.group(1)) if data else None,
                    "valor": brl(valor.group(1)) if valor else 0.0,
                }
            )
    return out


def _pagamentos(soup):
    out = []
    for tabela in soup.find_all("table"):
        cab = " ".join(th.get_text(" ", strip=True).lower() for th in tabela.find_all("th"))
        if "doc" not in cab or "data" not in cab:
            continue
        for tr in tabela.find_all("tr"):
            cels = [td.get_text(" ", strip=True) for td in tr.find_all("td")]
            if len(cels) < 4:
                continue
            if "total" in cels[0].lower():
                continue
            data = next((data_br(x) for x in cels if data_br(x)), None)
            doc = next((x for x in cels if re.fullmatch(r"\d{6,10}", x)), None)
            valor = next((brl(x) for x in cels if "r$" in x.lower()), 0.0)
            if data or valor:
                out.append({"descricao": cels[0], "data": data, "doc": doc, "valor": valor})
        if out:
            break
    return out
