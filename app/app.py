import click
from flask import Flask, render_template, jsonify, redirect, url_for, request, flash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from config import Config
from models import db, Usuario, Contrato, Empenho, Liquidacao, Pagamento
from scraper.sync import sync_contrato
from alerts.telegram import enviar, formatar_novidades
from sqlalchemy import func
import datetime as dt


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)

    @app.template_filter("brl")
    def brl_filter(value):
        try:
            return f"R$ {float(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        except Exception:
            return "R$ 0,00"

    @app.template_filter("format_number")
    def format_number_filter(value):
        try:
            return f"{int(value):,}".replace(",", ".")
        except Exception:
            return str(value)

    login_manager = LoginManager(app)
    login_manager.login_view = "login"
    login_manager.login_message = "Faça login para acessar."

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(Usuario, int(user_id))

    # ---------- AUTH ----------
    @app.route("/login", methods=["GET", "POST"])
    def login():
        if current_user.is_authenticated:
            return redirect(url_for("dashboard"))
        if request.method == "POST":
            email = request.form.get("email", "").strip().lower()
            senha = request.form.get("senha", "")
            u = Usuario.query.filter_by(email=email, ativo=True).first()
            if u and u.check_senha(senha):
                login_user(u, remember=True)
                return redirect(request.args.get("next") or url_for("dashboard"))
            flash("E-mail ou senha incorretos.", "erro")
        return render_template("login.html")

    @app.route("/logout")
    @login_required
    def logout():
        logout_user()
        return redirect(url_for("login"))

    # ---------- DASHBOARD ----------
    @app.route("/")
    @login_required
    def dashboard():
        contratos = Contrato.query.filter_by(ativo=True).order_by(Contrato.numero).all()
        total_emp = sum(c.total_empenhado for c in contratos)
        total_liq = sum(c.total_liquidado for c in contratos)
        total_pago = sum(c.total_pago for c in contratos)
        return render_template(
            "dashboard.html",
            contratos=contratos,
            total_emp=total_emp,
            total_liq=total_liq,
            total_pago=total_pago,
            now_date=dt.date.today(),
        )

    # ---------- PROCEDIMENTOS (SIASUS) ----------
    @app.route("/procedimentos")
    @login_required
    def procedimentos():
        from models import ProducaoSIA, SIAArquivo, SIAOrigem, SIAOrigemProc
        from scraper.siasus import TPFIN_LABELS, listar_arquivos_ftp
        from sqlalchemy import func

        # Parâmetros de filtro
        filtro_ini       = request.args.get("comp_ini", "")
        filtro_fim       = request.args.get("comp_fim", "")
        filtro_fin       = request.args.get("tpfin", "")
        filtro_proc      = request.args.get("proc", "").strip()
        filtro_municipio = request.args.get("municipio", "").strip()

        # Competências disponíveis no banco
        comps_q = db.session.query(ProducaoSIA.competencia).distinct().order_by(ProducaoSIA.competencia).all()
        competencias = [c[0] for c in comps_q]
        ultima_comp  = competencias[-1] if competencias else None

        # Lista de municípios para o select (todos os períodos)
        mun_q = (db.session.query(
                    SIAOrigem.municipio_cod,
                    SIAOrigem.municipio_nom,
                    func.sum(SIAOrigem.qtd_aprovada).label("qtd"))
                 .group_by(SIAOrigem.municipio_cod, SIAOrigem.municipio_nom)
                 .order_by(func.sum(SIAOrigem.qtd_aprovada).desc()).all())
        municipios_origem = [{"cod": r.municipio_cod, "nom": r.municipio_nom or r.municipio_cod, "qtd": int(r.qtd or 0)} for r in mun_q]

        # Query base — se filtrar por município usa SIAOrigemProc
        if filtro_municipio:
            # Subquery: proc_ids/tpfin daquele município
            sub = (db.session.query(
                        SIAOrigemProc.proc_id,
                        SIAOrigemProc.tpfin,
                        func.sum(SIAOrigemProc.qtd_produzida).label("qtd_prod"),
                        func.sum(SIAOrigemProc.qtd_aprovada).label("qtd_apr"),
                        func.sum(SIAOrigemProc.val_produzido).label("val_prod"),
                        func.sum(SIAOrigemProc.val_aprovado).label("val_apr"),
                   ).filter(SIAOrigemProc.municipio_cod == filtro_municipio)
                   .group_by(SIAOrigemProc.proc_id, SIAOrigemProc.tpfin))
            if filtro_ini:
                sub = sub.filter(SIAOrigemProc.competencia >= filtro_ini)
            if filtro_fim:
                sub = sub.filter(SIAOrigemProc.competencia <= filtro_fim)
            if filtro_fin:
                sub = sub.filter(SIAOrigemProc.tpfin == filtro_fin)
            raw_sub = sub.order_by(func.sum(SIAOrigemProc.val_aprovado).desc()).all()

            # Monta rows a partir do sub com nome do procedimento
            nome_map = {r.proc_id: r.nome_proc for r in db.session.query(ProducaoSIA.proc_id, ProducaoSIA.nome_proc).distinct().all()}
            rows = []
            class Row: pass
            for r in raw_sub:
                if filtro_proc and filtro_proc.lower() not in r.proc_id.lower() and filtro_proc.lower() not in (nome_map.get(r.proc_id) or "").lower():
                    continue
                ro = Row()
                ro.proc_id   = r.proc_id
                ro.nome_proc = nome_map.get(r.proc_id, r.proc_id)
                ro.tpfin     = r.tpfin
                ro.subfin    = ""
                ro.qtd_prod  = int(r.qtd_prod or 0)
                ro.qtd_apr   = int(r.qtd_apr  or 0)
                ro.val_prod  = float(r.val_prod or 0)
                ro.val_apr   = float(r.val_apr  or 0)
                ro.competencias = []
                rows.append(ro)
        else:
            q = db.session.query(
                ProducaoSIA.proc_id,
                ProducaoSIA.nome_proc,
                ProducaoSIA.tpfin,
                ProducaoSIA.subfin,
                func.sum(ProducaoSIA.qtd_produzida).label("qtd_prod"),
                func.sum(ProducaoSIA.qtd_aprovada).label("qtd_apr"),
                func.sum(ProducaoSIA.val_produzido).label("val_prod"),
                func.sum(ProducaoSIA.val_aprovado).label("val_apr"),
                func.group_concat(ProducaoSIA.competencia).label("comps_raw"),
            ).group_by(ProducaoSIA.proc_id, ProducaoSIA.nome_proc, ProducaoSIA.tpfin, ProducaoSIA.subfin)

            if filtro_ini:
                q = q.filter(ProducaoSIA.competencia >= filtro_ini)
            if filtro_fim:
                q = q.filter(ProducaoSIA.competencia <= filtro_fim)
            if filtro_fin:
                q = q.filter(ProducaoSIA.tpfin == filtro_fin)
            if filtro_proc:
                q = q.filter(
                    db.or_(
                        ProducaoSIA.proc_id.ilike(f"%{filtro_proc}%"),
                        ProducaoSIA.nome_proc.ilike(f"%{filtro_proc}%"),
                    )
                )

            raw = q.order_by(func.sum(ProducaoSIA.val_aprovado).desc()).all()

            class Row:
                pass
            rows = []
            for r in raw:
                ro = Row()
                ro.proc_id   = r.proc_id
                ro.nome_proc = r.nome_proc
                ro.tpfin     = r.tpfin
                ro.subfin    = r.subfin
                ro.qtd_prod  = int(r.qtd_prod or 0)
                ro.qtd_apr   = int(r.qtd_apr  or 0)
                ro.val_prod  = float(r.val_prod or 0)
                ro.val_apr   = float(r.val_apr  or 0)
                ro.competencias = sorted(set((r.comps_raw or "").split(",")))
                rows.append(ro)

        # Totais
        total_qtd_prod = sum(r.qtd_prod for r in rows)
        total_qtd_apr  = sum(r.qtd_apr  for r in rows)
        total_val_prod = sum(r.val_prod for r in rows)
        total_val_apr  = sum(r.val_apr  for r in rows)
        total_procs    = len(set(r.proc_id for r in rows))
        taxa_apr = (total_qtd_apr / total_qtd_prod * 100) if total_qtd_prod else 0

        # Dados para gráfico mensal
        mensal_q = (db.session.query(ProducaoSIA.competencia,
                        func.sum(ProducaoSIA.val_aprovado))
                    .group_by(ProducaoSIA.competencia)
                    .order_by(ProducaoSIA.competencia).all())
        mensal_labels = [f"{c[:4]}/{c[4:]}" for c,_ in mensal_q]
        mensal_val    = [float(v or 0) for _,v in mensal_q]

        # Dados para gráfico por financiamento
        fin_q = (db.session.query(ProducaoSIA.tpfin,
                     func.sum(ProducaoSIA.qtd_aprovada))
                 .group_by(ProducaoSIA.tpfin)
                 .order_by(func.sum(ProducaoSIA.qtd_aprovada).desc()).all())
        fin_labels = [f"{TPFIN_LABELS.get(t,t)} ({t})" for t,_ in fin_q]
        fin_qtd    = [int(v or 0) for _,v in fin_q]

        # Top 10 por valor aprovado
        top10 = sorted(rows, key=lambda r: r.val_apr, reverse=True)[:10]
        top10_labels = [f"{r.proc_id}\n{(r.nome_proc or '')[:30]}" for r in top10]
        top10_val    = [r.val_apr for r in top10]

        # Origem dos pacientes — usa SIAOrigemProc quando há filtro de financiamento ou proc
        # pois SIAOrigem não tem coluna tpfin
        if filtro_fin or filtro_proc:
            orig_q = db.session.query(
                SIAOrigemProc.municipio_cod,
                func.sum(SIAOrigemProc.qtd_aprovada).label("qtd"),
                func.sum(SIAOrigemProc.val_aprovado).label("val"),
            ).group_by(SIAOrigemProc.municipio_cod)
            if filtro_ini:
                orig_q = orig_q.filter(SIAOrigemProc.competencia >= filtro_ini)
            if filtro_fim:
                orig_q = orig_q.filter(SIAOrigemProc.competencia <= filtro_fim)
            if filtro_fin:
                orig_q = orig_q.filter(SIAOrigemProc.tpfin == filtro_fin)
            if filtro_proc:
                orig_q = orig_q.filter(SIAOrigemProc.proc_id == filtro_proc)
            if filtro_municipio:
                orig_q = orig_q.filter(SIAOrigemProc.municipio_cod == filtro_municipio)
            # Resolve nomes via join com SIAOrigem (qualquer competência)
            raw_orig = orig_q.order_by(func.sum(SIAOrigemProc.val_aprovado).desc()).all()
            # Busca nomes dos municípios
            nomes_mun = {r.municipio_cod: r.municipio_nom
                         for r in SIAOrigem.query.with_entities(
                             SIAOrigem.municipio_cod, SIAOrigem.municipio_nom
                         ).group_by(SIAOrigem.municipio_cod).all()}
            from collections import namedtuple
            OrigRow = namedtuple("OrigRow", ["municipio_cod", "municipio_nom", "qtd", "val"])
            origem_rows = [OrigRow(r.municipio_cod,
                                   nomes_mun.get(r.municipio_cod, r.municipio_cod),
                                   r.qtd, r.val) for r in raw_orig]
        else:
            orig_q = db.session.query(
                SIAOrigem.municipio_cod,
                SIAOrigem.municipio_nom,
                func.sum(SIAOrigem.qtd_aprovada).label("qtd"),
                func.sum(SIAOrigem.val_aprovado).label("val"),
            ).group_by(SIAOrigem.municipio_cod, SIAOrigem.municipio_nom)
            if filtro_ini:
                orig_q = orig_q.filter(SIAOrigem.competencia >= filtro_ini)
            if filtro_fim:
                orig_q = orig_q.filter(SIAOrigem.competencia <= filtro_fim)
            if filtro_municipio:
                orig_q = orig_q.filter(SIAOrigem.municipio_cod == filtro_municipio)
            origem_rows = orig_q.order_by(func.sum(SIAOrigem.qtd_aprovada).desc()).all()

        # Verifica arquivos novos no FTP
        arquivos_novos = []
        try:
            from models import SIAArquivo
            importados = {a.nome for a in SIAArquivo.query.all()}
            disponiveis = listar_arquivos_ftp()
            arquivos_novos = [n for n in disponiveis if n >= "PACE2508" and n not in importados]
        except Exception:
            pass

        return render_template(
            "procedimentos.html",
            competencias=competencias,
            filtro_ini=filtro_ini, filtro_fim=filtro_fim,
            filtro_fin=filtro_fin, filtro_proc=filtro_proc,
            rows=rows,
            total_qtd_prod=total_qtd_prod, total_qtd_apr=total_qtd_apr,
            total_val_prod=total_val_prod, total_val_apr=total_val_apr,
            total_procs=total_procs, taxa_apr=taxa_apr,
            mensal_labels=mensal_labels, mensal_val=mensal_val,
            fin_labels=fin_labels, fin_qtd=fin_qtd,
            top10_labels=top10_labels, top10_val=top10_val,
            tpfin_opts=TPFIN_LABELS,
            ultima_comp=ultima_comp,
            arquivos_importados=bool(competencias),
            arquivos_novos=arquivos_novos,
            origem_rows=origem_rows,
            municipios_origem=municipios_origem,
            filtro_municipio=filtro_municipio,
        )

    @app.route("/procedimentos/sync", methods=["POST"])
    @login_required
    def procedimentos_sync():
        if not current_user.admin:
            flash("Acesso negado.", "erro")
            return redirect(url_for("procedimentos"))
        from scraper.siasus import sincronizar_novos
        resultados = sincronizar_novos(app.app_context())
        for nome, n in resultados:
            if n >= 0:
                flash(f"{nome}: {n} linhas importadas.", "ok")
            else:
                flash(f"{nome}: erro na importação.", "erro")
        if not resultados:
            flash("Nenhum arquivo novo encontrado.", "ok")
        return redirect(url_for("procedimentos"))

    # ---------- CONTRATO DETALHE ----------
    @app.route("/contrato/<path:numero>")
    @login_required
    def detalhe_contrato(numero):
        c = Contrato.query.filter_by(numero=numero).first_or_404()
        empenhos = sorted(c.empenhos, key=lambda e: (e.data or dt.date.min), reverse=True)
        return render_template("contrato.html", c=c, empenhos=empenhos, hoje_date=dt.date.today())

    # ---------- GESTÃO DE CONTRATOS (admin) ----------
    @app.route("/admin/contratos")
    @login_required
    def admin_contratos():
        if not current_user.admin:
            flash("Acesso negado.", "erro")
            return redirect(url_for("dashboard"))
        contratos = Contrato.query.order_by(Contrato.numero).all()
        return render_template("admin_contratos.html", contratos=contratos)

    @app.route("/admin/contratos/add", methods=["POST"])
    @login_required
    def admin_add_contrato():
        if not current_user.admin:
            return jsonify({"erro": "Acesso negado"}), 403
        numero = request.form.get("numero", "").strip()
        orgao = request.form.get("orgao", "").strip()
        if not numero or not orgao:
            flash("Número e órgão são obrigatórios.", "erro")
            return redirect(url_for("admin_contratos"))
        c = Contrato.query.filter_by(numero=numero).first()
        if not c:
            c = Contrato(numero=numero, orgao=orgao, ativo=True)
            db.session.add(c)
        else:
            c.orgao, c.ativo = orgao, True
        db.session.commit()
        flash(f"Contrato {numero} adicionado. Rode a sincronização.", "ok")
        return redirect(url_for("admin_contratos"))

    @app.route("/admin/contratos/<int:cid>/toggle", methods=["POST"])
    @login_required
    def admin_toggle_contrato(cid):
        if not current_user.admin:
            return jsonify({"erro": "Acesso negado"}), 403
        c = db.session.get(Contrato, cid)
        if c:
            c.ativo = not c.ativo
            db.session.commit()
        return redirect(url_for("admin_contratos"))

    @app.route("/admin/usuarios")
    @login_required
    def admin_usuarios():
        if not current_user.admin:
            flash("Acesso negado.", "erro")
            return redirect(url_for("dashboard"))
        usuarios = Usuario.query.order_by(Usuario.nome).all()
        return render_template("admin_usuarios.html", usuarios=usuarios)

    @app.route("/admin/usuarios/add", methods=["POST"])
    @login_required
    def admin_add_usuario():
        if not current_user.admin:
            return jsonify({"erro": "Acesso negado"}), 403
        nome = request.form.get("nome", "").strip()
        email = request.form.get("email", "").strip().lower()
        senha = request.form.get("senha", "")
        admin = request.form.get("admin") == "1"
        if not nome or not email or not senha:
            flash("Nome, e-mail e senha são obrigatórios.", "erro")
            return redirect(url_for("admin_usuarios"))
        if Usuario.query.filter_by(email=email).first():
            flash("E-mail já cadastrado.", "erro")
            return redirect(url_for("admin_usuarios"))
        u = Usuario(nome=nome, email=email, admin=admin)
        u.set_senha(senha)
        db.session.add(u)
        db.session.commit()
        flash(f"Usuário {nome} criado.", "ok")
        return redirect(url_for("admin_usuarios"))

    @app.route("/admin/usuarios/<int:uid>/toggle", methods=["POST"])
    @login_required
    def admin_toggle_usuario(uid):
        if not current_user.admin:
            return jsonify({"erro": "Acesso negado"}), 403
        u = db.session.get(Usuario, uid)
        if u and u.id != current_user.id:
            u.ativo = not u.ativo
            db.session.commit()
        return redirect(url_for("admin_usuarios"))

    # ---------- API JSON ----------
    @app.route("/api/resumo")
    @login_required
    def api_resumo():
        contratos = Contrato.query.filter_by(ativo=True).all()
        return jsonify(
            [
                {
                    "numero": c.numero,
                    "fornecedor": c.fornecedor or "",
                    "cnpj": c.cnpj or "",
                    "objeto": (c.objeto or "")[:80],
                    "status": c.status,
                    "valor_inicial": float(c.valor_inicial or 0),
                    "empenhado": c.total_empenhado,
                    "liquidado": c.total_liquidado,
                    "pago": c.total_pago,
                    "pct_pago": c.pct_pago,
                    "n_empenhos": len(c.empenhos),
                    "data_final": c.data_final.isoformat() if c.data_final else None,
                }
                for c in contratos
            ]
        )

    @app.route("/api/contrato/<path:numero>")
    @login_required
    def api_contrato(numero):
        c = Contrato.query.filter_by(numero=numero).first_or_404()
        return jsonify(
            {
                "numero": c.numero,
                "fornecedor": c.fornecedor,
                "objeto": c.objeto,
                "status": c.status,
                "empenhos": [
                    {
                        "numero": e.numero,
                        "data": e.data.isoformat() if e.data else None,
                        "empenhado": float(e.valor_empenhado or 0),
                        "liquidado": e.total_liquidado,
                        "pago": e.total_pago,
                        "liquidacoes": [
                            {"cod": l.cod_liquidacao, "data": l.data.isoformat() if l.data else None, "valor": float(l.valor or 0)}
                            for l in e.liquidacoes
                        ],
                        "pagamentos": [
                            {"doc": p.doc, "data": p.data.isoformat() if p.data else None, "valor": float(p.valor or 0)}
                            for p in e.pagamentos
                        ],
                    }
                    for e in sorted(c.empenhos, key=lambda e: e.data or dt.date.min, reverse=True)
                ],
            }
        )

    @app.route("/api/timeline")
    @login_required
    def api_timeline():
        rows = (
            db.session.query(
                func.date_trunc("month", Pagamento.data).label("mes"),
                func.sum(Pagamento.valor).label("total"),
            )
            .filter(Pagamento.data.isnot(None))
            .group_by("mes")
            .order_by("mes")
            .all()
        )
        return jsonify(
            [{"mes": r.mes.strftime("%Y-%m") if r.mes else None, "pago": float(r.total or 0)} for r in rows]
        )

    # ---------- ITENS DO CONTRATO ----------
    @app.route("/itens-contrato")
    @login_required
    def itens_contrato():
        from models import ItemContrato, LancamentoItem
        db.create_all()
        itens = ItemContrato.query.filter_by(ativo=True).order_by(ItemContrato.ordem, ItemContrato.id).all()
        grupos = {}
        for it in itens:
            grupos.setdefault(it.forma_org or "Outros", []).append(it)

        # Competências (12 meses anteriores)
        hoje = dt.date.today()
        comps = []
        for i in range(12):
            m = hoje.month - i
            y = hoje.year
            while m <= 0:
                m += 12; y -= 1
            comps.append(f"{y}{m:02d}")

        # Competência selecionada (padrão = mês atual)
        comp_sel = request.args.get("comp", comps[0])
        if comp_sel not in comps:
            comp_sel = comps[0]

        # Lançamentos do mês selecionado: {item_id: LancamentoItem}
        lancs = LancamentoItem.query.filter_by(competencia=comp_sel).all()
        lancamentos_mes = {l.item_id: l for l in lancs}

        total_meta    = sum(float(it.meta_anual_val or 0) for it in itens)
        total_real    = sum(it.total_realizado_val for it in itens)
        total_mes_qtd = sum(l.qtd_realizada or 0 for l in lancs)
        total_mes_val = sum(float(l.val_realizado or 0) for l in lancs)
        return render_template("itens_contrato.html",
            itens=itens, grupos=grupos,
            competencias_disp=comps, comp_sel=comp_sel,
            lancamentos_mes=lancamentos_mes,
            total_meta=total_meta, total_real=total_real,
            total_mes_qtd=total_mes_qtd, total_mes_val=total_mes_val,
            hoje=hoje)

    @app.route("/itens-contrato/add", methods=["POST"])
    @login_required
    def item_contrato_add():
        from models import ItemContrato
        if not current_user.admin:
            flash("Acesso negado.", "erro")
            return redirect(url_for("itens_contrato"))
        it = ItemContrato(
            contrato_nome=request.form.get("contrato_nome", "Contrato Estado CE").strip(),
            forma_org=request.form.get("forma_org", "").strip(),
            cod_catalogo=request.form.get("cod_catalogo", "").strip(),
            cod_sigtap=request.form.get("cod_sigtap", "").strip(),
            descricao=request.form.get("descricao", "").strip(),
            valor_unit=request.form.get("valor_unit", 0) or 0,
            meta_anual_val=request.form.get("meta_anual_val", 0) or 0,
            ordem=int(request.form.get("ordem", 0) or 0),
        )
        db.session.add(it)
        db.session.commit()
        flash(f"Procedimento '{it.descricao[:40]}' cadastrado.", "ok")
        return redirect(url_for("itens_contrato"))

    @app.route("/itens-contrato/<int:iid>/edit", methods=["GET", "POST"])
    @login_required
    def item_contrato_edit(iid):
        from models import ItemContrato
        if not current_user.admin:
            flash("Acesso negado.", "erro")
            return redirect(url_for("itens_contrato"))
        it = db.session.get(ItemContrato, iid) or ItemContrato.query.get_or_404(iid)
        if request.method == "POST":
            it.contrato_nome = request.form.get("contrato_nome", it.contrato_nome).strip()
            it.forma_org     = request.form.get("forma_org", "").strip()
            it.cod_catalogo  = request.form.get("cod_catalogo", "").strip()
            it.cod_sigtap    = request.form.get("cod_sigtap", "").strip()
            it.descricao     = request.form.get("descricao", "").strip()
            it.valor_unit    = request.form.get("valor_unit", 0) or 0
            it.meta_anual_val = request.form.get("meta_anual_val", 0) or 0
            it.ordem         = int(request.form.get("ordem", 0) or 0)
            db.session.commit()
            flash("Procedimento atualizado.", "ok")
            return redirect(url_for("itens_contrato"))
        return render_template("item_contrato_edit.html", it=it)

    @app.route("/itens-contrato/<int:iid>/delete", methods=["POST"])
    @login_required
    def item_contrato_delete(iid):
        from models import ItemContrato
        if not current_user.admin:
            flash("Acesso negado.", "erro")
            return redirect(url_for("itens_contrato"))
        it = db.session.get(ItemContrato, iid)
        if it:
            db.session.delete(it)
            db.session.commit()
            flash("Procedimento removido.", "ok")
        return redirect(url_for("itens_contrato"))

    @app.route("/itens-contrato/lancar", methods=["POST"])
    @login_required
    def item_contrato_lancar():
        from models import ItemContrato, LancamentoItem
        item_id    = int(request.form.get("item_id", 0))
        competencia = request.form.get("competencia", "").strip()
        qtd        = int(request.form.get("qtd_realizada", 0) or 0)
        val_str    = request.form.get("val_realizado", "").strip()
        try:
            val = float(val_str) if val_str else 0
        except Exception:
            val = 0
        obs = request.form.get("observacao", "").strip()

        if not item_id or not competencia:
            flash("Dados inválidos.", "erro")
            return redirect(url_for("itens_contrato"))

        lanc = LancamentoItem.query.filter_by(item_id=item_id, competencia=competencia).first()
        if lanc:
            lanc.qtd_realizada = qtd
            lanc.val_realizado = val
            lanc.observacao    = obs
        else:
            lanc = LancamentoItem(item_id=item_id, competencia=competencia,
                                  qtd_realizada=qtd, val_realizado=val, observacao=obs)
            db.session.add(lanc)
        db.session.commit()
        flash("Lançamento salvo.", "ok")
        return redirect(url_for("itens_contrato"))

    @app.route("/itens-contrato/lancar-lote", methods=["POST"])
    @login_required
    def item_contrato_lancar_lote():
        """Salva múltiplos lançamentos de uma vez (formulário em lote)."""
        from models import ItemContrato, LancamentoItem
        competencia = request.form.get("competencia_lote", "").strip()
        if not competencia:
            flash("Selecione a competência.", "erro")
            return redirect(url_for("itens_contrato"))
        itens = ItemContrato.query.filter_by(ativo=True).all()
        salvos = 0
        for it in itens:
            qtd_key = f"qtd_{it.id}"
            val_key = f"val_{it.id}"
            obs_key = f"obs_{it.id}"
            qtd_str = request.form.get(qtd_key, "").strip()
            val_str = request.form.get(val_key, "").strip()
            obs     = request.form.get(obs_key, "").strip()
            if not qtd_str and not val_str:
                continue
            qtd = int(qtd_str) if qtd_str else 0
            try:
                val = float(val_str) if val_str else round(qtd * float(it.valor_unit or 0), 2)
            except Exception:
                val = 0
            lanc = LancamentoItem.query.filter_by(item_id=it.id, competencia=competencia).first()
            if lanc:
                lanc.qtd_realizada = qtd; lanc.val_realizado = val; lanc.observacao = obs
            else:
                lanc = LancamentoItem(item_id=it.id, competencia=competencia,
                                      qtd_realizada=qtd, val_realizado=val, observacao=obs)
                db.session.add(lanc)
            salvos += 1
        db.session.commit()
        flash(f"Competência {competencia[:4]}/{competencia[4:]}: {salvos} lançamentos salvos.", "ok")
        return redirect(url_for("itens_contrato"))

    # ---------- ELETIVAS FEDERAIS ----------
    @app.route("/eletivas-federais")
    @login_required
    def eletivas_federais():
        from models import PactuacaoFederal, RealizadoFederal
        pactuacoes = PactuacaoFederal.query.filter_by(ativo=True).order_by(
            PactuacaoFederal.municipio, PactuacaoFederal.proc_cod).all()

        # Competências disponíveis jul–dez/2026
        competencias_disp = ["202607","202608","202609","202610","202611","202612"]
        comp_sel = request.args.get("comp", competencias_disp[0])

        # Lançamentos do mês selecionado
        realizados_mes = {r.pactuacao_id: r for r in
            RealizadoFederal.query.filter_by(competencia=comp_sel).all()}

        por_municipio = {}
        for p in pactuacoes:
            por_municipio.setdefault(p.municipio, []).append(p)

        total_val      = sum(float(p.valor_total or 0) for p in pactuacoes)
        total_qtd      = sum(p.qtd_fisica for p in pactuacoes)
        total_real_val = sum(float(p.total_realizado_val) for p in pactuacoes)
        total_real_qtd = sum(p.total_realizado_qtd for p in pactuacoes)
        total_mes_qtd  = sum(r.qtd_realizada or 0 for r in realizados_mes.values())
        total_mes_val  = sum(float(r.val_realizado or 0) for r in realizados_mes.values())

        # Evolução mensal (val realizado por competência)
        todos_realizados = RealizadoFederal.query.all()
        evolucao_mensal = {}
        for c in competencias_disp:
            evolucao_mensal[c] = sum(float(r.val_realizado or 0)
                                     for r in todos_realizados if r.competencia == c)

        # Execução por procedimento (faco vs caps)
        FACO_COD = "0405050372"
        CAPS_COD = "0405050020"
        procs_dash = {
            FACO_COD: {"nome": "Facoemulsificação", "pac_val": 0, "pac_qtd": 0, "real_val": 0, "real_qtd": 0},
            CAPS_COD: {"nome": "Capsulotomia YAG Laser", "pac_val": 0, "pac_qtd": 0, "real_val": 0, "real_qtd": 0},
        }
        for p in pactuacoes:
            if p.proc_cod in procs_dash:
                procs_dash[p.proc_cod]["pac_val"]  += float(p.valor_total or 0)
                procs_dash[p.proc_cod]["pac_qtd"]  += p.qtd_fisica
                procs_dash[p.proc_cod]["real_val"] += p.total_realizado_val
                procs_dash[p.proc_cod]["real_qtd"] += p.total_realizado_qtd

        # Execução por município (resumo para dash)
        dash_municipios = []
        for mun, itens in por_municipio.items():
            pac_v  = sum(float(i.valor_total or 0) for i in itens)
            real_v = sum(i.total_realizado_val for i in itens)
            dash_municipios.append({
                "nome": mun,
                "pac_val": pac_v,
                "real_val": real_v,
                "pct": round(real_v / pac_v * 100, 1) if pac_v else 0,
            })
        dash_municipios.sort(key=lambda x: x["pac_val"], reverse=True)

        return render_template("eletivas_federais.html",
            pactuacoes=pactuacoes,
            por_municipio=por_municipio,
            total_val=total_val,
            total_qtd=total_qtd,
            total_real_val=total_real_val,
            total_real_qtd=total_real_qtd,
            total_mes_qtd=total_mes_qtd,
            total_mes_val=total_mes_val,
            competencias_disp=competencias_disp,
            comp_sel=comp_sel,
            realizados_mes=realizados_mes,
            evolucao_mensal=evolucao_mensal,
            procs_dash=procs_dash,
            dash_municipios=dash_municipios)

    @app.route("/eletivas-federais/lancar", methods=["POST"])
    @login_required
    def eletivas_lancar():
        from models import PactuacaoFederal, RealizadoFederal
        data = request.get_json(force=True)
        comp = data.get("competencia", "").strip()
        lancamentos = data.get("lancamentos", [])
        if not comp:
            return jsonify({"ok": False, "msg": "Competência inválida"}), 400

        for item in lancamentos:
            pid = int(item.get("pactuacao_id", 0))
            qtd = int(item.get("qtd", 0) or 0)
            pac = PactuacaoFederal.query.get(pid)
            if not pac:
                continue
            val = round(float(pac.valor_unit or 0) * qtd, 2)
            r = RealizadoFederal.query.filter_by(pactuacao_id=pid, competencia=comp).first()
            if r:
                r.qtd_realizada = qtd
                r.val_realizado = val
            else:
                r = RealizadoFederal(pactuacao_id=pid, competencia=comp,
                                     qtd_realizada=qtd, val_realizado=val)
                db.session.add(r)
        db.session.commit()
        return jsonify({"ok": True})

    # ---------- LICENÇAS / ALVARÁS ----------
    @app.route("/licencas")
    @login_required
    def licencas():
        from models import Licenca
        hoje = dt.date.today()
        todas = Licenca.query.order_by(Licenca.data_vencimento).all()

        vencidas  = [l for l in todas if l.status_alerta == "vencida"]
        em_alerta = [l for l in todas if l.status_alerta == "alerta"]
        vigentes  = [l for l in todas if l.status_alerta == "ok"]
        sem_venc  = [l for l in todas if l.status_alerta == "sem_vencimento"]

        categorias = sorted({l.categoria for l in todas if l.categoria})
        return render_template(
            "licencas.html",
            todas=todas, vencidas=vencidas,
            em_alerta=em_alerta, vigentes=vigentes, sem_venc=sem_venc,
            categorias=categorias, hoje=hoje,
        )

    @app.route("/licencas/add", methods=["POST"])
    @login_required
    def licenca_add():
        from models import Licenca
        import os
        l = Licenca(
            tipo              = request.form.get("tipo", "").strip(),
            categoria         = request.form.get("categoria", "").strip(),
            orgao_emissor     = request.form.get("orgao_emissor", "").strip(),
            numero            = request.form.get("numero", "").strip(),
            situacao          = request.form.get("situacao", "vigente"),
            dias_antecedencia = int(request.form.get("dias_antecedencia") or 90),
            observacoes       = request.form.get("observacoes", "").strip(),
        )
        emissao = request.form.get("data_emissao")
        vencimento = request.form.get("data_vencimento")
        if emissao:
            l.data_emissao = dt.date.fromisoformat(emissao)
        if vencimento:
            l.data_vencimento = dt.date.fromisoformat(vencimento)

        arq = request.files.get("arquivo")
        if arq and arq.filename:
            l.arquivo_nome  = arq.filename
            l.arquivo_dados = arq.read()

        db.session.add(l)
        db.session.commit()
        flash(f"Licença '{l.tipo}' cadastrada.", "ok")
        return redirect(url_for("licencas"))

    @app.route("/licencas/<int:lid>/edit", methods=["GET", "POST"])
    @login_required
    def licenca_edit(lid):
        from models import Licenca
        l = db.session.get(Licenca, lid)
        if not l:
            flash("Licença não encontrada.", "erro")
            return redirect(url_for("licencas"))
        if request.method == "POST":
            l.tipo              = request.form.get("tipo", "").strip()
            l.categoria         = request.form.get("categoria", "").strip()
            l.orgao_emissor     = request.form.get("orgao_emissor", "").strip()
            l.numero            = request.form.get("numero", "").strip()
            l.situacao          = request.form.get("situacao", "vigente")
            l.dias_antecedencia = int(request.form.get("dias_antecedencia") or 90)
            l.observacoes       = request.form.get("observacoes", "").strip()
            emissao    = request.form.get("data_emissao")
            vencimento = request.form.get("data_vencimento")
            if emissao:
                l.data_emissao = dt.date.fromisoformat(emissao)
            if vencimento:
                l.data_vencimento = dt.date.fromisoformat(vencimento)
            arq = request.files.get("arquivo")
            if arq and arq.filename:
                l.arquivo_nome  = arq.filename
                l.arquivo_dados = arq.read()
            db.session.commit()
            flash(f"Licença '{l.tipo}' atualizada.", "ok")
            return redirect(url_for("licencas"))
        categorias_padrao = ["sanitario","funcionamento","ambiental","bombeiros","vigilancia","outro"]
        return render_template("licenca_edit.html", l=l, categorias_padrao=categorias_padrao)

    @app.route("/licencas/<int:lid>/delete", methods=["POST"])
    @login_required
    def licenca_delete(lid):
        from models import Licenca
        if not current_user.admin:
            flash("Acesso negado.", "erro")
            return redirect(url_for("licencas"))
        l = db.session.get(Licenca, lid)
        if l:
            db.session.delete(l)
            db.session.commit()
            flash("Licença excluída.", "ok")
        return redirect(url_for("licencas"))

    @app.route("/licencas/<int:lid>/arquivo")
    @login_required
    def licenca_arquivo(lid):
        from models import Licenca
        from flask import send_file
        import io
        l = db.session.get(Licenca, lid)
        if not l or not l.arquivo_dados:
            flash("Arquivo não encontrado.", "erro")
            return redirect(url_for("licencas"))
        return send_file(
            io.BytesIO(l.arquivo_dados),
            download_name=l.arquivo_nome,
            as_attachment=False,
        )

    # ---------- CLI ----------
    @app.cli.command("init-db")
    def init_db():
        db.create_all()
        click.echo("Tabelas criadas.")

    @app.cli.command("criar-admin")
    @click.argument("nome")
    @click.argument("email")
    @click.argument("senha")
    def criar_admin(nome, email, senha):
        """Cria o primeiro usuário administrador."""
        db.create_all()
        if Usuario.query.filter_by(email=email).first():
            click.echo("E-mail já existe.")
            return
        u = Usuario(nome=nome, email=email, admin=True)
        u.set_senha(senha)
        db.session.add(u)
        db.session.commit()
        click.echo(f"Admin '{nome}' ({email}) criado.")

    @app.cli.command("add-contrato")
    @click.argument("numero")
    @click.argument("orgao")
    def add_contrato(numero, orgao):
        c = Contrato.query.filter_by(numero=numero).first()
        if not c:
            c = Contrato(numero=numero, orgao=orgao, ativo=True)
            db.session.add(c)
        else:
            c.orgao, c.ativo = orgao, True
        db.session.commit()
        click.echo(f"Monitorando {numero} (órgão {orgao}). Rode 'flask sync'.")

    @app.cli.command("list-contratos")
    def list_contratos():
        for c in Contrato.query.order_by(Contrato.numero).all():
            flag = "ativo" if c.ativo else "inativo"
            click.echo(f"{c.numero:20} órgão {c.orgao or '?':3} [{flag}]  {c.fornecedor or ''}")

    @app.cli.command("sync")
    @click.option("--silencioso", is_flag=True)
    @click.option("--numero", default=None)
    def sync(silencioso, numero):
        q = Contrato.query.filter_by(ativo=True)
        if numero:
            q = Contrato.query.filter_by(numero=numero)
        alvos = q.all()
        if not alvos:
            click.echo("Nenhum contrato ativo.")
            return
        todas = []
        for c in alvos:
            try:
                contrato, novidades = sync_contrato(c.numero, c.orgao)
                click.echo(f"[ok] {c.numero}: empenhado R$ {contrato.total_empenhado:,.2f} | {len(novidades)} novidade(s)")
                todas += novidades
            except Exception as e:
                click.echo(f"[erro] {c.numero}: {e}")
        msg = formatar_novidades(todas)
        if msg and not silencioso:
            click.echo("Alerta enviado." if enviar(msg) else "Falha no alerta Telegram.")

    @app.cli.command("sync-sia")
    @click.option("--a-partir", default="PACE2508", show_default=True, help="Nome mínimo do arquivo ex: PACE2508")
    @click.option("--forcar", is_flag=True, help="Reimporta mesmo os já importados")
    def sync_sia(a_partir, forcar):
        """Importa produção SIASUS (BPA-I) do DATASUS. Baixa apenas arquivos novos."""
        from scraper.siasus import sincronizar_novos, listar_arquivos_ftp, processar_arquivo
        from models import SIAArquivo

        if forcar:
            disponiveis = listar_arquivos_ftp()
            alvos = [n for n in disponiveis if n >= a_partir]
        else:
            with app.app_context():
                importados = {a.nome for a in SIAArquivo.query.all()}
            disponiveis = listar_arquivos_ftp()
            alvos = [n for n in disponiveis if n >= a_partir and n not in importados]

        if not alvos:
            click.echo("Nenhum arquivo novo para importar.")
            return

        click.echo(f"Arquivos a importar: {alvos}")
        for nome in alvos:
            click.echo(f">> Processando {nome} ...")
            try:
                n = processar_arquivo(nome, app.app_context())
                click.echo(f"  [ok] {nome}: {n} linhas importadas.")
            except Exception as e:
                click.echo(f"  [erro] {nome}: {e}")

    @app.cli.command("teste-alerta")
    def teste_alerta():
        ok = enviar("✅ Teste de alerta — Monitoramento de Contratos SMS Sobral.")
        click.echo("Enviado." if ok else "Falhou (verifique TOKEN/CHAT_ID).")

    @app.cli.command("sync-ceara")
    @click.argument("numero")
    def sync_ceara(numero):
        """Sincroniza contrato do Estado do Ceará via Playwright. Ex: flask sync-ceara 1199/2025"""
        from scraper.ceara import sync_contrato_ceara
        click.echo(f"Buscando contrato {numero} no Ceará Transparente (abre navegador headless)...")
        contrato, msg = sync_contrato_ceara(numero, app.app_context())
        if contrato:
            click.echo(f"[ok] {contrato['numero']} | {contrato['fornecedor']} | R$ {contrato['valor_inicial']:,.2f}")
            click.echo(f"     Objeto: {(contrato.get('objeto') or '')[:80]}")
        else:
            click.echo(f"[erro] {msg}")

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True, port=5000)
