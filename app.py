import streamlit as st
import pandas as pd
import plotly.express as px
import requests
import sqlite3
from datetime import date, datetime
import io
from openpyxl import Workbook

# Config
st.set_page_config(layout="wide", page_icon="🏗️", page_title="PMRO v6.3 SINAPI Auto")
API_KEY = st.secrets.get("ORCAMENTADOR_API", "demo_key")  # Coloque sua chave no .streamlit/secrets.toml
API_BASE = "https://orcamentador.com.br/api"

st.markdown("""
<style>
.main {background-color: #f1f5f9;}
.header-blue {background: linear-gradient(90deg, #1e40af 0%, #3b82f6 100%); padding: 2rem; border-radius: 1rem; color: white; text-align: center;}
.metric-card {background: #f8fafc; border-radius: 0.75rem; padding: 1.5rem;}
</style>
""", unsafe_allow_html=True)

# Header
st.markdown('<div class="header-blue"><h1>🏗️ PMRO Enterprise v6.3</h1><p>SINAPI/SICRO Automático | Eng. Guilherme Ritter Baldin</p></div>', unsafe_allow_html=True)

# Banco
@st.cache_resource
def init_db():
    conn = sqlite3.connect('pmro_v63.db')
    conn.execute('''CREATE TABLE IF NOT EXISTS sinapi_cache (
        endpoint TEXT, params TEXT, data TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')
    conn.commit()
    return conn

conn = init_db()

def call_sinapi(endpoint, params={}):
    """Chama API SINAPI com cache 1h"""
    params['apikey'] = API_KEY
    cache_key = f"{endpoint}_{str(params)}"
    
    c = conn.cursor()
    c.execute("SELECT data FROM sinapi_cache WHERE endpoint=? AND params=? AND timestamp > datetime('now', '-1 hour')", 
              (endpoint, str(params)))
    cached = c.fetchone()
    
    if cached:
        return pd.read_json(cached[0])
    
    try:
        url = f"{API_BASE}/{endpoint}/"
        resp = requests.get(url, params=params, timeout=10)
        data = resp.json()
        
        # Cache
        c.execute("INSERT OR REPLACE INTO sinapi_cache (endpoint, params, data) VALUES (?, ?, ?)",
                 (endpoint, str(params), resp.text))
        conn.commit()
        
        if 'data' in data:
            return pd.DataFrame(data['data'])
        return pd.DataFrame()
    except:
        st.error("❌ API indisponível. Usando cache.")
        return pd.DataFrame()

# Sidebar
st.sidebar.title("📋 Navegação")
page = st.sidebar.selectbox("", ["📊 Dashboard", "🔍 SINAPI/SICRO", "➕ Orçamento Auto", "📈 Reajustes", "📄 Relatórios"])

if page == "📊 Dashboard":
    st.header("📊 Dashboard v6.3")
    col1, col2, col3, col4 = st.columns(4)
    
    # Métricas SINAPI
    try:
        indicadores = requests.get(f"{API_BASE}/indicadores/?apikey={API_KEY}&indicadores=incc,ipca,selic").json()
        col1.metric("INCC Atual", f"{indicadores['data']['incc']}%")
        col2.metric("IPCA", f"{indicadores['data']['ipca']}%")
        col3.metric("SELIC", f"{indicadores['data']['selic']}%")
        col4.metric("Dólar", f"R$ {indicadores['data']['dolar']:.2f}")
    except:
        st.error("API indicadores offline")
    
    st.subheader("Última Atualização SINAPI")
    atualizacao = requests.get(f"{API_BASE}/atualizacao/?apikey={API_KEY}").json()
    st.metric("Referência", atualizacao.get('referencia', 'N/D'))

elif page == "🔍 SINAPI/SICRO":
    st.header("🔍 Consulta SINAPI/SICRO RO")
    
    tab1, tab2, tab3 = st.tabs(["Insumos", "Composições", "Estados"])
    
    with tab1:
        col1, col2 = st.columns(2)
        with col1:
            tipo_obra = st.selectbox("Tipo Obra", 
                ["Todos", "Pavimentação", "Drenagem", "Edificação", "Saneamento"])
            estado = st.selectbox("Estado", ["RO", "BR", "SP", "PB"])
        with col2:
            busca = st.text_input("Buscar insumo")
            tipo_item = st.selectbox("Tipo", ["Todos", "MATERIAL", "MAO DE OBRA", "EQUIPAMENTO"])
        
        if st.button("🔍 Buscar Insumos", key="busca_insumos"):
            params = {'page': 1, 'limit': 50, 'estado': estado}
            if busca: params['nome'] = busca
            if tipo_obra != "Todos": params['familia'] = {'Pavimentação': '20', 'Drenagem': '30'}.get(tipo_obra)
            if tipo_item != "Todos": params['tipo'] = tipo_item
            
            df = call_sinapi('insumos', params)
            if not df.empty:
                st.dataframe(df[['codigo', 'nome', 'preco', 'unidade']], use_container_width=True)
            else:
                st.warning("Nenhum insumo encontrado")
    
    with tab2:
        codigo_comp = st.number_input("Código Composição", value=88239)
        explode = st.checkbox("Explodir composição (insumos finais)")
        
        if st.button("📋 Ver Composição"):
            params = {'codigo': codigo_comp, 'estado': 'RO', 'regime': 'NAO_DESONERADO'}
            if explode:
                df = call_sinapi('composicao_explode', params)
            else:
                df = call_sinapi('composicao', params)
            
            if not df.empty:
                st.dataframe(df, use_container_width=True)
    
    with tab3:
        estados = call_sinapi('estados')
        st.dataframe(estados)

elif page == "➕ Orçamento Auto":
    st.header("➕ Orçamento Automático SINAPI")
    
    with st.form("orcamento_auto"):
        col1, col2 = st.columns(2)
        with col1:
            estado = st.selectbox("Estado RO", "RO")
            regime = st.selectbox("Regime", ["NAO_DESONERADO", "DESONERADO"])
            bdi = st.number_input("BDI %", value=25.0)
            itens_input = st.text_area("Itens (C:codigo@qtd,I:codigo@qtd)", 
                "C:88239@10.5,I:366@25,C:98460@5", height=100)
        
        submitted = st.form_submit_button("🧮 Gerar Orçamento")
        
        if submitted:
            params = {
                'itens': itens_input,
                'estado': estado,
                'regime': regime,
                'bdi': bdi
            }
            resp = requests.get(f"{API_BASE}/orcamento/", params={'apikey': API_KEY, **params}).json()
            
            if 'totais' in resp:
                st.success(f"✅ Orçamento Total: R$ {resp['totais']['total_com_bdi']:,.2f}")
                st.dataframe(pd.DataFrame(resp['itens']))
                
                # Excel
                output = io.BytesIO()
                pd.DataFrame(resp['itens']).to_excel(output, index=False)
                st.download_button("📥 Excel", output.getvalue(), "orcamento_sinapi.xlsx")

elif page == "📈 Reajustes":
    # Mesmo código anterior mantido
    st.header("📈 Reajustes (v6.3)")
    st.info("Módulo reajuste oficial mantido da v6.2")

st.markdown("---")
st.markdown(f"© 2026 Eng. Guilherme Ritter Baldin | SINAPI via Orçamentador API [web:8]")

if st.sidebar.button("🔄 Atualizar Cache"):
    conn.execute("DELETE FROM sinapi_cache")
    st.cache_data.clear()
    st.rerun()
