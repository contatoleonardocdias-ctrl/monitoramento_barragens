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
        print("❌ ERRO: CHAT_ID ou TOKEN não configurados nos Secrets.")
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
            print("✅ Relatório enviado!")
        else:
            print(f"❌ Erro Telegram: {res.text}")
    except Exception as e:
        print(f"⚠️ Falha de rede: {e}")

def verificar_clima(nome, lat, lon):
    # Puxamos o atual e a previsão horária
    url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        f"&current=precipitation,is_day,cloud_cover"
        f"&hourly=precipitation"
        f"&timezone=America%2FSao_Paulo"
    )
    try:
        res = requests.get(url, timeout=25).json()
        
        # Chuva agora
        chuva_agora = res["current"]["precipitation"]
        
        # Chuva esperada na próxima 1 hora (índice 1 da lista hourly)
        chuva_prevista = res["hourly"]["precipitation"][1]
        
        is_day = res["current"]["is_day"]
        nuvens = res["current"]["cloud_cover"]

        if chuva_agora > 0 or chuva_prevista > 0:
            # Modelo com a barra / e a previsão conforme solicitado
            status_formatado = (
                f"⚠️ **ALERTA DE CHUVA**\n"
                f"🌧️ **Tempo Real:** {chuva_agora:.1f}mm agora / {chuva_prevista:.1f}mm esperado próxima hora"
            )
        else:
            emoji = "☀️" if is_day and nuvens < 25 else "⛅" if is_day else "🌙" if nuvens < 25 else "☁️"
            status_formatado = f"{emoji} Sem chuva"

        return f"📍 *{nome.upper()}*\n{status_formatado}\n"
    except Exception as e:
        print(f"Erro em {nome}: {e}")
        return f"📍 *{nome.upper()}*\n❌ Erro na consulta\n"

def executar():
    fuso_sp = timezone(timedelta(hours=-3))
    agora = datetime.now(fuso_sp)
    data_str = agora.strftime('%d/%m/%Y %H:%M')
    
    if not os.path.exists(ARQUIVO):
        print(f"❌ Arquivo {ARQUIVO} não encontrado!")
        return

    df = pd.read_csv(ARQUIVO)
    
    corpo_mensagem = [
        "**RELATÓRIO DE BARRAGENS**",
        f"⏰ {data_str}\n"
    ]
    
    for _, row in df.iterrows():
        info_barragem = verificar_clima(row['nome'], row['lat'], row['long'])
        corpo_mensagem.append(info_barragem)

    enviar_telegram("\n".join(corpo_mensagem))

if __name__ == "__main__":
    executar()
