import requests
import os
import pandas as pd
from datetime import datetime, timedelta, timezone

# ==================== CONFIGURAÇÕES ====================
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
ARQUIVO = "barragens.csv"
ARQ_UPDATE = "last_update.txt"

# ==================== TELEGRAM ====================
def enviar_telegram(mensagem, chat_id=CHAT_ID):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": mensagem, "parse_mode": "Markdown"}
    requests.post(url, json=payload, timeout=15)

def ler_ultima_mensagem():
    url = f"https://api.telegram.org/bot{TOKEN}/getUpdates"
    res = requests.get(url, timeout=15).json()

    if not res.get("result"):
        return None

    ultima = res["result"][-1]
    texto = ultima.get("message", {}).get("text", "").lower()
    chat_id = ultima.get("message", {}).get("chat", {}).get("id")
    update_id = ultima.get("update_id")

    # Evita responder a mesma mensagem
    if os.path.exists(ARQ_UPDATE):
        if str(update_id) == open(ARQ_UPDATE).read().strip():
            return None

    with open(ARQ_UPDATE, "w") as f:
        f.write(str(update_id))

    return texto, chat_id

# ==================== CLIMA ====================
def verificar_clima(nome, lat, lon):
    url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        f"&current=precipitation"
        f"&timezone=America%2FSao_Paulo"
    )
    res = requests.get(url, timeout=15).json()
    chuva = res["current"]["precipitation"]

    return f"🌧 *{nome}:* {chuva} mm agora" if chuva > 0 else f"☀️ *{nome}:* Sem chuva agora"

# ==================== CONSULTA IMEDIATA ====================
def verificar_consulta_imediata():
    msg = ler_ultima_mensagem()
    if not msg:
        return False

    texto, chat_id = msg

    if "está chovendo agora" in texto or "esta chovendo agora" in texto:
        df = pd.read_csv(ARQUIVO)
        respostas = ["📍 *Consulta imediata*\n"]

        for _, row in df.iterrows():
            respostas.append(verificar_clima(row['nome'], row['lat'], row['long']))

        enviar_telegram("\n".join(respostas), chat_id)
        return True

    return False

# ==================== MONITOR AUTOMÁTICO ====================
def executar():
    # 1️⃣ Se for consulta imediata, responde e sai
    if verificar_consulta_imediata():
        return

    # 2️⃣ Monitor normal
    fuso_br = timezone(timedelta(hours=-3))
    agora = datetime.now(fuso_br)

    df = pd.read_csv(ARQUIVO)
    relatorio = [
        f"🛰 *RELATÓRIO BARRAGENS*",
        f"⏰ {agora.strftime('%d/%m/%Y %H:%M')}\n"
    ]

    for _, row in df.iterrows():
        relatorio.append(verificar_clima(row['nome'], row['lat'], row['long']))

    enviar_telegram("\n".join(relatorio))

if __name__ == "__main__":
    executar()
