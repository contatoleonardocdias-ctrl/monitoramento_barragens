import requests
import os
import pandas as pd
from datetime import datetime

# ==================== CONFIGURAÇÕES ====================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
ARQUIVO_BARRAGENS = "barragens.csv"

def enviar_telegram(mensagem):
    """Envia a mensagem final consolidada para o Telegram"""
    if TELEGRAM_TOKEN and CHAT_ID:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {
            "chat_id": CHAT_ID, 
            "text": mensagem, 
            "parse_mode": "Markdown"
        }
        try:
            requests.post(url, json=payload, timeout=15)
        except Exception as e:
            print(f"Erro ao enviar Telegram: {e}")

def verificar_clima(nome, lat, lon):
    """Consulta a API e retorna o status da barragem formatado"""
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=precipitation&hourly=precipitation&timezone=America%2FSao_Paulo&forecast_days=1"
    
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        data = response.json()
        
        chuva_agora = data['current']['precipitation']
        
        # Pega a previsão da próxima hora
        hora_iso = datetime.now().strftime('%Y-%m-%dT%H:00')
        indices = data['hourly']['time']
        try:
            idx = indices.index(hora_iso)
            chuva_prevista = data['hourly']['precipitation'][idx + 1] if idx + 1 < len(indices) else 0
        except:
            chuva_prevista = 0

        # Formata a linha da barragem para o relatório
        if chuva_agora > 0 or chuva_prevista > 0:
            return f"⚠️ *{nome}:* {chuva_agora}mm agora / {chuva_prevista}mm prev."
        else:
            return f"✅ *{nome}:* Sem chuva"

    except Exception as e:
        return f"❌ *{nome}:* Erro na consulta"

def executar_job():
    if not os.path.exists(ARQUIVO_BARRAGENS):
        print("Erro: Arquivo barragens.csv não encontrado!")
        return

    # Lê a planilha
    df = pd.read_csv(ARQUIVO_BARRAGENS)
    
    resultados = []
    data_hora = datetime.now().strftime('%d/%m/%Y %H:%M')
    
    print(f"Iniciando monitoramento em {data_hora}...")

    # Percorre as barragens e guarda o status de cada uma
    for _, linha in df.iterrows():
        status = verificar_clima(linha['nome'], linha['lat'], linha['long'])
        resultados.append(status)
        print(status)

    # Monta a mensagem final única
    mensagem_final = f"🛰 *RELATÓRIO METEOROLÓGICO*\n"
    mensagem_final += f"⏰ Atualizado: {data_hora}\n\n"
    mensagem_final += "\n".join(resultados)
    
    # Envia para o Telegram (uma única vez com todas as informações)
    enviar_telegram(mensagem_final)

if __name__ == "__main__":
    executar_job()
