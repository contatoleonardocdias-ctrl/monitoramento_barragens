import requests
import os
import pandas as pd
import time
from datetime import datetime, timedelta, timezone

# ==================== CONFIGURAÇÕES ====================
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
ARQUIVO = "barragens.csv"
ARQUIVO_EXCEL = "monitoramento_chuvas.xlsx"

def atualizar_planilha_excel(novos_dados):
    """Salva os dados no Excel com Base Bruta e Resumo Mensal"""
    if os.path.exists(ARQUIVO_EXCEL):
        try:
            df_bruta = pd.read_excel(ARQUIVO_EXCEL, sheet_name="Base Bruta")
            df_bruta = pd.concat([df_bruta, pd.DataFrame(novos_dados)], ignore_index=True)
        except Exception as e:
            print(f"Erro ao ler planilha existente: {e}")
            df_bruta = pd.DataFrame(novos_dados)
    else:
        df_bruta = pd.DataFrame(novos_dados)

    # Processamento de datas para o resumo
    df_bruta['Data_dt'] = pd.to_datetime(df_bruta['Data'], format='%d/%m/%Y')
    df_bruta['Mês'] = df_bruta['Data_dt'].dt.strftime('%B / %Y')
    
    aba_resumo = df_bruta.groupby(['Barragem', 'Mês'])['Precipitacao (mm)'].sum().reset_index()
    aba_resumo.columns = ['Barragem', 'Mês', 'Total Acumulado (mm)']

    with pd.ExcelWriter(ARQUIVO_EXCEL, engine='openpyxl') as writer:
        df_bruta.drop(columns=['Data_dt', 'Mês']).to_excel(writer, sheet_name="Base Bruta", index=False)
        aba_resumo.to_excel(writer, sheet_name="Resumo Mensal", index=False)

def enviar_telegram(mensagem):
    if not TOKEN or not CHAT_ID: 
        print("Configurações do Telegram ausentes.")
        return
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": str(CHAT_ID).strip(), "text": mensagem, "parse_mode": "Markdown"}
    try:
        requests.post(url, data=payload, timeout=25)
    except Exception as e:
        print(f"Erro ao enviar Telegram: {e}")

def verificar_clima(nome, lat, lon):
    # URL da Open-Meteo
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=precipitation,is_day,cloud_cover,temperature_2m&hourly=precipitation&timezone=America%2FSao_Paulo"
    
    try:
        # Pausa de 2 segundos para respeitar o limite da API gratuita
        time.sleep(2) 
        response = requests.get(url, timeout=20)
        res = response.json()
        
        # Verifica se a API retornou uma mensagem de erro no JSON
        if "error" in res:
            print(f"API Error para {nome}: {res.get('reason')}")
            return f"📍 *{nome.upper()}*\n❌ Erro nos dados da API\n", None

        # Captura de dados de forma segura com .get()
        current = res.get("current", {})
        chuva_agora = current.get("precipitation", 0.0)
        temp = current.get("temperature_2m", 0.0)
        is_day = current.get("is_day", 1)
        nuvens = current.get("cloud_cover", 0)

        # PROTEÇÃO: Verifica se a lista de previsão horária existe antes de acessar o índice [1]
        hourly_data = res.get("hourly", {}).get("precipitation", [])
        chuva_prevista = hourly_data[1] if len(hourly_data) > 1 else 0.0

        fuso_sp = timezone(timedelta(hours=-3))
        agora = datetime.now(fuso_sp)
        
        dados_planilha = {
            "Data": agora.strftime('%d/%m/%Y'), 
            "Hora": agora.strftime('%H:%M'),
            "Barragem": nome.upper(), 
            "Precipitacao (mm)": chuva_agora, 
            "Temp (C)": temp
        }

        info_temp = f"🌡️ Temp: {temp:.1f}°C"
        
        if chuva_agora > 0 or chuva_prevista > 0:
            status_clima = (
                f"⚠️ **ALERTA DE CHUVA**\n"
                f"🌧️ Agora: {chuva_agora:.1f}mm\n"
                f"🔮 Próxima hora: {chuva_prevista:.1f}mm"
            )
        else:
            # Lógica de emojis baseada em dia/noite e nuvens
            if nuvens > 70:
                emoji = "☁️"
            else:
                emoji = "☀️" if is_day and nuvens < 25 else "⛅" if is_day else "🌙" if nuvens < 25 else "☁️"
            status_clima = f"{emoji} Sem chuva"

        return f"📍 *{nome.upper()}*\n{info_temp}\n{status_clima}\n", dados_planilha

    except Exception as e:
        # Log detalhado no console para você debugar no GitHub Actions
        print(f"Falha ao processar {nome}: {type(e).__name__} - {e}")
        return f"📍 *{nome.upper()}*\n❌ Erro na consulta\n", None

def executar():
    if not os.path.exists(ARQUIVO):
        print(f"Arquivo {ARQUIVO} não encontrado!")
        return

    # Lendo o CSV e garantindo que lat/long sejam lidos corretamente
    df = pd.read_csv(ARQUIVO)
    
    fuso_sp = timezone(timedelta(hours=-3))
    agora_fuso = datetime.now(fuso_sp)
    
    corpo_mensagem = [
        "**🛰️ RELATÓRIO DE BARRAGENS**",
        f"⏰ {agora_fuso.strftime('%d/%m/%Y %H:%M')}\n"
    ]
    
    dados_para_excel = []
    
    for _, row in df.iterrows():
        # Passa os dados convertendo para float para garantir
        msg, dados = verificar_clima(str(row['nome']), float(row['lat']), float(row['long']))
        corpo_mensagem.append(msg)
        if dados:
            dados_para_excel.append(dados)

    # Atualiza Excel apenas se houve sucesso em alguma consulta
    if dados_para_excel:
        atualizar_planilha_excel(dados_para_excel)

    # Envia o relatório final acumulado
    enviar_telegram("\n".join(corpo_mensagem))

if __name__ == "__main__":
    executar()
