"""
Importador de produção ambulatorial BPA-I do SIASUS (DATASUS).
Arquivos DBC filtrados por CNPJ do prestador (C A DE SOUSA REZENDE).

FTP: ftp.datasus.gov.br/dissemin/publicos/SIASUS/200801_/Dados/
Padrão de arquivo: PACE<AA><MM>.dbc  (PA = produção ambu, CE = Ceará)
"""
import ftplib
import os
import tempfile
import datetime as dt
import logging
import re

log = logging.getLogger(__name__)

FTP_HOST    = "ftp.datasus.gov.br"
FTP_DIR     = "/dissemin/publicos/SIASUS/200801_/Dados/"
CNPJ_FILTRO = "15061733000103"   # C A DE SOUSA REZENDE
CNES_FILTRO = "0067326"

# Pasta local com arquivos DBC já baixados
LOCAL_DBC_DIR = r"C:\Users\daril\OneDrive\Documentos\Claude\Projects\CONTRATOS"
# Planilha SIGTAP com nomes oficiais dos procedimentos
SIGTAP_XLTX = os.path.join(LOCAL_DBC_DIR, "S_PROCED.xltx")

TPFIN_LABELS = {
    "01": "PAB",
    "02": "FAEC",
    "04": "FAEC",
    "05": "Epidemiologia",
    "06": "MAC",
    "07": "INVESTIMENTO",
}

_PROC_NOMES_CACHE = {}

# Nomes dos procedimentos oftalmológicos mais comuns (fallback quando SIGTAP não disponível)
_PROC_NOMES_FALLBACK = {
    "0405050372": "FACOEMULSIFICAÇÃO C/ IMPLANTE DE LIO DOBRÁVEL",
    "0405050020": "CAPSULOTOMIA A YAG LASER",
    "0405050038": "CIRURGIA DE CATARATA EXTRACAPSULAR",
    "0405050046": "CIRURGIA DE PTERÍGIO",
    "0405050054": "CIRURGIA DE ESTRABISMO",
    "0405050062": "CIRURGIA DE GLAUCOMA",
    "0405050070": "VITRECTOMIA",
    "0405010053": "CONSULTA OFTALMOLÓGICA",
    "0301010064": "CONSULTA MÉDICA EM ATENÇÃO BÁSICA",
    "0211070149": "TOMOGRAFIA DE COERÊNCIA ÓPTICA",
    "0211070130": "RETINOGRAFIA COLORIDA",
    "0211070121": "RETINOGRAFIA SEM COLORAÇÃO",
    "0211060100": "CAMPO VISUAL",
    "0211060053": "BIOMICROSCOPIA DE FUNDO DE OLHO",
    "0211060038": "BIOMETRIA OCULAR",
}


def _carregar_sigtap():
    """Carrega nomes oficiais de procedimentos do S_PROCED.xltx."""
    global _PROC_NOMES_CACHE
    if _PROC_NOMES_CACHE:
        return
    if not os.path.exists(SIGTAP_XLTX):
        log.warning("[SIA] S_PROCED.xltx não encontrado em %s", SIGTAP_XLTX)
        return
    try:
        import openpyxl
        wb = openpyxl.load_workbook(SIGTAP_XLTX, read_only=True, data_only=True)
        ws = wb["Planilha1"]
        for i, row in enumerate(ws.iter_rows(values_only=True)):
            if i == 0 or not row[0]:
                continue
            cod = str(row[1] or "").strip().zfill(9) + str(row[2] or "").strip()
            _PROC_NOMES_CACHE[cod] = str(row[3] or "").strip()
        log.info("[SIA] SIGTAP carregado: %d procedimentos.", len(_PROC_NOMES_CACHE))
    except Exception as e:
        log.error("[SIA] Erro ao carregar S_PROCED.xltx: %s", e)


def _nome_proc(proc_id):
    if not _PROC_NOMES_CACHE:
        _carregar_sigtap()
    cod = str(proc_id).strip()
    return _PROC_NOMES_CACHE.get(cod) or _PROC_NOMES_FALLBACK.get(cod, cod)


# Municípios — códigos IBGE 6 dígitos (primeiros 6 do código de 7 dígitos)
# Fonte: API IBGE /api/v1/localidades/estados/CE/municipios + SP e BA encontrados nos dados
_MUNICIPIOS_CE = {
    "230010": "Abaiara", "230015": "Acarape", "230020": "Acaraú", "230030": "Acopiara",
    "230040": "Aiuaba", "230050": "Alcântaras", "230060": "Altaneira", "230070": "Alto Santo",
    "230075": "Amontada", "230080": "Antonina do Norte", "230090": "Apuiarés", "230100": "Aquiraz",
    "230110": "Aracati", "230120": "Aracoiaba", "230125": "Ararendá", "230130": "Araripe",
    "230140": "Aratuba", "230150": "Arneiroz", "230160": "Assaré", "230170": "Aurora",
    "230180": "Baixio", "230185": "Banabuiú", "230190": "Barbalha", "230195": "Barreira",
    "230200": "Barro", "230205": "Barroquinha", "230210": "Baturité", "230220": "Beberibe",
    "230230": "Bela Cruz", "230240": "Boa Viagem", "230250": "Brejo Santo", "230260": "Camocim",
    "230270": "Campos Sales", "230280": "Canindé", "230290": "Capistrano", "230300": "Caridade",
    "230310": "Cariré", "230320": "Caririaçu", "230330": "Cariús", "230340": "Carnaubal",
    "230350": "Cascavel", "230360": "Catarina", "230365": "Catunda", "230370": "Caucaia",
    "230380": "Cedro", "230390": "Chaval", "230393": "Choró", "230395": "Chorozinho",
    "230400": "Coreaú", "230410": "Crateús", "230420": "Crato", "230423": "Croatá", "230425": "Cruz",
    "230426": "Deputado Irapuan Pinheiro", "230427": "Ererê", "230428": "Eusébio",
    "230430": "Farias Brito", "230435": "Forquilha", "230440": "Fortaleza", "230445": "Fortim",
    "230450": "Frecheirinha", "230460": "General Sampaio", "230465": "Graça", "230470": "Granja",
    "230480": "Granjeiro", "230490": "Groaíras", "230495": "Guaiúba", "230500": "Guaraciaba do Norte",
    "230510": "Guaramiranga", "230520": "Hidrolândia", "230523": "Horizonte", "230526": "Ibaretama",
    "230530": "Ibiapina", "230533": "Ibicuitinga", "230535": "Icapuí", "230540": "Icó",
    "230550": "Iguatu", "230560": "Independência", "230565": "Ipaporanga", "230570": "Ipaumirim",
    "230580": "Ipu", "230590": "Ipueiras", "230600": "Iracema", "230610": "Irauçuba",
    "230620": "Itaiçaba", "230625": "Itaitinga", "230630": "Itapajé", "230640": "Itapipoca",
    "230650": "Itapiúna", "230655": "Itarema", "230660": "Itatira", "230670": "Jaguaretama",
    "230680": "Jaguaribara", "230690": "Jaguaribe", "230700": "Jaguaruana", "230710": "Jardim",
    "230720": "Jati", "230725": "Jijoca de Jericoacoara", "230730": "Juazeiro do Norte",
    "230740": "Jucás", "230750": "Lavras da Mangabeira", "230760": "Limoeiro do Norte",
    "230763": "Madalena", "230765": "Maracanaú", "230770": "Maranguape", "230780": "Marco",
    "230790": "Martinópole", "230800": "Massapê", "230810": "Mauriti", "230820": "Meruoca",
    "230830": "Milagres", "230835": "Milhã", "230837": "Miraíma", "230840": "Missão Velha",
    "230850": "Mombaça", "230860": "Monsenhor Tabosa", "230870": "Morada Nova", "230880": "Moraújo",
    "230890": "Morrinhos", "230900": "Mucambo", "230910": "Mulungu", "230920": "Nova Olinda",
    "230930": "Nova Russas", "230940": "Novo Oriente", "230945": "Ocara", "230950": "Orós",
    "230960": "Pacajus", "230970": "Pacatuba", "230980": "Pacoti", "230990": "Pacujá",
    "231000": "Palhano", "231010": "Palmácia", "231020": "Paracuru", "231025": "Paraipaba",
    "231030": "Parambu", "231040": "Paramoti", "231050": "Pedra Branca", "231060": "Penaforte",
    "231070": "Pentecoste", "231080": "Pereiro", "231085": "Pindoretama", "231090": "Piquet Carneiro",
    "231095": "Pires Ferreira", "231100": "Poranga", "231110": "Porteiras", "231120": "Potengi",
    "231123": "Potiretama", "231126": "Quiterianópolis", "231130": "Quixadá", "231135": "Quixelô",
    "231140": "Quixeramobim", "231150": "Quixeré", "231160": "Redenção", "231170": "Reriutaba",
    "231180": "Russas", "231190": "Saboeiro", "231195": "Salitre", "231200": "Santana do Acaraú",
    "231210": "Santana do Cariri", "231220": "Santa Quitéria", "231230": "São Benedito",
    "231240": "São Gonçalo do Amarante", "231250": "São João do Jaguaribe",
    "231260": "São Luís do Curu", "231270": "Senador Pompeu", "231280": "Senador Sá",
    "231290": "Sobral", "231300": "Solonópole", "231310": "Tabuleiro do Norte", "231320": "Tamboril",
    "231325": "Tarrafas", "231330": "Tauá", "231335": "Tejuçuoca", "231340": "Tianguá",
    "231350": "Trairi", "231355": "Tururu", "231360": "Ubajara", "231370": "Umari", "231375": "Umirim",
    "231380": "Uruburetama", "231390": "Uruoca", "231395": "Varjota", "231400": "Várzea Alegre",
    "231410": "Viçosa do Ceará",
    # Outros estados encontrados nos dados
    "355030": "São Paulo/SP", "293135": "Teixeira de Freitas/BA",
}


def _nome_municipio(cod):
    c = str(cod).strip().zfill(6)
    return _MUNICIPIOS_CE.get(c, f"Cód {c}")


def listar_arquivos_ftp(prefixo="PACE"):
    """Lista arquivos disponíveis no FTP para o estado do Ceará (PACE*)."""
    ftp = ftplib.FTP(FTP_HOST, timeout=60)
    ftp.login()
    ftp.cwd(FTP_DIR)
    todos = ftp.nlst(f"{prefixo}*.dbc")
    ftp.quit()
    todos.sort()
    return [os.path.splitext(f)[0] for f in todos]  # sem .dbc


def baixar_arquivo(nome, destino):
    """Baixa <nome>.dbc do FTP para <destino>."""
    ftp = ftplib.FTP(FTP_HOST, timeout=120)
    ftp.login()
    ftp.cwd(FTP_DIR)
    log.info("[SIA] Baixando %s.dbc ...", nome)
    with open(destino, "wb") as f:
        ftp.retrbinary(f"RETR {nome}.dbc", f.write)
    ftp.quit()
    log.info("[SIA] %s.dbc salvo (%d bytes)", nome, os.path.getsize(destino))


def _competencia(nome):
    """PACE2604 → '202604'  (AAAAMM)"""
    ano2 = nome[4:6]   # '26'
    mes  = nome[6:8]   # '04'
    ano4 = f"20{ano2}"
    return f"{ano4}{mes}"


def processar_arquivo_stream(nome, dbc_path_externo, app_ctx):
    """Processa um arquivo DBC já salvo em disco (upload pelo usuário)."""
    return processar_arquivo(nome, app_ctx, dbc_externo=dbc_path_externo)


def processar_arquivo(nome, app_ctx, dbc_externo=None):
    """
    Baixa, converte e importa um arquivo DBC usando leitura lazy (stream)
    para evitar carregar todo o arquivo na RAM.
    Retorna número de registros inseridos/atualizados.
    dbc_externo: caminho de um DBC já salvo (upload web) — pula download.
    """
    from dbfread import DBF
    from collections import defaultdict

    tmp_dir = tempfile.gettempdir()
    dbc_path = os.path.join(tmp_dir, f"{nome}.dbc")
    dbf_path = os.path.join(tmp_dir, f"{nome}.dbf")

    try:
        if dbc_externo:
            # Arquivo enviado via upload web
            dbc_path = dbc_externo
            dbf_path = os.path.join(tmp_dir, f"{nome}.dbf")
        else:
            # Usa arquivo local se disponível (evita download do FTP)
            local_dbc = os.path.join(LOCAL_DBC_DIR, f"{nome}.dbc")
            if not os.path.exists(local_dbc):
                local_dbc = os.path.join(LOCAL_DBC_DIR, f"{nome.lower()}.dbc")
            if os.path.exists(local_dbc):
                log.info("[SIA] Usando arquivo local: %s", local_dbc)
                dbc_path = local_dbc
                dbf_path = os.path.join(tmp_dir, f"{nome}.dbf")
            else:
                baixar_arquivo(nome, dbc_path)

        if not os.path.exists(dbf_path):
            log.info("[SIA] Convertendo DBC -> DBF ...")
            import pyreaddbc
            pyreaddbc.dbc2dbf(dbc_path, dbf_path)

        log.info("[SIA] Lendo DBF em stream, filtrando CNPJ %s ...", CNPJ_FILTRO)

        # Agrega procedimentos: chave=(proc_id, tpfin, subfin, cnes)
        agg = defaultdict(lambda: {
            "qtd_prod": 0, "qtd_apr": 0,
            "val_prod": 0.0, "val_apr": 0.0,
            "municipio": "",
        })
        # Agrega origem do paciente: chave=municipio_cod (PA_MUNPCN)
        agg_orig = defaultdict(lambda: {"qtd_prod": 0, "qtd_apr": 0, "val_apr": 0.0})
        # Agrega município × procedimento: chave=(municipio_cod, proc_id, tpfin)
        agg_orig_proc = defaultdict(lambda: {"qtd_prod": 0, "qtd_apr": 0, "val_prod": 0.0, "val_apr": 0.0})

        total_lidos = 0
        total_clinica = 0
        for rec in DBF(dbf_path, encoding="latin-1", load=False):
            total_lidos += 1
            cnpj_rec = re.sub(r"\D", "", str(rec.get("PA_CNPJCPF") or ""))
            cnes_rec = str(rec.get("PA_CODUNI") or "").strip().zfill(7)
            if cnpj_rec != CNPJ_FILTRO or cnes_rec != CNES_FILTRO:
                continue
            total_clinica += 1
            chave = (
                str(rec.get("PA_PROC_ID") or "").strip(),
                str(rec.get("PA_TPFIN")   or "").strip(),
                str(rec.get("PA_SUBFIN")   or "").strip(),
                str(rec.get("PA_CODUNI")   or "").strip(),
            )
            bucket = agg[chave]
            qtd_pro = int(rec.get("PA_QTDPRO") or 0)
            qtd_apr = int(rec.get("PA_QTDAPR") or 0)
            val_pro = float(rec.get("PA_VALPRO") or 0)
            val_apr = float(rec.get("PA_VALAPR") or 0)
            bucket["qtd_prod"] += qtd_pro
            bucket["qtd_apr"]  += qtd_apr
            bucket["val_prod"] += val_pro
            bucket["val_apr"]  += val_apr
            if not bucket["municipio"]:
                bucket["municipio"] = str(rec.get("PA_UFMUN") or "").strip()

            # Município de residência do paciente
            munpcn = str(rec.get("PA_MUNPCN") or "").strip().zfill(6)
            if munpcn and munpcn != "000000":
                ob = agg_orig[munpcn]
                ob["qtd_prod"] += qtd_pro
                ob["qtd_apr"]  += qtd_apr
                ob["val_apr"]  += val_apr
                # município × procedimento
                proc_id = str(rec.get("PA_PROC_ID") or "").strip()
                tpfin   = str(rec.get("PA_TPFIN")   or "").strip()
                op = agg_orig_proc[(munpcn, proc_id, tpfin)]
                op["qtd_prod"] += qtd_pro
                op["qtd_apr"]  += qtd_apr
                op["val_prod"] += val_pro
                op["val_apr"]  += val_apr

            if total_lidos % 200000 == 0:
                log.info("[SIA] %s: %d lidos, %d da clinica...", nome, total_lidos, total_clinica)

        log.info("[SIA] Total lido: %d | Clinica: %d | Grupos: %d | Municípios: %d",
                 total_lidos, total_clinica, len(agg), len(agg_orig))

        if not agg:
            return 0

        competencia = _competencia(nome)

        with app_ctx:
            from models import db, ProducaoSIA, SIAArquivo, SIAOrigem, SIAOrigemProc

            count = 0
            for (proc_id, tpfin, subfin, cnes), vals in agg.items():
                rec_db = ProducaoSIA.query.filter_by(
                    competencia=competencia,
                    cnes=cnes,
                    proc_id=proc_id,
                    tpfin=tpfin,
                    subfin=subfin,
                ).first()
                if not rec_db:
                    rec_db = ProducaoSIA(
                        competencia=competencia,
                        cnes=cnes,
                        cnpj=CNPJ_FILTRO,
                        proc_id=proc_id,
                        tpfin=tpfin,
                        subfin=subfin,
                        arquivo_orig=nome,
                    )
                    db.session.add(rec_db)

                rec_db.nome_proc     = _nome_proc(proc_id)
                rec_db.qtd_produzida = vals["qtd_prod"]
                rec_db.qtd_aprovada  = vals["qtd_apr"]
                rec_db.val_produzido = vals["val_prod"]
                rec_db.val_aprovado  = vals["val_apr"]
                rec_db.municipio     = vals["municipio"]
                count += 1

            # Grava origem por município do paciente
            SIAOrigem.query.filter_by(competencia=competencia).delete()
            for mun_cod, ov in agg_orig.items():
                orig = SIAOrigem(
                    competencia=competencia,
                    municipio_cod=mun_cod,
                    municipio_nom=_nome_municipio(mun_cod),
                    qtd_produzida=ov["qtd_prod"],
                    qtd_aprovada=ov["qtd_apr"],
                    val_aprovado=ov["val_apr"],
                )
                db.session.add(orig)

            # Grava origem × procedimento
            SIAOrigemProc.query.filter_by(competencia=competencia).delete()
            for (mun_cod, proc_id, tpfin), ov in agg_orig_proc.items():
                db.session.add(SIAOrigemProc(
                    competencia=competencia,
                    municipio_cod=mun_cod,
                    proc_id=proc_id,
                    tpfin=tpfin,
                    qtd_produzida=ov["qtd_prod"],
                    qtd_aprovada=ov["qtd_apr"],
                    val_produzido=ov["val_prod"],
                    val_aprovado=ov["val_apr"],
                ))

            arq = SIAArquivo.query.filter_by(nome=nome).first()
            if not arq:
                arq = SIAArquivo(nome=nome)
                db.session.add(arq)
            arq.competencia  = competencia
            arq.importado_em = dt.datetime.utcnow()
            arq.registros    = count

            db.session.commit()
            log.info("[SIA] %s importado: %d grupos.", nome, count)
            return count

    finally:
        # Remove apenas arquivos temporários (não remove locais nem arquivos em LOCAL_DBC_DIR)
        for p in (dbc_path, dbf_path):
            if LOCAL_DBC_DIR not in p and os.path.exists(p):
                try:
                    os.unlink(p)
                except Exception:
                    pass


def sincronizar_novos(app_ctx, a_partir="PACE2508"):
    """
    Verifica o FTP, baixa e importa apenas arquivos novos (não importados ainda).
    Retorna lista de (nome, registros).
    """
    with app_ctx:
        from models import SIAArquivo
        importados = {a.nome for a in SIAArquivo.query.all()}

    disponiveis = listar_arquivos_ftp()
    novos = [n for n in disponiveis if n >= a_partir and n not in importados]
    log.info("[SIA] Disponíveis: %d | Já importados: %d | Novos: %s",
             len(disponiveis), len(importados), novos)

    resultados = []
    for nome in novos:
        try:
            n = processar_arquivo(nome, app_ctx)
            resultados.append((nome, n))
        except Exception as e:
            log.error("[SIA] Erro ao processar %s: %s", nome, e)
            resultados.append((nome, -1))
    return resultados
