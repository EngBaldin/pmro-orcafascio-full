import streamlit as st
import pandas as pd
import plotly.express as px
import io
import requests
import pdfplumber
import re
import json
from groq import Groq
from datetime import datetime, date

st.set_page_config(layout="wide", page_icon="🏗️", page_title="PMRO Enterprise SEINFRA v6.4")

st.markdown("""
<style>
.main {background-color: #f1f5f9;}
.pmro-header {
    background: linear-gradient(90deg, #1e3a8a 0%, #3b82f6 100%);
    padding: 2rem; border-radius: 1rem;
    margin-bottom: 2rem; color: white; text-align: center;
}
.stMetric {background-color: #f8fafc; border-radius: 0.5rem; padding: 1rem;}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="pmro-header">
    <h1>&#127959; PMRO Enterprise SEINFRA v6.4</h1>
    <p>Gestao de Contratos · SINAPI Auto · Reajustes · Orcamentos com IA</p>
    <small>Eng. Guilherme Ritter Baldin | Porto Velho - RO</small>
</div>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────
# FUNCOES AUXILIARES
# ─────────────────────────────────────────
def parse_valor(v):
    try:
        s = str(v).replace("R$", "").strip()
        if re.match(r"^\d+\.\d+$", s) or re.match(r"^\d+$", s):
            return float(s)
        if "," in s:
            s = s.replace(".", "").replace(",", ".")
        return float(s)
    except:
        return 0.0

def extrair_valores_pdf(texto):
    padrao = r"R\$\s*([\d]{1,3}(?:\.[\d]{3})*,\d{2})"
    valores = re.findall(padrao, texto)
    resultado = []
    for v in valores:
        try:
            resultado.append(float(v.replace(".", "").replace(",", ".")))
        except:
            pass
    return resultado

def ler_arquivo_texto(arquivo):
    """Le texto de PDF ou Excel e retorna string"""
    nome = arquivo.name.lower()
    texto = ""
    if nome.endswith(".pdf"):
        with pdfplumber.open(arquivo) as pdf:
            for pg in pdf.pages:
                t = pg.extract_text()
                if t:
                    texto += t + "\n"
    elif nome.endswith(".xlsx") or nome.endswith(".xls"):
        xls = pd.ExcelFile(arquivo)
        for aba in xls.sheet_names:
            df = pd.read_excel(xls, sheet_name=aba, header=None)
            texto += "ABA: " + str(aba) + "\n"
            texto += df.to_string() + "\n\n"
    return texto

import psycopg2
from psycopg2.extras import RealDictCursor
import streamlit as st

# ─────────────────────────────────────────
# BANCO DE DADOS - POSTGRES
# ─────────────────────────────────────────
@st.cache_resource
def init_db():
    conn = psycopg2.connect(
        st.secrets["DATABASE_URL"],
        cursor_factory=RealDictCursor
    )
    cur = conn.cursor()

    # Tabela contratos
    cur.execute('''
        CREATE TABLE IF NOT EXISTS contratos (
            id SERIAL PRIMARY KEY,
            numero TEXT,
            objeto TEXT,
            data_estimado TEXT,
            reajuste_base REAL,
            dt_base TEXT,
            valor_total REAL,
            valor_remanescente REAL,
            indice_atual REAL,
            reajuste_calculado REAL,
            data_cadastro DATE DEFAULT CURRENT_DATE
        )
    ''')

    # Tabela orcamentos
    cur.execute('''
        CREATE TABLE IF NOT EXISTS orcamentos (
            id SERIAL PRIMARY KEY,
            nome TEXT,
            descricao TEXT,
            status TEXT DEFAULT 'Em Elaboracao',
            bdi REAL,
            valor_total REAL,
            itens TEXT,
            data_criacao DATE DEFAULT CURRENT_DATE
        )
    ''')

    # Tabela planilhas_orcamentarias
    cur.execute('''
        CREATE TABLE IF NOT EXISTS planilhas_orcamentarias (
            id SERIAL PRIMARY KEY,
            contrato_id INTEGER REFERENCES contratos(id),
            arquivo_nome TEXT,
            indice_referencia TEXT,
            mes_ano_referencia TEXT,
            desonerado TEXT,
            valor_total REAL,
            observacoes TEXT,
            data_upload DATE DEFAULT CURRENT_DATE
        )
    ''')

    conn.commit()
    cur.close()
    return conn

conn = init_db()
# ─────────────────────────────────────────
# GROQ CLIENT
# ─────────────────────────────────────────
GROQ_KEY = st.secrets.get("GROQ_API_KEY", "")

@st.cache_resource
def get_groq():
    return Groq(api_key=GROQ_KEY)

# ─────────────────────────────────────────
# SINAPI IBGE — BUSCA PDF FTP
# ─────────────────────────────────────────
MESES_PT = {
    1:"jan", 2:"fev", 3:"mar", 4:"abr", 5:"mai", 6:"jun",
    7:"jul", 8:"ago", 9:"set", 10:"out", 11:"nov", 12:"dez"
}

ESTADOS_SINAPI = {
    "RO": "Rondônia",
    "AC": "Acre",
    "AM": "Amazonas",
    "RR": "Roraima",
    "PA": "Pará",
    "AP": "Amapá",
    "TO": "Tocantins",
    "MA": "Maranhão",
    "PI": "Piauí",
    "CE": "Ceará",
    "RN": "Rio Grande do Norte",
    "PB": "Paraíba",
    "PE": "Pernambuco",
    "AL": "Alagoas",
    "SE": "Sergipe",
    "BA": "Bahia",
    "MG": "Minas Gerais",
    "ES": "Espírito Santo",
    "RJ": "Rio de Janeiro",
    "SP": "São Paulo",
    "PR": "Paraná",
    "SC": "Santa Catarina",
    "RS": "Rio Grande do Sul",
    "MS": "Mato Grosso do Sul",
    "MT": "Mato Grosso",
    "GO": "Goiás",
    "DF": "Distrito Federal"
}

@st.cache_data(ttl=86400)
def buscar_sinapi_ibge(ano, mes, estado, desonerado):
    mes_str = MESES_PT[mes]
    urls = [
        "https://ftp.ibge.gov.br/Precos_Custos_e_Indices_da_Construcao_Civil/SINAPI/Fasciculo_Indicadores_IBGE/SINAPI_Indicadores_" + "{:02d}".format(mes) + "_" + str(ano) + ".pdf",
        "https://ftp.ibge.gov.br/Precos_Custos_e_Indices_da_Construcao_Civil/Fasciculo_Indicadores_IBGE/sinapi_" + str(ano) + "{:02d}".format(mes) + "caderno.pdf",
        "https://ftp.ibge.gov.br/Precos_Custos_e_Indices_da_Construcao_Civil/SINAPI/Fasciculo_Indicadores_IBGE/sinapi_" + str(ano) + "{:02d}".format(mes) + "caderno.pdf",
    ]
    try:
        resp = None
        url_usada = None
        for url in urls:
            r = requests.get(url, timeout=15)
            if r.status_code == 200:
                resp = r
                url_usada = url
                break

        if not resp:
            return None, "PDF não encontrado para " + mes_str + "/" + str(ano)

        nome_estado = ESTADOS_SINAPI.get(estado, estado)

        with pdfplumber.open(io.BytesIO(resp.content)) as pdf:
            for i, page in enumerate(pdf.pages):
                texto = page.extract_text()
                if not texto:
                    continue

                # Filtra pagina correta pelo tipo de desoneracao
                texto_lower = texto.lower()
                tem_nao_desonerado = "não considerando a desoner" in texto_lower or "nao considerando a desoner" in texto_lower
                tem_desonerado     = "considerando a desoner" in texto_lower

                if desonerado and tem_nao_desonerado:
                    continue
                if not desonerado and tem_desonerado and not tem_nao_desonerado:
                    continue

                # Busca linha do estado — usa \n real (nao escapado)
                linhas = texto.split("\n")
                for linha in linhas:
                    linha_lower = linha.lower()
                    # Busca pelo nome completo com acento e tambem sem acento como fallback
                    nome_lower = nome_estado.lower()
                    nome_sem_acento = (
                        nome_lower
                        .replace("ô", "o").replace("á", "a").replace("ã", "a")
                        .replace("é", "e").replace("í", "i").replace("ú", "u")
                        .replace("ó", "o").replace("â", "a").replace("ê", "e")
                    )
                    if nome_lower in linha_lower or nome_sem_acento in linha_lower or estado in linha:
                        nums = re.findall(r"\d+[.,]\d+", linha)
                        if len(nums) >= 2:
                            indice_str = nums[1].replace(".", "").replace(",", ".")
                            try:
                                return float(indice_str), "URL: " + str(url_usada)
                            except:
                                continue

        return None, "Estado '" + nome_estado + "' não encontrado no PDF (" + str(url_usada) + ")"

    except Exception as e:
        return None, "Erro: " + str(e)

# ─────────────────────────────────────────
# BCB API PUBLICA
# ─────────────────────────────────────────
@st.cache_data(ttl=3600)
def get_bcb(codigo):
    try:
        url = "https://api.bcb.gov.br/dados/serie/bcdata.sgs." + str(codigo) + "/dados?formato=json"
        r = requests.get(url, timeout=5).json()
        return float(r[-1]['valor']), r[-1]['data']
    except:
        return 0.0, "N/D"

# ─────────────────────────────────────────
# SINAPI INSUMOS LOCAL RO
# ─────────────────────────────────────────
SINAPI_INSUMOS = [
    {"codigo":"98460","nome":"Asfalto Usinado a Quente CAU","unidade":"t","preco":456.78,"tipo":"MATERIAL","familia":"Pavimentacao"},
    {"codigo":"88239","nome":"Emboco de Argamassa Mista","unidade":"m2","preco":28.45,"tipo":"COMPOSICAO","familia":"Edificacao"},
    {"codigo":"366","nome":"Ceramica 30x30 cm","unidade":"m2","preco":45.20,"tipo":"MATERIAL","familia":"Edificacao"},
    {"codigo":"12547","nome":"Tubo PVC 100mm","unidade":"m","preco":12.80,"tipo":"MATERIAL","familia":"Drenagem"},
    {"codigo":"789","nome":"Cimento Portland CP II","unidade":"sc 50kg","preco":28.90,"tipo":"MATERIAL","familia":"Geral"},
    {"codigo":"4209","nome":"Areia Media Lavada","unidade":"m3","preco":89.00,"tipo":"MATERIAL","familia":"Geral"},
    {"codigo":"7155","nome":"Brita n1","unidade":"m3","preco":110.00,"tipo":"MATERIAL","familia":"Geral"},
    {"codigo":"11703","nome":"Aco CA-50 12mm","unidade":"kg","preco":8.75,"tipo":"MATERIAL","familia":"Edificacao"},
    {"codigo":"99990","nome":"Pedreiro","unidade":"h","preco":21.50,"tipo":"MAO DE OBRA","familia":"Geral"},
    {"codigo":"99991","nome":"Servente","unidade":"h","preco":15.30,"tipo":"MAO DE OBRA","familia":"Geral"},
    {"codigo":"55210","nome":"Escavacao Mecanica Solo","unidade":"m3","preco":5.80,"tipo":"COMPOSICAO","familia":"Terraplenagem"},
    {"codigo":"93358","nome":"Subleito Compactado","unidade":"m3","preco":9.40,"tipo":"COMPOSICAO","familia":"Pavimentacao"},
    {"codigo":"97528","nome":"Meio Fio 15x30 cm","unidade":"m","preco":42.10,"tipo":"COMPOSICAO","familia":"Pavimentacao"},
    {"codigo":"74104","nome":"Tubo Concreto 60cm","unidade":"m","preco":185.00,"tipo":"MATERIAL","familia":"Drenagem"},
    {"codigo":"80842","nome":"Caixa de Passagem 60x60","unidade":"un","preco":350.00,"tipo":"COMPOSICAO","familia":"Drenagem"},
]

# ─────────────────────────────────────────
# SIDEBAR MENU
# ─────────────────────────────────────────
st.sidebar.title("Menu Principal")
page = st.sidebar.radio("", [
    "📊 Dashboard",
    "📑 Contratos",
    "📋 Planilha Orcamentaria",
    "➕ Orcamento",
    "🔍 Pesquisa de Precos",
    "📈 Reajustes",
    "📄 Relatorios"
])

if st.sidebar.button("Atualizar BCB"):
    st.cache_data.clear()
    st.rerun()

# ─────────────────────────────────────────
# 1. DASHBOARD
# ─────────────────────────────────────────
if page == "📊 Dashboard":
    st.header("Dashboard Geral")

    incc, dt_incc = get_bcb(433)
    ipca, _       = get_bcb(438)
    selic, _      = get_bcb(432)
    igpm, _       = get_bcb(189)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("INCC Mensal", str(incc) + "%", delta="ref " + str(dt_incc))
    col2.metric("IPCA Mensal", str(ipca) + "%")
    col3.metric("SELIC", str(selic) + "%")
    col4.metric("IGP-M", str(igpm) + "%")

    st.markdown("---")

    df_c = pd.read_sql("SELECT * FROM contratos", conn)
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Contratos", len(df_c))
    val_carteira = df_c['valor_total'].sum() if not df_c.empty else 0
    col2.metric("Valor Carteira", "R$ " + "{:,.2f}".format(val_carteira))

    pendentes = 0
    if not df_c.empty:
        hoje = date.today()
        for _, row in df_c.iterrows():
            try:
                dt = datetime.strptime(str(row['data_estimado'])[:10], "%Y-%m-%d").date()
                if (hoje - dt).days > 365:
                    pendentes += 1
            except:
                pass
    col3.metric("Pendentes Reajuste", pendentes)
    val_reaj = df_c['reajuste_calculado'].sum() if not df_c.empty else 0
    col4.metric("Total Reajustes", "R$ " + "{:,.2f}".format(val_reaj))

    if not df_c.empty:
        fig = px.bar(df_c, x='numero', y='valor_total',
                     title="Valor por Contrato (R$)",
                     color='reajuste_calculado',
                     labels={'numero': 'Contrato', 'valor_total': 'Valor (R$)'},
                     color_continuous_scale='Blues')
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("Contratos Ativos")
    if not df_c.empty:
        st.dataframe(df_c, use_container_width=True)
    else:
        st.info("Nenhum contrato cadastrado ainda.")

# ─────────────────────────────────────────
# 2. CONTRATOS
# ─────────────────────────────────────────
elif page == "📑 Contratos":
    st.header("Gestao de Contratos")

    tab1, tab2, tab3 = st.tabs(["Upload PDF (IA)", "Cadastro Manual", "Contratos Cadastrados"])

    with tab1:
        st.subheader("Upload da Planilha Ganha na Licitacao")
        st.caption("Aceita Excel (.xlsx) ou PDF. A IA ira identificar o indice e mes de referencia.")

        df_c = pd.read_sql("SELECT id, numero, objeto FROM contratos", conn)
        if df_c.empty:
            st.warning("Cadastre um contrato primeiro antes de vincular uma planilha.")
        else:
            contrato_sel = st.selectbox(
                "Vincular ao Contrato",
                df_c['id'],
                format_func=lambda x: df_c[df_c['id']==x]['numero'].values[0] + " — " + df_c[df_c['id']==x]['objeto'].values[0][:50]
            )

            arquivo = st.file_uploader("Selecione a Planilha (Excel ou PDF)", type=["xlsx","xls","pdf"])

            if arquivo:
                # Salva no session_state para nao perder ao clicar botao
                st.session_state['plan_arquivo_nome'] = arquivo.name
                st.session_state['plan_contrato_sel'] = contrato_sel
                with st.spinner("Lendo arquivo..."):
                    texto_arquivo = ler_arquivo_texto(arquivo)
                if texto_arquivo:
                    st.session_state['plan_texto'] = texto_arquivo
                    st.success("Arquivo lido! " + str(len(texto_arquivo)) + " caracteres.")

            if st.session_state.get('plan_texto') and st.session_state.get('plan_arquivo_nome'):
                if st.button("🤖 Analisar com IA"):
                    with st.spinner("IA identificando indice e referencia..."):
                        try:
                            client = get_groq()
                            prompt = (
    "Voce e um engenheiro civil especialista em orcamentos publicos brasileiros. "
    "Analise a planilha orcamentaria abaixo e extraia SOMENTE o JSON sem explicacoes. "
    "IMPORTANTE: Se houver mais de um indice (ex: SINAPI e SICRO), escolha o PRINCIPAL "
    "(geralmente o de maior participacao no orcamento). "
    "Se houver mais de uma data, use a data do indice PRINCIPAL escolhido. "
    "Retorne SOMENTE este JSON:\n"
    "{\"indice_referencia\":\"\","
    "\"mes_ano_referencia\":\"MM/AAAA\","
    "\"desonerado\":\"Sim ou Nao\","
    "\"valor_total\":0.0,"
    "\"observacoes\":\"informe todos os indices encontrados aqui\"}"
    "\n\nREGRAS:"
    "\n- indice_referencia: APENAS UM indice principal (SINAPI, SICRO, ORSE, etc.)"
    "\n- mes_ano_referencia: mes e ano APENAS do indice principal, formato MM/AAAA"
    "\n- desonerado: Sim ou Nao"
    "\n- valor_total: valor total com BDI, float"
    "\n- observacoes: liste TODOS os indices encontrados e suas datas"
    "\n\nPLANILHA:\n" + st.session_state['plan_texto'][:4000]
)
                            resp = client.chat.completions.create(
                                model="llama-3.3-70b-versatile",
                                messages=[{"role": "user", "content": prompt}],
                                temperature=0.1
                            )
                            json_str = resp.choices[0].message.content.strip()
                            json_str = re.sub(r"```json|```", "", json_str).strip()
                            st.session_state['plan_dados'] = json.loads(json_str)
                            st.success("IA identificou os dados!")
                        except Exception as e:
                            st.error("Erro IA: " + str(e))
                            st.session_state['plan_dados'] = {
                                "indice_referencia": "SINAPI",
                                "mes_ano_referencia": "",
                                "desonerado": "Nao",
                                "valor_total": 0.0,
                                "observacoes": ""
                            }

                if st.session_state.get('plan_dados'):
                    dados_planilha = st.session_state['plan_dados']
                    st.json(dados_planilha)
                    st.markdown("---")
                    st.subheader("Confirme e salve:")

                    col1, col2 = st.columns(2)
                    with col1:
                        indice_ref = st.selectbox(
                            "Indice de Referencia",
                            ["SINAPI", "SICRO", "ORSE", "SEINFRA-CE", "Outro"],
                            index=["SINAPI","SICRO","ORSE","SEINFRA-CE","Outro"].index(
                                dados_planilha.get("indice_referencia","SINAPI")
                            ) if dados_planilha.get("indice_referencia","") in ["SINAPI","SICRO","ORSE","SEINFRA-CE","Outro"] else 0,
                            key="indice_ref_sel"
                        )
                        mes_ano_ref = st.text_input(
                            "Mes/Ano Referencia (MM/AAAA)",
                            value=dados_planilha.get("mes_ano_referencia", ""),
                            key="mes_ano_ref_inp"
                        )
                    with col2:
                        desonerado_p = st.selectbox(
                            "Desonerado?",
                            ["Nao", "Sim"],
                            index=0 if dados_planilha.get("desonerado","Nao") == "Nao" else 1,
                            key="desonerado_sel"
                        )
                        valor_total_p = st.number_input(
                            "Valor Total R$",
                            value=parse_valor(dados_planilha.get("valor_total", 0)),
                            format="%.2f",
                            key="valor_total_plan"
                        )
                    observacoes_p = st.text_area(
                        "Observacoes",
                        value=dados_planilha.get("observacoes", ""),
                        height=80,
                        key="obs_plan"
                    )

                    if st.button("💾 Salvar Planilha e Atualizar Contrato"):
                        nome_arq     = st.session_state['plan_arquivo_nome']
                        contrato_id  = st.session_state['plan_contrato_sel']

                        conn.execute(
                            "INSERT INTO planilhas_orcamentarias (contrato_id, arquivo_nome, indice_referencia, mes_ano_referencia, desonerado, valor_total, observacoes) VALUES (?,?,?,?,?,?,?)",
                            (contrato_id, nome_arq, indice_ref, mes_ano_ref, desonerado_p, valor_total_p, observacoes_p)
                        )
                        conn.commit()
                        st.success("✅ Planilha vinculada!")

                        if mes_ano_ref:
                            try:
                                partes   = mes_ano_ref.split("/")
                                mes_r    = int(partes[0])
                                ano_r    = int(partes[1])
                                des_bool = desonerado_p == "Sim"

                                with st.spinner("Buscando indice " + indice_ref + " " + mes_ano_ref + "..."):
                                    if indice_ref == "SINAPI":
                                        idx_valor, msg_idx = buscar_sinapi_ibge(ano_r, mes_r, "RO", des_bool)
                                    elif indice_ref == "INCC":
                                        idx_valor, _ = get_bcb(433)
                                        msg_idx = "OK"
                                    elif indice_ref == "IPCA":
                                        idx_valor, _ = get_bcb(438)
                                        msg_idx = "OK"
                                    elif indice_ref == "IGP-M":
                                        idx_valor, _ = get_bcb(189)
                                        msg_idx = "OK"
                                    else:
                                        idx_valor = None
                                        msg_idx   = "Indice nao automatizado ainda"

                                if idx_valor:
                                    dt_base_nova = partes[1] + "-" + partes[0] + "-01"
                                    conn.execute(
                                        "UPDATE contratos SET data_estimado=?, dt_base=?, reajuste_base=? WHERE id=?",
                                        (dt_base_nova, dt_base_nova, idx_valor, contrato_id)
                                    )
                                    conn.commit()
                                    st.success("✅ Contrato atualizado! Indice Io = " + str(idx_valor) + " | Data-base: " + mes_ano_ref)
                                    st.balloons()
                                    # Limpa session_state apos salvar
                                    for k in ['plan_texto','plan_dados','plan_arquivo_nome','plan_contrato_sel']:
                                        st.session_state.pop(k, None)
                                else:
                                    st.warning("Indice nao encontrado: " + msg_idx)
                                    st.info("Va em Contratos e atualize o Indice Base Io manualmente.")

                            except Exception as e:
                                st.error("Erro ao atualizar contrato: " + str(e))
                        else:
                            st.warning("Mes/ano nao identificado. Atualize o contrato manualmente.")

    with tab2:
        with st.form("form_manual"):
            col1, col2 = st.columns(2)
            with col1:
                numero          = st.text_input("Numero do Contrato", placeholder="001/2026")
                objeto          = st.text_area("Objeto", height=100)
                data_est_manual = st.text_input("Data Orcamento Estimado (MM/AAAA)", placeholder="01/2025")
                desonerado_m    = st.checkbox("Desonerado?", value=False, key="des_manual")
            with col2:
                estado_m  = st.selectbox("Estado", list(ESTADOS_SINAPI.keys()), key="estado_manual")
                val_total = st.number_input("Valor Total R$", value=1000000.0, format="%.2f")
                val_rem   = st.number_input("Valor Remanescente R$", value=800000.0, format="%.2f")
                ind_base  = st.number_input("Indice Base Io", value=100.0, format="%.2f")

            col_btn1, col_btn2 = st.columns(2)
            buscar_idx = col_btn1.form_submit_button("Buscar Indice SINAPI")
            salvar_btn = col_btn2.form_submit_button("Salvar Contrato")

            if buscar_idx and data_est_manual:
                try:
                    partes = data_est_manual.split("/")
                    idx, msg = buscar_sinapi_ibge(int(partes[1]), int(partes[0]), estado_m, desonerado_m)
                    if idx:
                        st.success("Indice SINAPI encontrado: " + str(idx))
                        st.info("Cole esse valor no campo Indice Base Io e clique Salvar.")
                    else:
                        st.warning(msg)
                except:
                    st.error("Formato invalido. Use MM/AAAA")

            if salvar_btn:
                if not numero or not objeto:
                    st.error("Preencha numero e objeto!")
                else:
                    try:
                        partes = data_est_manual.split("/")
                        dt_salvar = partes[1] + "-" + partes[0] + "-01"
                    except:
                        dt_salvar = str(date.today())
                    conn.execute(
                        
                        "INSERT INTO contratos (numero, objeto, data_estimado, reajuste_base, dt_base, valor_total, valor_remanescente) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                        (numero, objeto, dt_salvar, ind_base, dt_salvar, val_total, val_rem)
                    )
                    conn.commit()
                    cur.close()
                    st.success("Contrato " + numero + " salvo!")
                    st.balloons()

    with tab3:
        df_c = pd.read_sql("SELECT * FROM contratos", conn)
        if df_c.empty:
            st.info("Nenhum contrato cadastrado.")
        else:
            st.dataframe(df_c, use_container_width=True)
            del_id = st.number_input("ID para excluir", min_value=0, step=1)
            if st.button("Excluir") and del_id > 0:
                conn.execute("DELETE FROM contratos WHERE id=?", (del_id,))
                conn.commit()
                st.rerun()

# ─────────────────────────────────────────
# 3. PLANILHA ORCAMENTARIA
# ─────────────────────────────────────────
elif page == "📋 Planilha Orcamentaria":
    st.header("Planilha Orcamentaria")

    tab1, tab2 = st.tabs(["Upload e Cadastro", "Planilhas Cadastradas"])

    with tab1:
        st.subheader("Upload da Planilha Ganha na Licitacao")
        st.caption("Aceita Excel (.xlsx) ou PDF. A IA ira identificar o indice e mes de referencia.")

        df_c = pd.read_sql("SELECT id, numero, objeto FROM contratos", conn)
        if df_c.empty:
            st.warning("Cadastre um contrato primeiro antes de vincular uma planilha.")
        else:
            contrato_sel = st.selectbox(
                "Vincular ao Contrato",
                df_c['id'],
                format_func=lambda x: df_c[df_c['id']==x]['numero'].values[0] + " — " + df_c[df_c['id']==x]['objeto'].values[0][:50]
            )

            arquivo = st.file_uploader("Selecione a Planilha (Excel ou PDF)", type=["xlsx","xls","pdf"])

            if arquivo:
                    st.write("DEBUG — arquivo carregado:", arquivo.name)
                    with st.spinner("Lendo arquivo..."):
                        texto_arquivo = ler_arquivo_texto(arquivo)

                    if texto_arquivo:
                        st.success("Arquivo lido! " + str(len(texto_arquivo)) + " caracteres extraidos.")

                        with st.spinner("IA identificando indice e referencia..."):
                            try:
                                client = get_groq()
                                prompt = (
                                    "Voce e um engenheiro civil especialista em orcamentos publicos brasileiros. "
                                    "Analise a planilha orcamentaria abaixo e extraia SOMENTE o JSON sem explicacoes: "
                                    "{\"indice_referencia\":\"\","
                                    "\"mes_ano_referencia\":\"MM/AAAA\","
                                    "\"desonerado\":\"Sim ou Nao\","
                                    "\"valor_total\":0.0,"
                                    "\"observacoes\":\"\"}"
                                    "\n\nREGRAS:"
                                    "\n- indice_referencia: qual tabela de precos foi usada (SINAPI, SICRO, ORSE, etc.)"
                                    "\n- mes_ano_referencia: mes e ano da tabela de referencia usada no orcamento"
                                    "\n- desonerado: se a planilha usa custos desonerados ou nao"
                                    "\n- valor_total: valor total da planilha orcamentaria com BDI, float"
                                    "\n- observacoes: qualquer informacao relevante"
                                    "\n\nPLANILHA:\n" + texto_arquivo[:4000]
                                )
                                resp = client.chat.completions.create(
                                    model="llama-3.3-70b-versatile",
                                    messages=[{"role": "user", "content": prompt}],
                                    temperature=0.1
                                )
                                json_str = resp.choices[0].message.content.strip()
                                json_str = re.sub(r"```json|```", "", json_str).strip()
                                dados_planilha = json.loads(json_str)
                                st.success("IA identificou os dados!")
                                st.json(dados_planilha)

                            except Exception as e:
                                st.error("Erro IA: " + str(e))
                                dados_planilha = {
                                    "indice_referencia": "",
                                    "mes_ano_referencia": "",
                                    "desonerado": "Nao",
                                    "valor_total": 0.0,
                                    "observacoes": ""
                                }

                        st.markdown("---")
                        st.subheader("Confirme e salve:")

                        # Campos fora do form para manter valores no session_state
                        col1, col2 = st.columns(2)
                        with col1:
                            indice_ref = st.selectbox(
                                "Indice de Referencia",
                                ["SINAPI", "SICRO", "ORSE", "SEINFRA-CE", "Outro"],
                                index=["SINAPI","SICRO","ORSE","SEINFRA-CE","Outro"].index(
                                    dados_planilha.get("indice_referencia","SINAPI")
                                ) if dados_planilha.get("indice_referencia","") in ["SINAPI","SICRO","ORSE","SEINFRA-CE","Outro"] else 0,
                                key="indice_ref_sel"
                            )
                            mes_ano_ref = st.text_input(
                                "Mes/Ano Referencia (MM/AAAA)",
                                value=dados_planilha.get("mes_ano_referencia", ""),
                                key="mes_ano_ref_inp"
                            )
                        with col2:
                            desonerado_p = st.selectbox(
                                "Desonerado?",
                                ["Nao", "Sim"],
                                index=0 if dados_planilha.get("desonerado","Nao") == "Nao" else 1,
                                key="desonerado_sel"
                            )
                            valor_total_p = st.number_input(
                                "Valor Total R$",
                                value=parse_valor(dados_planilha.get("valor_total", 0)),
                                format="%.2f",
                                key="valor_total_plan"
                            )
                        observacoes_p = st.text_area(
                            "Observacoes",
                            value=dados_planilha.get("observacoes", ""),
                            height=80,
                            key="obs_plan"
                        )

                        if st.button("💾 Salvar Planilha e Atualizar Contrato"):
                            st.write("DEBUG — botao clicado!")
                            st.write("DEBUG — indice_ref:", indice_ref)
                            st.write("DEBUG — mes_ano_ref:", mes_ano_ref)
                            st.write("DEBUG — desonerado_p:", desonerado_p)
                            conn.execute(
                                "INSERT INTO planilhas_orcamentarias (contrato_id, arquivo_nome, indice_referencia, mes_ano_referencia, desonerado, valor_total, observacoes) VALUES (?,?,?,?,?,?,?)",
                                (contrato_sel, arquivo.name, indice_ref, mes_ano_ref, desonerado_p, valor_total_p, observacoes_p)
                            )
                            conn.commit()
                            st.success("✅ Planilha vinculada!")

                            if mes_ano_ref:
                                try:
                                    partes   = mes_ano_ref.split("/")
                                    mes_r    = int(partes[0])
                                    ano_r    = int(partes[1])
                                    des_bool = desonerado_p == "Sim"

                                    with st.spinner("Buscando indice " + indice_ref + " " + mes_ano_ref + "..."):
                                        if indice_ref == "SINAPI":
                                            idx_valor, msg_idx = buscar_sinapi_ibge(ano_r, mes_r, "RO", des_bool)
                                        elif indice_ref == "INCC":
                                            idx_valor, _ = get_bcb(433)
                                            msg_idx = "OK"
                                        elif indice_ref == "IPCA":
                                            idx_valor, _ = get_bcb(438)
                                            msg_idx = "OK"
                                        elif indice_ref == "IGP-M":
                                            idx_valor, _ = get_bcb(189)
                                            msg_idx = "OK"
                                        else:
                                            idx_valor = None
                                            msg_idx   = "Indice nao automatizado ainda"

                                    if idx_valor:
                                        dt_base_nova = partes[1] + "-" + partes[0] + "-01"
                                        conn.execute(
                                            "UPDATE contratos SET data_estimado=?, dt_base=?, reajuste_base=? WHERE id=?",
                                            (dt_base_nova, dt_base_nova, idx_valor, contrato_sel)
                                        )
                                        conn.commit()
                                        st.success("✅ Contrato atualizado! Indice Io = " + str(idx_valor) + " | Data-base: " + mes_ano_ref)
                                        st.balloons()
                                    else:
                                        st.warning("Indice nao encontrado: " + msg_idx)
                                        st.info("Va em Contratos e atualize o Indice Base Io manualmente.")

                                except Exception as e:
                                    st.error("Erro ao atualizar contrato: " + str(e))
                            else:
                                st.warning("Mes/ano nao identificado. Atualize o contrato manualmente.")
                    else:
                        st.error("Nao foi possivel extrair texto do arquivo.")
    with tab2:
        st.subheader("Planilhas Cadastradas")
        df_p = pd.read_sql("""
            SELECT p.id, c.numero as contrato, p.arquivo_nome,
                   p.indice_referencia, p.mes_ano_referencia,
                   p.desonerado, p.valor_total, p.observacoes, p.data_upload
            FROM planilhas_orcamentarias p
            LEFT JOIN contratos c ON p.contrato_id = c.id
        """, conn)

        if df_p.empty:
            st.info("Nenhuma planilha cadastrada ainda.")
        else:
            st.dataframe(df_p, use_container_width=True)

            st.markdown("---")
            del_p = st.number_input("ID para excluir", min_value=0, step=1, key="del_plan")
            if st.button("Excluir Planilha") and del_p > 0:
                conn.execute("DELETE FROM planilhas_orcamentarias WHERE id=?", (del_p,))
                conn.commit()
                st.rerun()

# ─────────────────────────────────────────
# 4. ORCAMENTO
# ─────────────────────────────────────────
elif page == "➕ Orcamento":
    st.header("Orcamentos")

    sub = st.radio("", ["Criar Orcamento", "Criar com IA", "Modelos Prontos", "Meus Orcamentos"], horizontal=True)

    if sub == "Criar Orcamento":
        st.subheader("Novo Orcamento Manual")
        df_sinapi = pd.DataFrame(SINAPI_INSUMOS)

        col1, col2 = st.columns([3, 1])
        with col2:
            nome_orc = st.text_input("Nome do Orcamento")
            bdi      = st.number_input("BDI (%)", value=25.0)
            status   = st.selectbox("Status", ["Em Elaboracao", "Finalizado"])

        itens_orc = []
        with col1:
            st.caption("Insira quantidades:")
            for _, r in df_sinapi.iterrows():
                c1, c2, c3 = st.columns([4, 1, 2])
                c1.write(r['codigo'] + " - " + r['nome'])
                qtd = c2.number_input("qtd", min_value=0.0, value=0.0,
                                      key="qtd_" + r['codigo'], format="%.2f",
                                      label_visibility="collapsed")
                c3.write("R$ " + "{:.2f}".format(r['preco']) + "/" + r['unidade'])
                if qtd > 0:
                    item = dict(r)
                    item['qtd']   = qtd
                    item['total'] = r['preco'] * qtd
                    itens_orc.append(item)

        if st.button("Calcular e Salvar Orcamento") and itens_orc and nome_orc:
            df_orc    = pd.DataFrame(itens_orc)
            subtotal  = df_orc['total'].sum()
            total_bdi = subtotal * (1 + bdi / 100)

            st.dataframe(df_orc[['codigo','nome','unidade','qtd','preco','total']], use_container_width=True)
            col1, col2, col3 = st.columns(3)
            col1.metric("Subtotal", "R$ " + "{:,.2f}".format(subtotal))
            col2.metric("BDI", "R$ " + "{:,.2f}".format(subtotal * bdi / 100))
            col3.metric("TOTAL", "R$ " + "{:,.2f}".format(total_bdi))

            conn.execute(
                "INSERT INTO orcamentos (nome, status, bdi, valor_total, itens) VALUES (?,?,?,?,?)",
                (nome_orc, status, bdi, total_bdi, json.dumps(itens_orc))
            )
            conn.commit()
            st.success("Orcamento salvo!")

            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df_orc.to_excel(writer, sheet_name='Orcamento', index=False)
            st.download_button("Baixar Excel", output.getvalue(), nome_orc + ".xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    elif sub == "Criar com IA":
        st.subheader("Orcamento com Inteligencia Artificial")
        descricao_obra = st.text_area("Descreva a obra:",
                                      placeholder="Ex: Pavimentacao asfaltica 500m via urbana com drenagem e meio-fio",
                                      height=120)
        bdi_ia = st.number_input("BDI (%)", value=25.0, key="bdi_ia")

        if st.button("Gerar Orcamento com IA") and descricao_obra:
            with st.spinner("IA elaborando orcamento..."):
                try:
                    client    = get_groq()
                    itens_str = str([{"codigo": i["codigo"], "nome": i["nome"],
                                      "unidade": i["unidade"], "preco": i["preco"]}
                                     for i in SINAPI_INSUMOS])
                    prompt = (
                        "Voce e um engenheiro civil especialista em orcamentos publicos. "
                        "Monte um orcamento usando APENAS os itens SINAPI da lista. "
                        "Retorne SOMENTE JSON no formato: "
                        '[{"codigo":"","nome":"","unidade":"","preco":0.0,"qtd":0.0,"total":0.0}] '
                        "Itens SINAPI: " + itens_str + " Obra: " + descricao_obra
                    )

                    resp = client.chat.completions.create(
                        model="llama-3.3-70b-versatile",
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.2
                    )

                    json_str  = resp.choices[0].message.content.strip()
                    json_str  = re.sub(r"```json|```", "", json_str).strip()
                    itens_ia  = json.loads(json_str)
                    df_ia     = pd.DataFrame(itens_ia)
                    subtotal  = df_ia['total'].sum()
                    total_ia  = subtotal * (1 + bdi_ia / 100)

                    st.success("Orcamento gerado pela IA!")
                    st.dataframe(df_ia, use_container_width=True)

                    col1, col2 = st.columns(2)
                    col1.metric("Subtotal", "R$ " + "{:,.2f}".format(subtotal))
                    col2.metric("Total c/ BDI", "R$ " + "{:,.2f}".format(total_ia))

                    if st.button("Salvar Orcamento IA"):
                        conn.execute(
                            "INSERT INTO orcamentos (nome, descricao, status, bdi, valor_total, itens) VALUES (?,?,?,?,?,?)",
                            ("Orc IA - " + descricao_obra[:30], descricao_obra,
                             "Em Elaboracao", bdi_ia, total_ia, json.dumps(itens_ia))
                        )
                        conn.commit()
                        st.success("Salvo em Meus Orcamentos!")

                except Exception as e:
                    st.error("Erro IA: " + str(e))

    elif sub == "Modelos Prontos":
        st.subheader("Modelos de Orcamento")
        modelos = {
            "Pavimentacao Asfaltica 1km": [
                {"codigo":"98460","nome":"Asfalto CAU","unidade":"t","preco":456.78,"qtd":120,"total":54813.60},
                {"codigo":"93358","nome":"Subleito Compactado","unidade":"m3","preco":9.40,"qtd":600,"total":5640.00},
                {"codigo":"97528","nome":"Meio Fio 15x30","unidade":"m","preco":42.10,"qtd":2000,"total":84200.00},
            ],
            "Drenagem Pluvial 500m": [
                {"codigo":"12547","nome":"Tubo PVC 100mm","unidade":"m","preco":12.80,"qtd":500,"total":6400.00},
                {"codigo":"74104","nome":"Tubo Concreto 60cm","unidade":"m","preco":185.00,"qtd":200,"total":37000.00},
                {"codigo":"80842","nome":"Caixa de Passagem","unidade":"un","preco":350.00,"qtd":20,"total":7000.00},
                {"codigo":"55210","nome":"Escavacao Solo","unidade":"m3","preco":5.80,"qtd":800,"total":4640.00},
            ],
        }

        modelo_sel   = st.selectbox("Selecionar Modelo", list(modelos.keys()))
        df_modelo    = pd.DataFrame(modelos[modelo_sel])
        st.dataframe(df_modelo, use_container_width=True)

        bdi_mod      = st.number_input("BDI (%)", value=25.0, key="bdi_mod")
        subtotal_mod = df_modelo['total'].sum()
        total_mod    = subtotal_mod * (1 + bdi_mod / 100)

        col1, col2 = st.columns(2)
        col1.metric("Subtotal", "R$ " + "{:,.2f}".format(subtotal_mod))
        col2.metric("Total c/ BDI", "R$ " + "{:,.2f}".format(total_mod))

        if st.button("Usar este Modelo"):
            conn.execute(
                "INSERT INTO orcamentos (nome, status, bdi, valor_total, itens) VALUES (?,?,?,?,?)",
                (modelo_sel, "Em Elaboracao", bdi_mod, total_mod, json.dumps(modelos[modelo_sel]))
            )
            conn.commit()
            st.success("Modelo copiado para Meus Orcamentos!")

    elif sub == "Meus Orcamentos":
        st.subheader("Meus Orcamentos Salvos")
        df_orc_saved = pd.read_sql("SELECT id, nome, status, bdi, valor_total, data_criacao FROM orcamentos", conn)
        if df_orc_saved.empty:
            st.info("Nenhum orcamento salvo ainda.")
        else:
            st.dataframe(df_orc_saved, use_container_width=True)
            del_orc = st.number_input("ID para excluir", min_value=0, step=1, key="del_orc")
            if st.button("Excluir Orcamento") and del_orc > 0:
                conn.execute("DELETE FROM orcamentos WHERE id=?", (del_orc,))
                conn.commit()
                st.rerun()

# ─────────────────────────────────────────
# 5. PESQUISA DE PRECOS
# ─────────────────────────────────────────
elif page == "🔍 Pesquisa de Precos":
    st.header("Pesquisa de Precos")

    sub2 = st.radio("", ["Insumos e Composicoes", "Tabelas de Precos"], horizontal=True)

    if sub2 == "Insumos e Composicoes":
        st.subheader("Insumos e Composicoes SINAPI/SICRO RO")
        df_sinapi = pd.DataFrame(SINAPI_INSUMOS)

        col1, col2, col3 = st.columns(3)
        busca   = col1.text_input("Buscar")
        familia = col2.selectbox("Familia", ["Todos"] + sorted(df_sinapi['familia'].unique().tolist()))
        tipo    = col3.selectbox("Tipo",    ["Todos"] + sorted(df_sinapi['tipo'].unique().tolist()))

        df_f = df_sinapi.copy()
        if busca:
            df_f = df_f[df_f['nome'].str.contains(busca, case=False)]
        if familia != "Todos":
            df_f = df_f[df_f['familia'] == familia]
        if tipo != "Todos":
            df_f = df_f[df_f['tipo'] == tipo]

        st.dataframe(df_f, use_container_width=True)
        st.caption(str(len(df_f)) + " itens | SINAPI RO Mar/2026")

    elif sub2 == "Tabelas de Precos":
        st.subheader("Tabelas de Precos Referenciais")
        tabelas = {
            "SINAPI - Caixa/IBGE": "Nacional - Obras em Geral",
            "SICRO - DNIT":        "Infraestrutura Rodoviaria",
            "ORSE - Sergipe":      "Edificacoes Regionais",
            "SEINFRA-CE":          "Referencia Regional CE",
            "SINAPI-RO Local":     "Rondonia - Atualizado Mar/2026",
        }
        st.table(pd.DataFrame(list(tabelas.items()), columns=["Tabela", "Aplicacao"]))
        st.info("Upload de tabelas personalizadas em breve.")

        st.subheader("Indices SINAPI por Estado e Mes")
        col1, col2, col3, col4 = st.columns(4)
        est_idx = col1.selectbox("Estado", list(ESTADOS_SINAPI.keys()), key="est_pesq")
        mes_idx = col2.selectbox("Mes", list(range(1, 13)), key="mes_pesq")
        ano_idx = col3.number_input("Ano", value=2025, min_value=2020, max_value=2026, key="ano_pesq")
        des_idx = col4.checkbox("Desonerado", key="des_pesq")

        if st.button("Buscar Indice SINAPI"):
            with st.spinner("Consultando IBGE FTP..."):
                idx, msg = buscar_sinapi_ibge(int(ano_idx), int(mes_idx), est_idx, des_idx)
            if idx:
                st.success("Indice SINAPI " + est_idx + " " + str(mes_idx) + "/" + str(ano_idx) + ": " + str(idx))
            else:
                st.warning(msg)

# ─────────────────────────────────────────
# 6. REAJUSTES
# ─────────────────────────────────────────
elif page == "📈 Reajustes":
    st.header("Calculo de Reajustes - Lei 14.133")

    df_c = pd.read_sql("SELECT * FROM contratos", conn)
    if df_c.empty:
        st.warning("Cadastre contratos primeiro.")
    else:
        sel = st.selectbox("Selecionar Contrato", df_c['id'],
                           format_func=lambda x: df_c[df_c['id']==x]['numero'].values[0])
        row = df_c[df_c['id']==sel].iloc[0]

        # Busca planilha vinculada
        df_plan = pd.read_sql(
            "SELECT * FROM planilhas_orcamentarias WHERE contrato_id=?",
            conn, params=(sel,)
        )

        col1, col2, col3 = st.columns(3)
        col1.metric("Contrato", str(row['numero']))
        col1.metric("Indice Io", "{:.4f}".format(row['reajuste_base']))
        col2.metric("Data-Base", str(row['dt_base'])[:10])
        col2.metric("Valor Total", "R$ " + "{:,.2f}".format(row['valor_total']))

        if not df_plan.empty:
            col3.info("📋 Planilha: " + str(df_plan.iloc[0]['arquivo_nome']))
            col3.info("Indice: " + str(df_plan.iloc[0]['indice_referencia']) + " | " + str(df_plan.iloc[0]['mes_ano_referencia']))
        else:
            col3.warning("Sem planilha orcamentaria vinculada.")

        hoje = date.today()
        try:
            dt_est = datetime.strptime(str(row['data_estimado'])[:10], "%Y-%m-%d").date()
            dias   = (hoje - dt_est).days
            if dias < 365:
                st.warning("Periodo minimo nao atingido! " + str(365 - dias) + " dias restantes.")
            else:
                st.success("Elegivel para reajuste!")
        except:
            pass

        st.markdown("---")
        col1, col2 = st.columns(2)
        with col1:
            indices_disponiveis = ["SINAPI-RO", "SICRO-DNIT", "INCC", "IPCA", "IGP-M"]
            if not df_plan.empty:
                idx_planilha = str(df_plan.iloc[0]['indice_referencia'])
                if idx_planilha not in indices_disponiveis:
                    indices_disponiveis.insert(0, idx_planilha)
            indice_tipo = st.selectbox("Indice", indices_disponiveis)
            Ii = st.number_input("Indice Ii (mes reajuste)", value=float(row['reajuste_base']) * 1.05, format="%.4f")
        with col2:
            V = st.number_input("Valor V (Remanescente R$)", value=float(row['valor_remanescente']), format="%.2f")

        if st.button("Calcular Reajuste"):
            Io = float(row['reajuste_base'])
            R  = ((Ii - Io) / Io) * V

            col1, col2, col3 = st.columns(3)
            col1.metric("Indice Io", "{:.4f}".format(Io))
            col2.metric("Indice Ii", "{:.4f}".format(Ii))
            col3.metric("Reajuste R", "R$ " + "{:,.2f}".format(R))

            st.markdown("---")
            st.subheader("Memoria de Calculo")
            linha1 = "Formula: R = ((Ii - Io) / Io) x V"
            linha2 = "R = ((" + "{:.4f}".format(Ii) + " - " + "{:.4f}".format(Io) + ") / " + "{:.4f}".format(Io) + ") x " + "{:,.2f}".format(V)
            linha3 = "R = R$ " + "{:,.2f}".format(R)
            st.code(linha1 + "\n" + linha2 + "\n" + linha3, language="")

            col1, col2 = st.columns(2)
            col1.info("Indice: " + indice_tipo)
            col1.info("Data: " + hoje.strftime("%d/%m/%Y"))
            col2.success("Valor V: R$ " + "{:,.2f}".format(V))
            col2.success("Reajuste R: R$ " + "{:,.2f}".format(R))
            st.metric("Novo Valor Total", "R$ " + "{:,.2f}".format(float(row['valor_total']) + R))

            if st.button("Salvar Reajuste"):
                conn.execute("UPDATE contratos SET indice_atual=?, reajuste_calculado=? WHERE id=?", (Ii, R, sel))
                conn.commit()
                st.success("Reajuste salvo!")

# ─────────────────────────────────────────
# 7. RELATORIOS
# ─────────────────────────────────────────
elif page == "📄 Relatorios":
    st.header("Relatorios e Exportacoes")

    tab1, tab2, tab3 = st.tabs(["Contratos", "Orcamentos", "Planilhas"])

    with tab1:
        df_c = pd.read_sql("SELECT * FROM contratos", conn)
        if df_c.empty:
            st.info("Nenhum contrato para exportar.")
        else:
            st.dataframe(df_c, use_container_width=True)
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df_c.to_excel(writer, sheet_name='Contratos', index=False)
            st.download_button("Exportar Contratos Excel", output.getvalue(), "contratos_pmro.xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    with tab2:
        df_o = pd.read_sql("SELECT * FROM orcamentos", conn)
        if df_o.empty:
            st.info("Nenhum orcamento para exportar.")
        else:
            st.dataframe(df_o[['id','nome','status','bdi','valor_total','data_criacao']], use_container_width=True)
            output2 = io.BytesIO()
            with pd.ExcelWriter(output2, engine='openpyxl') as writer:
                df_o.to_excel(writer, sheet_name='Orcamentos', index=False)
            st.download_button("Exportar Orcamentos Excel", output2.getvalue(), "orcamentos_pmro.xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    with tab3:
        df_p = pd.read_sql("""
            SELECT p.id, c.numero as contrato, p.arquivo_nome,
                   p.indice_referencia, p.mes_ano_referencia,
                   p.desonerado, p.valor_total, p.data_upload
            FROM planilhas_orcamentarias p
            LEFT JOIN contratos c ON p.contrato_id = c.id
        """, conn)
        if df_p.empty:
            st.info("Nenhuma planilha cadastrada.")
        else:
            st.dataframe(df_p, use_container_width=True)
            output3 = io.BytesIO()
            with pd.ExcelWriter(output3, engine='openpyxl') as writer:
                df_p.to_excel(writer, sheet_name='Planilhas', index=False)
            st.download_button("Exportar Planilhas Excel", output3.getvalue(), "planilhas_pmro.xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# ─────────────────────────────────────────
# FOOTER
# ─────────────────────────────────────────
st.markdown("---")
st.caption("PMRO Enterprise SEINFRA v6.4 | Eng. Guilherme Ritter Baldin | Porto Velho/RO | " + str(date.today().year))
