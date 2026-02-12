import requests
import os
import pandas as pd
from datetime import datetime

# ==================== CONFIGURAÇÕES ====================
# O GitHub vai preencher essas variáveis usando os "Secrets" que você configurou
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
ARQUIVO_BARRAGENS = "barragens.csv"

def enviar_telegram(mensagem):
    """Envia a mensagem formatada para o seu Telegram"""
    if TELEGRAM_TOKEN and CHAT_ID:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {
            "chat_id": CHAT_ID, 
            "text": mensagem, 
            "parse_mode": "Markdown"
        }
        try:
            requests.post(url, json=payload, timeout=10)
        except Exception as e:
            print(f"Erro ao conectar com Telegram: {e}")

def verificar_clima(nome, lat, lon):
    """Consulta a API para uma coordenada específica"""
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=precipitation&hourly=precipitation&timezone=America%2FSao_Paulo&forecast_days=1"
    
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        data = response.json()
        
        chuva_agora = data['current']['precipitation']
        
        # Pega a chuva prevista para a próxima hora
        hora_atual_iso = datetime.now().strftime('%Y-%m-%dT%H:00')
        indices = data['hourly']['time']
        try:
            idx = indices.index(hora_atual_iso)
            chuva_prevista = data['hourly']['precipitation'][idx + 1] if idx + 1 < len(indices) else 0
        except:
            chuva_prevista = 0

        # Só envia mensagem se tiver previsão de chuva (ou se estiver chovendo)
        if chuva_agora > 0 or chuva_prevista > 0:
            msg = (
                f"⚠️ *ALERTA: {nome.upper()}*\n\n"
                f"🌧 *Chovendo agora:* {chuva_agora}mm\n"
                f"📅 *Próxima hora:* {chuva_prevista}mm\n"
                f"⏰ _Consulta em: {datetime.now().strftime('%d/%m %H:%M')}_"
            )
            enviar_telegram(msg)
            return f"✅ Alerta enviado para {nome}"
        
        return f"☁️ {nome}: Sem chuva no momento."

    except Exception as e:
        return f"❌ Erro ao consultar {nome}: {e}"

def executar_job():
    """Função principal que lê a planilha e roda o loop"""
    if not os.path.exists(ARQUIVO_BARRAGENS):
        print(f"Erro: O arquivo {ARQUIVO_BARRAGENS} não foi encontrado no repositório.")
        return

    # O PANDAS LÊ A PLANILHA AQUI
    df = pd.read_csv(ARQUIVO_BARRAGENS)
    
    print(f"Iniciando monitoramento de {len(df)} barragens...")
    
    # LOOP: Para cada linha da planilha, ele executa a função de clima
    for _, linha in df.iterrows():
        # 'nome', 'latitude' e 'longitude' precisam ser os títulos das colunas no seu CSV
        resultado = verificar_clima(linha['nome'], linha['latitude'], linha['longitude'])
        print(resultado)

if __name__ == "__main__":
    executar_job()
