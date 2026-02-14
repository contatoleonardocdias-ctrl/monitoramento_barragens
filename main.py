import requests
import os
import pandas as pd
from datetime import datetime, timedelta, timezone

# ==================== CONFIGURAÇÕES ====================
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
ARQUIVO = "barragens.csv"

def enviar_telegram(mensagem):
    if not TOKEN or not CHAT_ID:
        print("❌ ERRO: CHAT_ID ou TOKEN não configurados nos Secrets do GitHub.")
        return
    
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {
        "chat_id": str(CHAT_ID).strip(), 
        "text": mensagem, 
        "parse_mode": "Markdown"
    }
    
    try:
        res = requests.post(url, data=payload, timeout=25)
        if res.status_code == 200:
            print("✅ Relatório único enviado!")
        else:
            print(f"❌ Erro Telegram: {res.text}")
    except Exception as e:
        print(f"⚠️ Falha de rede: {e}")

def verificar_clima(nome, lat, lon):
    url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        f"&current=precipitation,is_day,cloud_cover"
        f"&timezone=America%2FSao_Paulo"
    )
    try:
        res = requests.get(url, timeout=25).json()
        atual = res["current"]
        chuva = atual["precipitation"]
        is_day = atual["is_day"]
        nuvens = atual["cloud_cover"]

        if chuva > 0:
            # Modelo de alerta para quando há chuva
            status_formatado = f"⚠️ **ALERTA DE CHUVA**\n🌧️ **Tempo Real:** Está chovendo {chuva:.1f}mm agora!"
        else:
            # Status simples para quando não há chuva
            emoji = "☀️" if is_day and nuvens < 25 else "⛅" if is_day else "🌙" if nuvens < 25 else "☁️"
            status_formatado = f"{emoji} Sem chuva"

        return f"📍 *{nome.upper()}*\n{status_formatado}\n"
    except:
        return f"📍 *{nome.upper()}*\n❌ Erro na consulta\n"

def executar():
    fuso_sp = timezone(timedelta(hours=-3))
    agora = datetime.now(fuso_sp)
    data_str = agora.strftime('%d/%m/%Y %H:%M')
    
    if not os.path.exists(ARQUIVO):
        print(f"❌ Arquivo {ARQUIVO} não encontrado!")
        return

    df = pd.read_csv(ARQUIVO)
    
    # Montagem do relatório
    corpo_mensagem = [
        "**RELATÓRIO DE BARRAGENS**",
        f"⏰ {data_str}\n"
    ]
    
    for _, row in df.iterrows():
        # Busca a info de cada barragem e adiciona à lista
        info_barragem = verificar_clima(row['nome'], row['lat'], row['long'])
        corpo_mensagem.append(info_barragem)

    # Envia tudo em uma única mensagem
    enviar_telegram("\n".join(corpo_mensagem))

if __name__ == "__main__":
    executar()
