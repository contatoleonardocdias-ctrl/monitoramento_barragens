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
    if not mensagem: return
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": mensagem, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload, timeout=15)
    except Exception as e:
        print(f"Erro ao enviar Telegram: {e}")

def ler_ultima_mensagem():
    url = f"https://api.telegram.org/bot{TOKEN}/getUpdates"
    try:
        res = requests.get(url, timeout=15).json()
        if not res.get("result"): return None

        ultima = res["result"][-1]
        texto = ultima.get("message", {}).get("text", "").lower()
        cid = ultima.get("message", {}).get("chat", {}).get("id")
        update_id = ultima.get("update_id")

        if os.path.exists(ARQ_UPDATE):
            with open(ARQ_UPDATE, "r") as f:
                if str(update_id) == f.read().strip(): return None

        with open(ARQ_UPDATE, "w") as f:
            f.write(str(update_id))

        return texto, cid
    except:
        return None

# ==================== CLIMA (LÓGICA DE EMOJIS COMBINADOS) ====================
def verificar_clima(nome, lat, lon):
    url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        f"&current=precipitation,is_day,cloud_cover,weather_code"
        f"&hourly=precipitation"
        f"&timezone=America%2FSao_Paulo"
    )
    try:
        res = requests.get(url, timeout=15).json()
        atual = res["current"]
        chuva_agora = atual["precipitation"]
        chuva_prev = res["hourly"]["precipitation"][1] 
        
        is_day = atual["is_day"]
        nuvens = atual["cloud_cover"]
        code = atual["weather_code"]

        # 1. Define o emoji base do tempo atual
        if code in [95, 96, 99]: 
            emoji = "⛈️"
        elif chuva_agora > 0:
            emoji = "🌧️"
        else:
            if is_day:
                emoji = "☀️" if nuvens < 25 else "⛅"
            else:
                emoji = "🌙" if nuvens < 25 else "☁️"
            
            # 2. Se não chove agora mas tem PREVISÃO, combina com Alerta
            if chuva_prev > 0:
                emoji = f"{emoji}⚠️"

        # 3. Formatação do Texto
        if chuva_agora == 0 and chuva_prev == 0:
            status_texto = "SEM CHUVA"
        else:
            status_texto = f"{chuva_agora:.1f}mm agora / {chuva_prev:.1f}mm prev."

        return f"{emoji} *{nome.upper()}:* {status_texto}"

    except Exception:
        return f"❌ *{nome.upper()}:* Erro na consulta"

# ==================== PROCESSAMENTO ====================
def executar():
    fuso_sp = timezone(timedelta(hours=-3))
    agora = datetime.now(fuso_sp)
    data_formatada = agora.strftime('%d/%m/%Y %H:%M')
    
    msg_info = ler_ultima_mensagem()
    if msg_info:
        texto, cid = msg_info
        if any(k in texto for k in ["agora", "status", "chuva"]):
            df = pd.read_csv(ARQUIVO)
            respostas = ["📍 *CONSULTA SOLICITADA*", f"⏰ {data_formatada}\n"]
            for _, row in df.iterrows():
                respostas.append(verificar_clima(row['nome'], row['lat'], row['long']))
            enviar_telegram("\n".join(respostas), cid)
            return

    df = pd.read_csv(ARQUIVO)
    relatorio = ["🛰️ *RELATÓRIO BARRAGENS*", f"⏰ {data_formatada}\n"]
    for _, row in df.iterrows():
        relatorio.append(verificar_clima(row['nome'], row['lat'], row['long']))

    enviar_telegram("\n".join(relatorio))

if __name__ == "__main__":
    executar()
