import requests
import os
import pandas as pd
from datetime import datetime, timedelta, timezone

# ==================== CONFIGURAÇÕES ====================
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
# No GitHub, configure o segredo TOMORROW_TOKEN com a sua chave
TOMORROW_API_KEY = os.getenv("TOMORROW_TOKEN") 
ARQUIVO = "barragens.csv"
ARQUIVO_EXCEL = "monitoramento_chuvas.xlsx"

def atualizar_planilha_excel(novos_dados):
    """Salva os dados no Excel com Base Bruta e Resumo Mensal Silencioso"""
    fuso_sp = timezone(timedelta(hours=-3))
    
    if os.path.exists(ARQUIVO_EXCEL):
        try:
            with pd.ExcelFile(ARQUIVO_EXCEL, engine='openpyxl') as xls:
                df_bruta = pd.read_excel(xls, "Base Bruta")
            df_bruta = pd.concat([df_bruta, pd.DataFrame(novos_dados)], ignore_index=True)
        except:
            df_bruta = pd.DataFrame(novos_dados)
    else:
        df_bruta = pd.DataFrame(novos_dados)

    # Lógica de Resumo Mensal: Barragem | Mês | Acumulado
    df_bruta['Data_dt'] = pd.to_datetime(df_bruta['Data'], format='%d/%m/%Y')
    df_bruta['Mês'] = df_bruta['Data_dt'].dt.strftime('%B / %Y')

    aba_resumo = df_bruta.groupby(['Barragem', 'Mês'])['Precipitacao (mm)'].sum().reset_index()
    aba_resumo.columns = ['Barragem', 'Mês', 'Total Acumulado (mm)']
    aba_resumo['Última Atualização'] = datetime.now(fuso_sp).strftime('%d/%m %H:%M')

    df_salvar_bruta = df_bruta.drop(columns=['Data_dt', 'Mês'])
    
    with pd.ExcelWriter(ARQUIVO_EXCEL, engine='openpyxl') as writer:
        df_salvar_bruta.to_excel(writer, sheet_name="Base Bruta", index=False)
        aba_resumo.to_excel(writer, sheet_name="Resumo Mensal", index=False)

def enviar_telegram(mensagem):
    if not TOKEN or not CHAT_ID: return
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": str(CHAT_ID).strip(), "text": mensagem, "parse_mode": "Markdown"}
    try:
        requests.post(url, data=payload, timeout=25)
    except:
        pass

def verificar_clima(nome, lat, lon):
    # TROCADO: Agora usa Tomorrow.io para maior precisão em tempo real
    url = f"https://api.tomorrow.io/v4/weather/realtime?location={lat},{lon}&apikey={TOMORROW_API_KEY}"
    
    try:
        res = requests.get(url, timeout=25).json()
        # A Tomorrow organiza os dados dentro de data -> values
        valores = res.get("data", {}).get("values", {})
        
        # precipitationIntensity é o mm/h exato no momento (Mais preciso que Open-Meteo)
        chuva_agora = valores.get("precipitationIntensity", 0.0) if valores.get("precipitationIntensity") is not None else 0.0
        temp = valores.get("temperature", 0.0) if valores.get("temperature") is not None else 0.0
        probabilidade = valores.get("precipitationProbability", 0)
        nuvens = valores.get("cloudCover", 0)
        
        fuso_sp = timezone(timedelta(hours=-3))
        agora = datetime.now(fuso_sp)

        # Dados para a Planilha
        dados_planilha = {
            "Data": agora.strftime('%d/%m/%Y'),
            "Hora": agora.strftime('%H:%M'),
            "Barragem": nome.upper(),
            "Precipitacao (mm)": chuva_agora,
            "Temp (C)": temp
        }

        # Formatação da Mensagem (Mantendo sua lógica de alertas)
        # Na Tomorrow usamos intensidade + probabilidade para o alerta
        if chuva_agora > 0 or probabilidade > 30:
            intensidade = "Fraca" if chuva_agora < 2 else "Moderada" if chuva_agora < 10 else "FORTE"
            status_formatado = (
                f"⚠️ **ALERTA DE CHUVA ({intensidade})**\n"
                f"🌡️ **Temp:** {temp:.1f}°C\n"
                f"🌧️ **Agora:** {chuva_agora:.2f}mm/h\n"
                f"🎲 **Probabilidade:** {probabilidade}%"
            )
        else:
            emoji = "☀️" if nuvens < 25 else "☁️"
            status_formatado = f"🌡️ **{temp:.1f}°C**\n{emoji} Sem chuva registrada"

        return f"📍 *{nome.upper()}*\n{status_formatado}\n", dados_planilha
    
    except Exception as e:
        return f"📍 *{nome.upper()}*\n❌ Erro na API: {str(e)[:20]}\n", None

def executar():
    fuso_sp = timezone(timedelta(hours=-3))
    agora = datetime.now(fuso_sp)
    
    if not os.path.exists(ARQUIVO): return

    df = pd.read_csv(ARQUIVO)
    corpo_mensagem = [
        "🛰️ **MONITORAMENTO PRECISÃO (TOMORROW.IO)**",
        f"⏰ {agora.strftime('%d/%m/%Y %H:%M')}\n",
        "---"
    ]
    
    dados_para_excel = []
    for _, row in df.iterrows():
        msg, dados = verificar_clima(row['nome'], row['lat'], row['long'])
        corpo_mensagem.append(msg)
        if dados:
            dados_para_excel.append(dados)

    # 1. Salva na planilha silenciosamente
    if dados_para_excel:
        atualizar_planilha_excel(dados_para_excel)

    # 2. Envia relatório para o Telegram
    enviar_telegram("\n".join(corpo_mensagem))

if __name__ == "__main__":
    executar()
