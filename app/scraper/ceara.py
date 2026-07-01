"""
Scraper do Portal Ceará Transparente (JavaScript SPA).
Usa Playwright com Chromium headless para renderizar a página.

URL base: https://cearatransparente.ce.gov.br/portal-da-transparencia/contratos/contratos
Busca por número de contrato (ex: 1199/2025) e extrai:
  - dados do contrato (fornecedor, objeto, valor, vigência, situação)
  - empenhos, liquidações e pagamentos quando disponíveis
"""
import re
import time
import datetime as dt

BASE = "https://cearatransparente.ce.gov.br/portal-da-transparencia/contratos/contratos"


def brl(texto):
    if not texto:
        return 0.0
    m = re.search(r"([\d\.]+,\d{2})", str(texto))
    if not m:
        return 0.0
    return float(m.group(1).replace(".", "").replace(",", "."))


def data_br(texto):
    if not texto:
        return None
    m = re.search(r"(\d{2})/(\d{2})/(\d{4})", str(texto))
    if not m:
        return None
    d, mth, y = map(int, m.groups())
    try:
        return dt.date(y, mth, d)
    except ValueError:
        return None


def buscar_contrato(numero_contrato):
    """
    Busca o contrato pelo número no Ceará Transparente.
    Retorna dict com dados do contrato ou None se não encontrado.
    """
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

    url_busca = (
        f"{BASE}?search_sacc={numero_contrato.replace('/', '%2F')}"
        "&locale=pt-BR"
    )

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
            ],
        )
        ctx = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
            locale="pt-BR",
            viewport={"width": 1280, "height": 800},
        )
        # Remove a flag webdriver que delata automação
        ctx.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'plugins', { get: () => [1,2,3] });
        """)
        page = ctx.new_page()
        page.set_extra_http_headers({
            "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        })

        print(f"[ceará] Abrindo página de busca...")
        try:
            page.goto(BASE, wait_until="networkidle", timeout=60000)
        except PWTimeout:
            page.goto(BASE, wait_until="domcontentloaded", timeout=60000)

        # Verifica se bloqueou
        if "403" in page.title() or "Forbidden" in page.content():
            print("[ceará] 403 Forbidden — portal bloqueou acesso headless.")
            _salvar_debug(page.content(), "ceara_403_debug.html")
            browser.close()
            return None

        time.sleep(2)

        # Preenche o campo search_sacc e clica em Buscar
        campo = page.query_selector("input[name='search_sacc']")
        if campo:
            campo.fill(numero_contrato)
            print(f"[ceará] Campo preenchido com: {numero_contrato}")
            # Clica no botão Buscar do mesmo formulário
            btn = page.query_selector("input[name='commit'][value='Buscar']")
            if btn:
                btn.click()
            else:
                campo.press("Enter")
            try:
                page.wait_for_load_state("networkidle", timeout=20000)
            except PWTimeout:
                pass
            time.sleep(2)
        else:
            # Fallback via URL com slash literal (sem encode)
            url_direta = f"{BASE}?locale=pt-BR&search_sacc={numero_contrato}&commit=Buscar"
            print(f"[ceará] Tentando URL direta: {url_direta}")
            try:
                page.goto(url_direta, wait_until="networkidle", timeout=60000)
            except PWTimeout:
                page.goto(url_direta, wait_until="domcontentloaded", timeout=60000)
            time.sleep(2)

        _salvar_debug(page.content(), "ceara_busca_debug.html")
        print(f"[ceará] Título: {page.title()}")

        # Conta resultados
        txt_pag = page.inner_text("body")
        import re as _re
        m_res = _re.search(r"Exibindo\s+(\d+)\s+de", txt_pag)
        if m_res:
            print(f"[ceará] Resultados encontrados: {m_res.group(1)}")

        # Busca link de detalhe — deve ter ID numérico no final (ex: /contratos/123456)
        detalhe_url = None
        import re as _re2
        for a in page.query_selector_all("a[href*='/contratos/']"):
            href = a.get_attribute("href") or ""
            # Link de detalhe termina com /contratos/NUMERO_ID
            if _re2.search(r"/contratos/\d+", href):
                detalhe_url = href if href.startswith("http") else f"https://cearatransparente.ce.gov.br{href}"
                print(f"[ceará] Link de detalhe: {detalhe_url}")
                break

        if not detalhe_url:
            # Tenta células da tabela com link
            for a in page.query_selector_all("table tbody tr td a"):
                href = a.get_attribute("href") or ""
                if href and "/contratos" in href and href != "/portal-da-transparencia/contratos/contratos":
                    detalhe_url = href if href.startswith("http") else f"https://cearatransparente.ce.gov.br{href}"
                    break

        if not detalhe_url:
            print("[ceará] Contrato não encontrado na listagem.")
            # Salva HTML para debug
            _salvar_debug(page.content(), "ceara_busca_debug.html")
            browser.close()
            return None

        print(f"[ceará] Abrindo detalhe: {detalhe_url}")
        page.goto(detalhe_url, wait_until="networkidle", timeout=60000)
        time.sleep(2)

        dados = _extrair_detalhe(page, detalhe_url)
        browser.close()
        return dados


def _extrair_detalhe(page, url):
    """Extrai todos os dados da página de detalhe do contrato."""
    texto_completo = page.inner_text("body")
    linhas = [l.strip() for l in texto_completo.split("\n") if l.strip()]

    def campo_apos(rotulo):
        for i, l in enumerate(linhas):
            if rotulo.lower() in l.lower() and i + 1 < len(linhas):
                return linhas[i + 1]
        return None

    # Campos básicos
    dados = {
        "url": url,
        "numero": campo_apos("Número do Contrato") or campo_apos("N° do Contrato") or campo_apos("Número"),
        "objeto": campo_apos("Objeto"),
        "fornecedor": campo_apos("Contratado") or campo_apos("Fornecedor") or campo_apos("Empresa"),
        "cnpj": campo_apos("CNPJ") or campo_apos("CPF/CNPJ"),
        "secretaria": campo_apos("Órgão") or campo_apos("Secretaria") or campo_apos("Unidade Gestora"),
        "situacao": campo_apos("Situação"),
        "valor_inicial": 0.0,
        "data_inicial": None,
        "data_final": None,
        "empenhos": [],
    }

    # Valor — tenta vários rótulos
    for rotulo in ("Valor Global", "Valor do Contrato", "Valor Contratado", "Valor"):
        v = campo_apos(rotulo)
        if v and "R$" in v:
            dados["valor_inicial"] = brl(v)
            break

    # Datas
    for rotulo in ("Início da Vigência", "Data de Início", "Data Início", "Início"):
        d = campo_apos(rotulo)
        if d and data_br(d):
            dados["data_inicial"] = data_br(d)
            break

    for rotulo in ("Fim da Vigência", "Data de Término", "Data Fim", "Término", "Fim"):
        d = campo_apos(rotulo)
        if d and data_br(d):
            dados["data_final"] = data_br(d)
            break

    # Empenhos — procura na tabela
    dados["empenhos"] = _extrair_empenhos(page)

    print(f"[ceará] Extraído: {dados['numero']} | {dados['fornecedor']} | R$ {dados['valor_inicial']:,.2f}")
    return dados


def _extrair_empenhos(page):
    """Tenta extrair empenhos vinculados da página."""
    empenhos = []
    try:
        tabelas = page.query_selector_all("table")
        for tabela in tabelas:
            cabecalho = tabela.inner_text().lower()
            if "empenho" in cabecalho or "nota" in cabecalho:
                linhas_tab = tabela.query_selector_all("tbody tr")
                for tr in linhas_tab:
                    cels = [td.inner_text().strip() for td in tr.query_selector_all("td")]
                    if len(cels) >= 2:
                        num = next((c for c in cels if re.search(r"\d{4,}", c)), None)
                        val = next((brl(c) for c in cels if "r$" in c.lower()), 0.0)
                        dat = next((data_br(c) for c in cels if data_br(c)), None)
                        if num:
                            empenhos.append({"numero": num, "valor": val, "data": dat})
    except Exception as e:
        print(f"[ceará] Aviso ao extrair empenhos: {e}")
    return empenhos


def _salvar_debug(html, nome):
    import os
    caminho = os.path.join(os.path.dirname(__file__), "..", nome)
    with open(caminho, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[ceará] HTML de debug salvo: {caminho}")


def sync_contrato_ceara(numero, app_context):
    """
    Sincroniza um contrato estadual via Playwright.
    Retorna (numero_str, msg) — nunca um objeto SQLAlchemy fora de sessão.
    """
    from models import db, Contrato

    dados = buscar_contrato(numero)
    if not dados:
        return None, f"Contrato {numero} não encontrado no Ceará Transparente."

    with app_context:
        chave = numero
        c = Contrato.query.filter(
            Contrato.numero.ilike(f"%{numero.split('/')[0]}%")
        ).filter(Contrato.orgao == "CE").first()

        if not c:
            c = Contrato(numero=chave, orgao="CE", ativo=True)
            db.session.add(c)

        c.secretaria   = dados.get("secretaria") or c.secretaria
        c.objeto       = dados.get("objeto")     or c.objeto
        c.fornecedor   = dados.get("fornecedor") or c.fornecedor
        c.cnpj         = dados.get("cnpj")       or c.cnpj
        c.valor_inicial= dados.get("valor_inicial") or c.valor_inicial
        c.data_inicial = dados.get("data_inicial") or c.data_inicial
        c.data_final   = dados.get("data_final")   or c.data_final
        c.url          = dados.get("url")          or c.url

        db.session.commit()
        # Retorna strings, não o objeto (evita DetachedInstanceError)
        return {
            "numero": c.numero,
            "fornecedor": c.fornecedor,
            "valor_inicial": float(c.valor_inicial or 0),
            "objeto": c.objeto,
        }, "ok"
