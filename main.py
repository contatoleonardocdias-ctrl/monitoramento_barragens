import requests
import os
import pandas as pd
from datetime import datetime

# Busca as chaves do GitHub
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
ARQUIVO = "barragens.csv"

def enviar_telegram(mensagem):
    if not TOKEN or not CHAT_ID:
        print("❌ ERRO: Chaves TELEGRAM_TOKEN ou CHAT_ID não encontradas nos Secrets!")
        return

    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": mensagem, "parse_mode": "Markdown"}
    
    try:
        response = requests.post(url, json=payload, timeout=15)
        if response.status_code == 200:
            print("✅ Mensagem enviada com sucesso para o Telegram!")
        else:
            print(f"❌ Erro na API do Telegram: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"❌ Erro de conexão: {e}")

def verificar_clima(nome, lat, lon):
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=precipitation&hourly=precipitation&timezone=America%2FSao_Paulo&forecast_days=1"
    try:
        res = requests.get(url, timeout=15).json()
        chuva_agora = res['current']['precipitation']
        
        # Pega previsão próxima hora
        hora_iso = datetime.now().strftime('%Y-%m-%dT%H:00')
        indices = res['hourly']['time']
        try:
            idx = indices.index(hora_iso)
            chuva_prev = res['hourly']['precipitation'][idx + 1]
        except:
            chuva_prev = 0

        if chuva_agora > 0 or chuva_prev > 0:
            return f"⚠️ *{nome}:* {chuva_agora}mm agora / {chuva_prev}mm prev."
        return f"✅ *{nome}:* Sem chuva"
    except:
        return f"❌ *{nome}:* Erro na API de clima"

def executar():
    if not os.path.exists(ARQUIVO):
        print("Arquivo CSV não encontrado!")
        return

    df = pd.read_csv(ARQUIVO)
    relatorio = [f"🛰 *RELATÓRIO BARRAGENS*\n⏰ {datetime.now().strftime('%d/%m %H:%M')}\n"]
    
    for _, row in df.iterrows():
        status = verificar_clima(row['nome'], row['lat'], row['long'])
        relatorio.append(status)
        print(status) # Isso aparece no log do GitHub

    # Envia tudo em uma única mensagem
    enviar_telegram("\n".join(relatorio))

if __name__ == "__main__":
    executar()
