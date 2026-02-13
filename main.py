import requests
import os
import pandas as pd
from datetime import datetime, timedelta, timezone

# ==================== CONFIGURAÇÕES ====================
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
ARQUIVO = "barragens.csv"

# ==================== TELEGRAM ====================
def enviar_telegram(mensagem):
    if not mensagem: return
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": mensagem, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload, timeout=15)
    except Exception as e:
        print(f"Erro ao enviar Telegram: {e}")

# ==================== CLIMA (SOMA 3H) ====================
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
        
        # Soma a previsão das próximas 3 horas (índices 1, 2 e 3)
        previsoes_3h = res["hourly"]["precipitation"][1:4]
        soma_prevista = sum(previsoes_3h)
        
        is_day = atual["is_day"]
        nuvens = atual["cloud_cover"]

        # Se houver chuva agora ou acumulado previsto para as próximas 3h
        if chuva_agora > 0 or soma_prevista > 0:
            emoji = "⚠️🌧️"
            status_texto = f"{chuva_agora:.1f}mm agora / Esperado {soma_prevista:.1f}mm para as próximas horas."
        else:
            if is_day:
                emoji = "☀️" if nuvens < 25 else "⛅"
            else:
                emoji = "🌙" if nuvens < 25 else "☁️"
            status_texto = "SEM CHUVA"

        return f"{emoji} - *{nome.upper()}:* {status_texto}"

    except Exception:
        return f"❌ - *{nome.upper()}:* Erro na consulta"

# ==================== PROCESSAMENTO ====================
def executar():
    fuso_sp = timezone(timedelta(hours=-3))
    agora = datetime.now(fuso_sp)
    data_formatada = agora.strftime('%d/%m/%Y %H:%M')
    
    try:
        df = pd.read_csv(ARQUIVO)
        relatorio = ["🛰️ *RELATÓRIO BARRAGENS*", f"⏰ {data_formatada}\n"]
        
        for _, row in df.iterrows():
            linha = verificar_clima(row['nome'], row['lat'], row['long'])
            relatorio.append(linha)

        enviar_telegram("\n".join(relatorio))
        
    except Exception as e:
        print(f"Erro ao processar: {e}")

if __name__ == "__main__":
    executar()
