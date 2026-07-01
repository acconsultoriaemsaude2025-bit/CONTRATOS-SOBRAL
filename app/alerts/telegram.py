import requests
from config import Config


def enviar(texto):
    token = Config.TELEGRAM_BOT_TOKEN
    chat_id = Config.TELEGRAM_CHAT_ID
    if not token or not chat_id:
        print("[alerta] Telegram não configurado.")
        print(texto)
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    r = requests.post(
        url,
        json={"chat_id": chat_id, "text": texto, "parse_mode": "HTML", "disable_web_page_preview": True},
        timeout=20,
    )
    return r.ok


def formatar_novidades(novidades):
    if not novidades:
        return None
    linhas = ["<b>Movimentação nova nos contratos monitorados</b>", ""]
    for tipo, empenho, reg in novidades:
        contrato = empenho.contrato.numero if empenho.contrato else "?"
        forn = empenho.contrato.fornecedor if empenho.contrato else ""
        valor = f"R$ {float(reg.valor or 0):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        data = reg.data.strftime("%d/%m/%Y") if reg.data else "—"
        if tipo == "liquidacao":
            linhas.append(f"• <b>Liquidação</b> {valor} — {data}")
        else:
            linhas.append(f"• <b>Pagamento</b> {valor} — {data}")
        linhas.append(f"  Empenho {empenho.numero} · Contrato {contrato}")
        if forn:
            linhas.append(f"  {forn}")
        linhas.append("")
    return "\n".join(linhas).strip()
