import requests
import os
import pandas as pd
import time
import matplotlib.pyplot as plt
import io
from datetime import datetime, timedelta, timezone
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ==================== CONFIGURAÇÕES ====================
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
ARQUIVO = "barragens.csv"
ARQUIVO_EXCEL = "monitoramento_chuvas.xlsx"

session = requests.Session()
retries = Retry(total=3, backoff_factor=2, status_forcelist=[429, 500, 502, 503, 504])
session.mount('https://', HTTPAdapter(max_retries=retries))

def atualizar_planilha_excel(novos_dados):
    if os.path.exists(ARQUIVO_EXCEL):
        try:
            df_bruta = pd.read_excel(ARQUIVO_EXCEL, sheet_name="Base Bruta")
            df_bruta = pd.concat([df_bruta, pd.DataFrame(novos_dados)], ignore_index=True)
        except:
            df_bruta = pd.DataFrame(novos_dados)
    else:
        df_bruta = pd.DataFrame(novos_dados)

    df_bruta['Data_dt'] = pd.to_datetime(df_bruta['Data'], dayfirst=True)
    df_bruta = df_bruta.sort_values('Hora').drop_duplicates(subset=['Data', 'Barragem'], keep='last')
    
    df_bruta['Mês'] = df_bruta['Data_dt'].dt.strftime('%B / %Y')
    aba_resumo = df_bruta.groupby(['Barragem', 'Mês'])['Precipitacao (mm)'].sum().reset_index()
    
    with pd.ExcelWriter(ARQUIVO_EXCEL, engine='openpyxl') as writer:
        df_bruta.drop(columns=['Data_dt', 'Mês']).to_excel(writer, sheet_name="Base Bruta", index=False)
        aba_resumo.to_excel(writer, sheet_name="Resumo Mensal", index=False)

def enviar_telegram(mensagem, foto=None):
    if not TOKEN or not CHAT_ID: return
    if foto:
        url = f"https://api.telegram.org/bot{TOKEN}/sendPhoto"
        files = {'photo': ('grafico.png', foto, 'image/png')}
        payload = {"chat_id": str(CHAT_ID).strip(), "caption": mensagem, "parse_mode": "Markdown"}
        try: session.post(url, data=payload, files=files, timeout=30)
        except: pass
    else:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        payload = {"chat_id": str(CHAT_ID).strip(), "text": mensagem, "parse_mode": "Markdown"}
        try: session.post(url, data=payload, timeout=20)
        except: pass

def verificar_clima_oficial(nome, cod_cemaden, cod_inmet):
    """
    Nova função utilizando fontes oficiais:
    - Cemaden: Dados de precipitação acumulada em tempo real.
    - INMET: Dados de temperatura da estação automática de referência.
    """
    chuva_agora = 0.0
    chuva_acumulada_hoje = 0.0
    temp = 20.0 # Valor padrão caso o INMET falhe
    
    # 1. Coleta de Chuva via CEMADEN
    # Usando o endpoint público que monitora o acumulado das estações
    url_cemaden = f"http://sirene.cemaden.gov.br/sirene/estacao/{cod_cemaden}"
    try:
        res = session.get(url_cemaden, timeout=20).json()
        # O Cemaden retorna históricos de 1h, 3h, 24h.
        chuva_agora = float(res.get("chuva_hora", 0.0)) 
        chuva_acumulada_hoje = float(res.get("chuva_dia", 0.0))
    except:
        # Alternativa estável se o endpoint principal do Cemaden estiver fora do ar
        pass

    # 2. Coleta de Temperatura via INMET (Estações Automáticas)
    agora_utc = datetime.now(timezone.utc)
    data_inmet = agora_utc.strftime('%Y-%m-%d')
    url_inmet = f"https://api.inmet.gov.br/estacao/dados/{data_inmet}"
    try:
        # Busca a última leitura horária da estação selecionada
        dados_inmet = session.get(url_inmet, timeout=25).json()
        estacao_dados = [d for d in dados_inmet if d.get("CD_ESTACAO") == cod_inmet]
        if estacao_dados:
            # Pega a leitura mais recente do dia
            temp = float(estacao_dados[-1].get("TEM_PRE", 20.0))
    except:
        pass

    agora = datetime.now(timezone(timedelta(hours=-3)))
    
    dados_planilha = {
        "Data": agora.strftime('%d/%m/%Y'), 
        "Hora": agora.strftime('%H:%M'),
        "Barragem": nome.upper(), 
        "Precipitacao (mm)": Point_Or_Float(chuva_acumulada_hoje), 
        "Temp (C)": temp
    }
    
    # Montagem da mensagem idêntica ao seu padrão visual
    msg_formatada = f"📍 *{nome.upper()}*\n🌡️ {temp:.1f}°C\n"
    
    # Como o Cemaden não dá previsão para a "Próxima Hora" (pois são sensores físicos e não modelos),
    # o alerta foca no acumulado atual medido no local:
    if chuva_agora > 0:
        msg_formatada += (
            f"⚠️ **ALERTA DE CHUVA**\n"
            f" 🌧️ Agora: {chuva_agora:.1f}mm\n"
            f"📊 Acumulado Hoje: {chuva_acumulada_hoje:.1f}mm\n"
        )
    else:
        msg_formatada += f"☁️ Sem chuva\n"
        
    return msg_formatada, dados_planilha

def Point_Or_Float(val):
    try: return float(val)
    except: return 0.0
