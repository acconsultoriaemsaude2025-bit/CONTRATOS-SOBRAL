from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


class Usuario(UserMixin, db.Model):
    __tablename__ = "usuarios"
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    senha_hash = db.Column(db.String(256), nullable=False)
    admin = db.Column(db.Boolean, default=False)
    ativo = db.Column(db.Boolean, default=True)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

    def set_senha(self, senha):
        self.senha_hash = generate_password_hash(senha)

    def check_senha(self, senha):
        return check_password_hash(self.senha_hash, senha)


class Contrato(db.Model):
    __tablename__ = "contratos"
    id = db.Column(db.Integer, primary_key=True)
    numero = db.Column(db.String(40), unique=True, nullable=False, index=True)
    orgao = db.Column(db.String(8))
    secretaria = db.Column(db.String(120))
    unidade = db.Column(db.String(120))
    objeto = db.Column(db.Text)
    fornecedor = db.Column(db.String(200))
    cnpj = db.Column(db.String(20), index=True)
    favorecido_codigo = db.Column(db.String(20))
    data_assinatura = db.Column(db.Date)
    data_inicial = db.Column(db.Date)
    data_final = db.Column(db.Date)
    valor_inicial = db.Column(db.Numeric(15, 2), default=0)
    valor_total = db.Column(db.Numeric(15, 2), default=0)
    url = db.Column(db.String(300))
    ativo = db.Column(db.Boolean, default=True)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    atualizado_em = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    empenhos = db.relationship("Empenho", backref="contrato", cascade="all, delete-orphan")

    @property
    def total_empenhado(self):
        return sum((float(e.valor_empenhado or 0)) for e in self.empenhos)

    @property
    def total_liquidado(self):
        return sum((float(l.valor or 0)) for e in self.empenhos for l in e.liquidacoes)

    @property
    def total_pago(self):
        return sum((float(p.valor or 0)) for e in self.empenhos for p in e.pagamentos)

    @property
    def pct_pago(self):
        emp = self.total_empenhado
        return round(self.total_pago / emp * 100, 1) if emp else 0

    @property
    def status(self):
        import datetime as dt
        if self.data_final and self.data_final < dt.date.today():
            return "encerrado"
        if self.total_empenhado == 0:
            return "pendente"
        if self.total_pago >= self.total_empenhado * 0.99:
            return "quitado"
        return "ativo"


class Empenho(db.Model):
    __tablename__ = "empenhos"
    id = db.Column(db.Integer, primary_key=True)
    numero = db.Column(db.String(40), unique=True, nullable=False, index=True)
    contrato_id = db.Column(db.Integer, db.ForeignKey("contratos.id"))
    orgao = db.Column(db.String(8))
    unidade = db.Column(db.String(8))
    data = db.Column(db.Date)
    valor_empenhado = db.Column(db.Numeric(15, 2), default=0)
    descricao = db.Column(db.Text)
    natureza = db.Column(db.String(200))
    fonte = db.Column(db.String(300))
    url = db.Column(db.String(300))
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    atualizado_em = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    liquidacoes = db.relationship("Liquidacao", backref="empenho", cascade="all, delete-orphan")
    pagamentos = db.relationship("Pagamento", backref="empenho", cascade="all, delete-orphan")

    @property
    def total_liquidado(self):
        return sum((float(l.valor or 0)) for l in self.liquidacoes)

    @property
    def total_pago(self):
        return sum((float(p.valor or 0)) for p in self.pagamentos)

    @property
    def saldo_a_pagar(self):
        return float(self.valor_empenhado or 0) - self.total_pago


class Liquidacao(db.Model):
    __tablename__ = "liquidacoes"
    id = db.Column(db.Integer, primary_key=True)
    empenho_id = db.Column(db.Integer, db.ForeignKey("empenhos.id"))
    cod_liquidacao = db.Column(db.String(30), index=True)
    data = db.Column(db.Date)
    valor = db.Column(db.Numeric(15, 2), default=0)
    descricao = db.Column(db.Text)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint("empenho_id", "cod_liquidacao", name="uq_liq"),)


class Pagamento(db.Model):
    __tablename__ = "pagamentos"
    id = db.Column(db.Integer, primary_key=True)
    empenho_id = db.Column(db.Integer, db.ForeignKey("empenhos.id"))
    doc = db.Column(db.String(30), index=True)
    data = db.Column(db.Date)
    valor = db.Column(db.Numeric(15, 2), default=0)
    descricao = db.Column(db.Text)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint("empenho_id", "doc", "valor", name="uq_pag"),)


class ProducaoSIA(db.Model):
    """Produção ambulatorial BPA-I do SIASUS filtrada por CNPJ do prestador."""
    __tablename__ = "producao_sia"
    id            = db.Column(db.Integer, primary_key=True)
    competencia   = db.Column(db.String(6), nullable=False, index=True)   # AAAAMM ex 202604
    cnes          = db.Column(db.String(7), index=True)
    cnpj          = db.Column(db.String(14), index=True)
    proc_id       = db.Column(db.String(10), nullable=False, index=True)  # PA_PROC_ID
    nome_proc     = db.Column(db.String(200))
    tpfin         = db.Column(db.String(2))   # Tipo financiamento (06=FAEC, etc.)
    subfin        = db.Column(db.String(6))   # Subfinanciamento
    qtd_produzida = db.Column(db.Integer, default=0)
    qtd_aprovada  = db.Column(db.Integer, default=0)
    val_produzido = db.Column(db.Numeric(15, 2), default=0)
    val_aprovado  = db.Column(db.Numeric(15, 2), default=0)
    municipio     = db.Column(db.String(6))
    arquivo_orig  = db.Column(db.String(20))  # Ex: PACE2604
    criado_em     = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint("competencia", "cnes", "proc_id", "tpfin", "subfin", name="uq_sia"),
    )


class SIAOrigem(db.Model):
    """Produção por município de residência do paciente (PA_MUNPCN)."""
    __tablename__ = "sia_origem"
    id            = db.Column(db.Integer, primary_key=True)
    competencia   = db.Column(db.String(6), nullable=False, index=True)
    municipio_cod = db.Column(db.String(7), nullable=False, index=True)
    municipio_nom = db.Column(db.String(80))
    qtd_produzida = db.Column(db.Integer, default=0)
    qtd_aprovada  = db.Column(db.Integer, default=0)
    val_aprovado  = db.Column(db.Numeric(15, 2), default=0)
    __table_args__ = (
        db.UniqueConstraint("competencia", "municipio_cod", name="uq_origem"),
    )


class SIAOrigemProc(db.Model):
    """Produção por município × procedimento (para filtros cruzados)."""
    __tablename__ = "sia_origem_proc"
    id            = db.Column(db.Integer, primary_key=True)
    competencia   = db.Column(db.String(6), nullable=False, index=True)
    municipio_cod = db.Column(db.String(7), nullable=False, index=True)
    proc_id       = db.Column(db.String(10), nullable=False, index=True)
    tpfin         = db.Column(db.String(2))
    qtd_produzida = db.Column(db.Integer, default=0)
    qtd_aprovada  = db.Column(db.Integer, default=0)
    val_produzido = db.Column(db.Numeric(15, 2), default=0)
    val_aprovado  = db.Column(db.Numeric(15, 2), default=0)
    __table_args__ = (
        db.UniqueConstraint("competencia", "municipio_cod", "proc_id", "tpfin", name="uq_orig_proc"),
    )


class Licenca(db.Model):
    """Licenças e alvarás da clínica."""
    __tablename__ = "licencas"
    id            = db.Column(db.Integer, primary_key=True)
    tipo          = db.Column(db.String(80), nullable=False)   # Ex: Alvará Sanitário Estadual
    categoria     = db.Column(db.String(50))                   # sanitario, funcionamento, ambiental, etc.
    orgao_emissor = db.Column(db.String(120))                  # VISA, Corpo de Bombeiros, etc.
    numero        = db.Column(db.String(60))                   # Número do documento
    data_emissao  = db.Column(db.Date)
    data_vencimento = db.Column(db.Date)
    dias_antecedencia = db.Column(db.Integer, default=90)      # Alertar X dias antes
    situacao      = db.Column(db.String(20), default="vigente") # vigente, vencida, renovando, cancelada
    observacoes   = db.Column(db.Text)
    arquivo_nome  = db.Column(db.String(200))                  # Nome do arquivo anexado
    arquivo_dados = db.Column(db.LargeBinary)                  # Conteúdo do arquivo
    criado_em     = db.Column(db.DateTime, default=datetime.utcnow)
    atualizado_em = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @property
    def dias_para_vencer(self):
        if not self.data_vencimento:
            return None
        return (self.data_vencimento - datetime.utcnow().date()).days

    @property
    def status_alerta(self):
        d = self.dias_para_vencer
        if d is None:
            return "sem_vencimento"
        if d < 0:
            return "vencida"
        if d <= self.dias_antecedencia:
            return "alerta"
        return "ok"


class ItemContrato(db.Model):
    """Itens/procedimentos de contrato com o estado (meta anual)."""
    __tablename__ = "itens_contrato"
    id            = db.Column(db.Integer, primary_key=True)
    contrato_nome = db.Column(db.String(120), default="Contrato Estado CE")
    forma_org     = db.Column(db.String(120))
    cod_catalogo  = db.Column(db.String(20))
    cod_sigtap    = db.Column(db.String(20))
    descricao     = db.Column(db.String(300))
    valor_unit    = db.Column(db.Numeric(12, 2), default=0)
    meta_anual_val = db.Column(db.Numeric(12, 2), default=0)
    ativo         = db.Column(db.Boolean, default=True)
    ordem         = db.Column(db.Integer, default=0)
    criado_em     = db.Column(db.DateTime, default=datetime.utcnow)

    lancamentos   = db.relationship("LancamentoItem", backref="item", cascade="all, delete-orphan")

    @property
    def meta_qtd(self):
        if self.valor_unit and float(self.valor_unit) > 0:
            return int(float(self.meta_anual_val or 0) / float(self.valor_unit))
        return 0

    @property
    def total_realizado_val(self):
        return sum(float(l.val_realizado or 0) for l in self.lancamentos)

    @property
    def total_realizado_qtd(self):
        return sum(int(l.qtd_realizada or 0) for l in self.lancamentos)

    @property
    def pct_execucao(self):
        meta = float(self.meta_anual_val or 0)
        return round(self.total_realizado_val / meta * 100, 1) if meta > 0 else 0


class LancamentoItem(db.Model):
    """Lançamento mensal do realizado por item do contrato."""
    __tablename__ = "lancamentos_item"
    id            = db.Column(db.Integer, primary_key=True)
    item_id       = db.Column(db.Integer, db.ForeignKey("itens_contrato.id"), nullable=False)
    competencia   = db.Column(db.String(6), nullable=False)
    qtd_realizada = db.Column(db.Integer, default=0)
    val_realizado = db.Column(db.Numeric(12, 2), default=0)
    observacao    = db.Column(db.Text)
    criado_em     = db.Column(db.DateTime, default=datetime.utcnow)
    atualizado_em = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint("item_id", "competencia", name="uq_lancamento"),
    )


class PactuacaoFederal(db.Model):
    """Pactuações de procedimentos eletivos federais por município de origem."""
    __tablename__ = "pactuacoes_federais"
    id            = db.Column(db.Integer, primary_key=True)
    ano           = db.Column(db.Integer, nullable=False, default=2026)
    municipio     = db.Column(db.String(100), nullable=False)
    proc_cod      = db.Column(db.String(15), nullable=False)   # ex: 0405050372
    proc_nome     = db.Column(db.String(200))
    valor_unit    = db.Column(db.Numeric(12, 2), default=0)
    valor_total   = db.Column(db.Numeric(12, 2), default=0)
    competencia_ini = db.Column(db.String(6))                  # AAAAMM
    competencia_fim = db.Column(db.String(6))
    ativo         = db.Column(db.Boolean, default=True)
    criado_em     = db.Column(db.DateTime, default=datetime.utcnow)

    realizados = db.relationship("RealizadoFederal", backref="pactuacao", cascade="all, delete-orphan")

    @property
    def qtd_fisica(self):
        vu = float(self.valor_unit or 0)
        vt = float(self.valor_total or 0)
        return round(vt / vu, 2) if vu > 0 else 0

    @property
    def total_realizado_qtd(self):
        return sum(int(r.qtd_realizada or 0) for r in self.realizados)

    @property
    def total_realizado_val(self):
        return sum(float(r.val_realizado or 0) for r in self.realizados)

    @property
    def pct_execucao(self):
        vt = float(self.valor_total or 0)
        return round(self.total_realizado_val / vt * 100, 1) if vt > 0 else 0


class RealizadoFederal(db.Model):
    """Lançamento mensal de produção realizada por item da pactuação federal."""
    __tablename__ = "realizados_federais"
    id              = db.Column(db.Integer, primary_key=True)
    pactuacao_id    = db.Column(db.Integer, db.ForeignKey("pactuacoes_federais.id"), nullable=False)
    competencia     = db.Column(db.String(6), nullable=False)
    qtd_realizada   = db.Column(db.Integer, default=0)
    val_realizado   = db.Column(db.Numeric(12, 2), default=0)
    observacao      = db.Column(db.Text)
    criado_em       = db.Column(db.DateTime, default=datetime.utcnow)
    atualizado_em   = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint("pactuacao_id", "competencia", name="uq_realizado_fed"),)


class AuditLog(db.Model):
    """Registro de auditoria — quem fez o quê e quando."""
    __tablename__ = "audit_log"
    id          = db.Column(db.Integer, primary_key=True)
    usuario_id  = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=True)
    usuario_nom = db.Column(db.String(100))          # nome gravado na hora (mesmo se user deletado)
    acao        = db.Column(db.String(20))            # criar | editar | excluir
    entidade    = db.Column(db.String(50))            # licenca | item_contrato | pactuacao | ...
    entidade_id = db.Column(db.Integer)
    descricao   = db.Column(db.Text)                 # resumo legível da alteração
    criado_em   = db.Column(db.DateTime, default=datetime.utcnow)

    usuario = db.relationship("Usuario", foreign_keys=[usuario_id])


class EscalaMedica(db.Model):
    """Escala mensal de atendimento por médico/procedimento (ofícios à Vigilância)."""
    __tablename__ = "escalas_medicas"
    id          = db.Column(db.Integer, primary_key=True)
    competencia = db.Column(db.String(6), nullable=False)   # YYYYMM
    medico      = db.Column(db.String(150), nullable=False)
    procedimento = db.Column(db.String(200), nullable=False)
    dias        = db.Column(db.String(120))                  # "3,10,17,24,31"
    turno       = db.Column(db.String(20))                   # Manhã | Tarde
    horario     = db.Column(db.String(20))                   # "07:30"
    qtd_vagas   = db.Column(db.Integer, default=0)
    observacao  = db.Column(db.Text)
    criado_em   = db.Column(db.DateTime, default=datetime.utcnow)


class ExecucaoDiaria(db.Model):
    """Produção executada por dia — conferência contra a escala médica."""
    __tablename__ = "execucoes_diarias"
    id            = db.Column(db.Integer, primary_key=True)
    competencia   = db.Column(db.String(6), nullable=False, index=True)  # YYYYMM
    dia           = db.Column(db.Integer, nullable=False)                # 1-31
    medico        = db.Column(db.String(150), nullable=False)
    procedimento  = db.Column(db.String(200), nullable=False)
    qtd_agendada  = db.Column(db.Integer)                    # agendado pelo SMS
    qtd_executada = db.Column(db.Integer, default=0)
    observacao    = db.Column(db.Text)
    criado_em     = db.Column(db.DateTime, default=datetime.utcnow)
    atualizado_em = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint("competencia", "dia", "medico", "procedimento",
                                          name="uq_exec_diaria"),)


class SIAArquivo(db.Model):
    """Controla quais arquivos DBC já foram importados."""
    __tablename__ = "sia_arquivos"
    id          = db.Column(db.Integer, primary_key=True)
    nome        = db.Column(db.String(20), unique=True, nullable=False)  # PACE2604
    competencia = db.Column(db.String(6))
    importado_em = db.Column(db.DateTime, default=datetime.utcnow)
    registros   = db.Column(db.Integer, default=0)
