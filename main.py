import requests
import os
import pandas as pd
from datetime import datetime, timedelta, timezone

# ==================== CONFIGURAÇÕES ====================
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
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
    if not TOKEN or not CHAT_ID:
        print("❌ ERRO: CHAT_ID ou TOKEN não configurados.")
        return
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": str(CHAT_ID).strip(), "text": mensagem, "parse_mode": "Markdown"}
    try:
        res = requests.post(url, data=payload, timeout=25)
        if res.status_code == 200:
            print("✅ Relatório enviado!")
    except Exception as e:
        print(f"⚠️ Falha Telegram: {e}")

def verificar_clima(nome, lat, lon):
    # Tomorrow.io - Realtime endpoint para máxima precisão
    url = f"https://api.tomorrow.io/v4/weather/realtime?location={lat},{lon}&apikey={TOMORROW_API_KEY}"
    
    try:
        res = requests.get(url, timeout=25).json()
        valores = res.get("data", {}).get("values", {})
        
        # Extração de dados com blindagem contra None
        chuva_agora = float(valores.get("precipitationIntensity") or 0.0)
        probabilidade = int(valores.get("precipitationProbability") or 0)
        temp = float(valores.get("temperature") or 0.0)
        nuvens = int(valores.get("cloudCover") or 0)
        
        # Como a Tomorrow Realtime foca no agora, usamos a probabilidade como indicador de "esperado"
        # para manter o seu padrão de visualização "agora / esperado"
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

        # CONDIÇÕES E EMOJIS CONFORME SOLICITADO
        if chuva_agora > 0 or probabilidade > 25:
            status_formatado = (
                f"⚠️ **ALERTA DE CHUVA**\n"
                f"🌧️ **Tempo Real:** {chuva_agora:.1f}mm agora / {probabilidade}% de probabilidade próxima hora"
            )
        else:
            # Lógica de emojis baseada em nuvens e horário (isDay não vem direto, calculamos pela hora)
            hora_atual = agora.hour
            is_day = 6 <= hora_atual < 18
            
            if is_day:
                emoji = "☀️" if nuvens < 25 else "⛅"
            else:
                emoji = "🌙" if nuvens < 25 else "☁️"
            
            status_formatado = f"{emoji} Sem chuva"

        return f"📍 *{nome.upper()}*\n{status_formatado}\n", dados_planilha
    
    except Exception as e:
        print(f"Erro em {nome}: {e}")
        return f"📍 *{nome.upper()}*\n❌ Erro na consulta\n", None

def executar():
    fuso_sp = timezone(timedelta(hours=-3))
    agora = datetime.now(fuso_sp)
    
    if not os.path.exists(ARQUIVO):
        print(f"❌ Arquivo {ARQUIVO} não encontrado!")
        return

    df = pd.read_csv(ARQUIVO)
    
    corpo_mensagem = [
        "**🛰️ RELATÓRIO DE BARRAGENS**",
        f"⏰ {agora.strftime('%d/%m/%Y %H:%M')}\n"
    ]
    
    dados_para_excel = []
    
    for _, row in df.iterrows():
        info_barragem, dados = verificar_clima(row['nome'], row['lat'], row['long'])
        corpo_mensagem.append(info_barragem)
        if dados:
            dados_para_excel.append(dados)

    # Preenchimento XLS
    if dados_para_excel:
        atualizar_planilha_excel(dados_para_excel)

    # Envio Telegram
    enviar_telegram("\n".join(corpo_mensagem))

if __name__ == "__main__":
    executar()
