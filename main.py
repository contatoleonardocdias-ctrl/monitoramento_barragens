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
    fuso_sp = timezone(timedelta(hours=-3))
    if os.path.exists(ARQUIVO_EXCEL):
        try:
            df_bruta = pd.read_excel(ARQUIVO_EXCEL, sheet_name="Base Bruta")
            df_bruta = pd.concat([df_bruta, pd.DataFrame(novos_dados)], ignore_index=True)
        except:
            df_bruta = pd.DataFrame(novos_dados)
    else:
        df_bruta = pd.DataFrame(novos_dados)

    df_bruta['Data_dt'] = pd.to_datetime(df_bruta['Data'], format='%d/%m/%Y')
    df_bruta['Mês'] = df_bruta['Data_dt'].dt.strftime('%B / %Y')
    aba_resumo = df_bruta.groupby(['Barragem', 'Mês'])['Precipitacao (mm)'].sum().reset_index()
    aba_resumo.columns = ['Barragem', 'Mês', 'Total Acumulado (mm)']

    with pd.ExcelWriter(ARQUIVO_EXCEL, engine='openpyxl') as writer:
        df_bruta.drop(columns=['Data_dt', 'Mês']).to_excel(writer, sheet_name="Base Bruta", index=False)
        aba_resumo.to_excel(writer, sheet_name="Resumo Mensal", index=False)

def enviar_telegram(mensagem):
    if not TOKEN or not CHAT_ID: return
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": str(CHAT_ID).strip(), "text": mensagem, "parse_mode": "Markdown"}
    try:
        requests.post(url, data=payload, timeout=30)
    except:
        pass

def verificar_clima(nome, lat, lon):
    # Limpeza radical de espaços e vírgulas nas coordenadas
    lat = str(lat).replace(',', '.').strip()
    lon = str(lon).replace(',', '.').strip()
    
    url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        f"&current=precipitation,is_day,cloud_cover,temperature_2m"
        f"&hourly=precipitation"
        f"&timezone=America%2FSao_Paulo"
    )
    
    # Tenta até 3 vezes se a API der timeout
    for tentativa in range(3):
        try:
            time.sleep(2) # ESPERA 2 SEGUNDOS ENTRE CADA BARRAGEM (PARA NÃO TRAVAR)
            res = requests.get(url, timeout=15).json()
            
            if "current" not in res:
                continue

            chuva_agora = res["current"].get("precipitation", 0.0)
            temp = res["current"].get("temperature_2m", 0.0)
            is_day = res["current"].get("is_day", 1)
            nuvens = res["current"].get("cloud_cover", 0)
            chuva_prevista = res["hourly"]["precipitation"][1] if "hourly" in res else 0.0

            fuso_sp = timezone(timedelta(hours=-3))
            agora = datetime.now(fuso_sp)
            dados_planilha = {
                "Data": agora.strftime('%d/%m/%Y'), "Hora": agora.strftime('%H:%M'),
                "Barragem": nome.upper(), "Precipitacao (mm)": chuva_agora, "Temp (C)": temp
            }

            # FORMATO QUE VOCÊ QUER: NOME -> TEMP -> CLIMA
            info_temp = f"🌡️ Temp: {temp:.1f}°C"
            
            if chuva_agora > 0 or chuva_prevista > 0:
                status_clima = (
                    f"⚠️ **ALERTA DE CHUVA**\n"
                    f"🌧️ Agora: {chuva_agora:.1f}mm\n"
                    f"🔮 Próxima hora: {chuva_prevista:.1f}mm"
                )
            else:
                if nuvens > 70: emoji = "☁️"
                else: emoji = "☀️" if is_day and nuvens < 25 else "⛅" if is_day else "🌙" if nuvens < 25 else "☁️"
                status_clima = f"{emoji} Sem chuva"

            return f"📍 *{nome.upper()}*\n{info_temp}\n{status_clima}\n", dados_planilha
        except:
            time.sleep(3) # Se der erro, espera mais e tenta de novo
            continue
            
    return f"📍 *{nome.upper()}*\n❌ Erro de Conexão\n", None

def executar():
    if not os.path.exists(ARQUIVO): return
    df = pd.read_csv(ARQUIVO)
    agora_fuso = datetime.now(timezone(timedelta(hours=-3)))
    corpo_mensagem = ["**🛰️ RELATÓRIO DE BARRAGENS**", f"⏰ {agora_fuso.strftime('%d/%m/%Y %H:%M')}\n"]
    
    dados_para_excel = []
    for _, row in df.iterrows():
        msg, dados = verificar_clima(row['nome'], row['lat'], row['long'])
        corpo_mensagem.append(msg)
        if dados:
            dados_para_excel.append(dados)

    if dados_para_excel:
        atualizar_planilha_excel(dados_para_excel)

    enviar_telegram("\n".join(corpo_mensagem))

if __name__ == "__main__":
    executar()
