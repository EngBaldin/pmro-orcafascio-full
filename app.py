import streamlit as st
import pandas as pd
import plotly.express as px
import sqlite3
import io
import re
import pdfplumber
import requests
from openpyxl import Workbook
from datetime import datetime, date

st.set_page_config(layout="wide", page_icon="🏗️", page_title="PMRO Enterprise SEINFRA v6.3")

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
    <h1>🏗️ PMRO Enterprise SEINFRA v6.3</h1>
    <p>Gestão de Contratos · SINAPI/SICRO · Reajustes · Orçamentos</p>
    <small>Eng. Guilherme Ritter Baldin | Porto Velho - RO</small>
</div>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────
# BANCO DE DADOS
# ─────────────────────────────────────────
@st.cache_resource
def init_db():
    conn = sqlite3.connect('pmro_contratos.db', check_same_thread=False)
    conn.execute('''CREATE TABLE IF NOT EXISTS contratos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        numero TEXT, objeto TEXT,
        data_estimado TEXT, reajuste_base REAL,
        dt_base TEXT, valor_total REAL,
        valor_remanescente REAL, indice_atual REAL,
        reajuste_calculado REAL,
        data_cadastro TEXT DEFAULT CURRENT_DATE
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS sinapi_cache (
        endpoint TEXT, params TEXT, data TEXT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')
    conn.commit()
    return conn

conn = init_db()

# ─────────────────────────────────────────
# DADOS SINAPI RO LOCAL (atualizado Mar/2026)
# ─────────────────────────────────────────
SINAPI_INSUMOS = [
    {"codigo":"98460","nome":"Asfalto Usinado a Quente CAU","unidade":"t","preco":456.78,"tipo":"MATERIAL","familia":"Pavimentação"},
    {"codigo":"88239","nome":"Emboço de Argamassa Mista","unidade":"m²","preco":28.45,"tipo":"COMPOSICAO","familia":"Edificação"},
    {"codigo":"366","nome":"Cerâmica 30x30 cm","unidade":"m²","preco":45.20,"tipo":"MATERIAL","familia":"Edificação"},
    {"codigo":"12547","nome":"Tubo PVC 100mm","unidade":"m","preco":12.80,"tipo":"MATERIAL","familia":"Drenagem"},
    {"codigo":"789","nome":"Cimento Portland CP II","unidade":"sc 50kg","preco":28.90,"tipo":"MATERIAL","familia":"Geral"},
    {"codigo":"4209","nome":"Areia Média Lavada","unidade":"m³","preco":89.00,"tipo":"MATERIAL","familia":"Geral"},
    {"codigo":"7155","nome":"Brita n°1","unidade":"m³","preco":110.00,"tipo":"MATERIAL","familia":"Geral"},
    {"codigo":"11703","nome":"Aço CA-50 12mm","unidade":"kg","preco":8.75,"tipo":"MATERIAL","familia":"Edificação"},
    {"codigo":"99990","nome":"Pedreiro","unidade":"h","preco":21.50,"tipo":"MAO DE OBRA","familia":"Geral"},
    {"codigo":"99991","nome":"Servente","unidade":"h","preco":15.30,"tipo":"MAO DE OBRA","familia":"Geral"},
    {"codigo":"55210","nome":"Escavação Mecânica Solo","unidade":"m³","preco":5.80,"tipo":"COMPOSICAO","familia":"Terraplenagem"},
    {"codigo":"93358","nome":"Subleito Compactado","unidade":"m³","preco":9.40,"tipo":"COMPOSICAO","familia":"Pavimentação"},
    {"codigo":"97528","nome":"Meio Fio 15x30 cm","unidade":"m","preco":42.10,"tipo":"COMPOSICAO","familia":"Pavimentação"},
    {"codigo":"74104","nome":"Tubo Concreto Ø 60cm","unidade":"m","preco":185.00,"tipo":"MATERIAL","familia":"Drenagem"},
    {"codigo":"80842","nome":"Caixa de Passagem 60x60","unidade":"un","preco":350.00,"tipo":"COMPOSICAO","familia":"Drenagem"},
]

# ─────────────────────────────────────────
# BCB API (pública, sem chave)
# ─────────────────────────────────────────
@st.cache_data(ttl=3600)
def get_bcb(codigo):
    try:
        url = f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados?formato=json"
        r = requests.get(url, timeout=5).json()
        return float(r[-1]['valor']), r[-1]['data']
    except:
        return 0.0, "N/D"

# ─────────────────────────────────────────
# SIDEBAR MENU
# ─────────────────────────────────────────
st.sidebar.title("📋 Menu Principal")
page = st.sidebar.radio("", [
    "📊 Dashboard",
    "📑 Contratos",
    "📈 Reajustes",
    "🔍 SINAPI/SICRO",
    "➕ Orçamento",
    "📄 Relatórios"
])

if st.sidebar.button("🔄 Atualizar Dados BCB"):
    st.cache_data.clear()
    st.rerun()

# ─────────────────────────────────────────
# 1. DASHBOARD
# ─────────────────────────────────────────
if page == "📊 Dashboard":
    st.header("📊 Dashboard Geral")

    # Indicadores BCB
    incc, dt_incc   = get_bcb(433)
    ipca, _         = get_bcb(438)
    selic, _        = get_bcb(432)
    igpm, _         = get_bcb(189)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("🏗️ INCC Mensal", f"{incc:.2f}%", delta=f"ref {dt_incc}")
    col2.metric("📈 IPCA Mensal", f"{ipca:.2f}%")
    col3.metric("💰 SELIC", f"{selic:.2f}%")
    col4.metric("📉 IGP-M", f"{igpm:.2f}%")

    st.markdown("---")

    # Métricas contratos
    df_c = pd.read_sql("SELECT * FROM contratos", conn)
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Contratos", len(df_c))
    col2.metric("Valor Total Carteira", f"R$ {df_c['valor_total'].sum():,.2f}" if not df_c.empty else "R$ 0,00")
    
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
    col3.metric("⚠️ Pendentes Reajuste", pendentes)
    col4.metric("Reajustes Calculados", f"R$ {df_c['reajuste_calculado'].sum():,.2f}" if not df_c.empty else "R$ 0,00")

    # Gráfico
    if not df_c.empty:
        fig = px.bar(df_c, x='numero', y='valor_total',
                     title="Valor por Contrato (R$)",
                     color='reajuste_calculado',
                     labels={'numero': 'Contrato', 'valor_total': 'Valor (R$)'},
                     color_continuous_scale='Blues')
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("📋 Contratos Ativos")
    if not df_c.empty:
        st.dataframe(df_c, use_container_width=True)
    else:
        st.info("Nenhum contrato cadastrado ainda.")

# ─────────────────────────────────────────
# 2. CONTRATOS
# ─────────────────────────────────────────
elif page == "📑 Contratos":
    st.header("📑 Gestão de Contratos")

    tab1, tab2 = st.tabs(["➕ Novo Contrato", "📋 Contratos Cadastrados"])

    with tab1:
        with st.form("form_contrato"):
            col1, col2 = st.columns(2)
            with col1:
                numero    = st.text_input("Número do Contrato *", placeholder="Ex: 001/2026")
                objeto    = st.text_area("Objeto *", height=100)
                data_est  = st.date_input("Data Orçamento Estimado *", value=date.today())
                dt_base   = st.date_input("Data-Base Io *", value=date(2025, 1, 1))
            with col2:
                ind_base  = st.number_input("Índice Base Io (SINAPI/SICRO) *", value=100.0, format="%.4f")
                val_total = st.number_input("Valor Total Contratado R$ *", value=1000000.0, format="%.2f")
                val_rem   = st.number_input("Valor Remanescente R$ *", value=800000.0, format="%.2f")
                st.caption("⚠️ Período mínimo 1 ano para reajuste (Lei 14.133)")

            salvar = st.form_submit_button("💾 Salvar Contrato")
            if salvar:
                if not numero or not objeto:
                    st.error("Preencha todos os campos obrigatórios!")
                else:
                    conn.execute('''INSERT INTO contratos
                        (numero, objeto, data_estimado, reajuste_base, dt_base, valor_total, valor_remanescente)
                        VALUES (?, ?, ?, ?, ?, ?, ?)''',
                        (numero, objeto, str(data_est), ind_base, str(dt_base), val_total, val_rem))
                    conn.commit()
                    st.success(f"✅ Contrato {numero} salvo!")
                    st.balloons()

    with tab2:
        df_c = pd.read_sql("SELECT * FROM contratos", conn)
        if df_c.empty:
            st.info("Nenhum contrato cadastrado.")
        else:
            st.dataframe(df_c, use_container_width=True)
            # Exclusão
            del_id = st.number_input("ID para excluir", min_value=0, step=1)
            if st.button("🗑️ Excluir Contrato") and del_id > 0:
                conn.execute("DELETE FROM contratos WHERE id=?", (del_id,))
                conn.commit()
                st.success("Excluído!")
                st.rerun()

# ─────────────────────────────────────────
# 3. REAJUSTES
# ─────────────────────────────────────────
elif page == "📈 Reajustes":
    st.header("📈 Cálculo de Reajustes — Lei 14.133")

    df_c = pd.read_sql("SELECT * FROM contratos", conn)
    if df_c.empty:
        st.warning("Cadastre contratos primeiro.")
    else:
        sel = st.selectbox("Selecionar Contrato",
                           df_c['id'],
                           format_func=lambda x: df_c[df_c['id']==x]['numero'].values[0])
        row = df_c[df_c['id']==sel].iloc[0]

        col1, col2, col3 = st.columns(3)
        col1.metric("Nº Contrato", row['numero'])
        col1.metric("Índice Io", f"{row['reajuste_base']:.4f}")
        col2.metric("Data-Base", str(row['dt_base'])[:10])
        col2.metric("Valor Total", f"R$ {row['valor_total']:,.2f}")

        # Verificar anualidade
        hoje = date.today()
        try:
            dt_est = datetime.strptime(str(row['data_estimado'])[:10], "%Y-%m-%d").date()
            dias = (hoje - dt_est).days
            if dias < 365:
                col3.warning(f"⚠️ Período mínimo não atingido!\n{365-dias} dias restantes.")
            else:
                col3.success("✅ Elegível para reajuste!")
        except:
            pass

        st.markdown("---")
        col1, col2 = st.columns(2)
        with col1:
            indice_tipo = st.selectbox("Índice de Reajuste", ["SINAPI-RO", "SICRO-DNIT", "INCC", "IPCA", "IGP-M"])
            Ii = st.number_input("Índice Ii (mês reajuste)", value=float(row['reajuste_base'])*1.05, format="%.4f")
        with col2:
            V  = st.number_input("Valor V (Remanescente R$)", value=float(row['valor_remanescente']), format="%.2f")

        if st.button("🧮 Calcular Reajuste"):
            Io = float(row['reajuste_base'])
            # FÓRMULA OFICIAL: R = ((Ii - Io) / Io) × V
            R  = ((Ii - Io) / Io) * V

            col1, col2, col3 = st.columns(3)
            col1.metric("Índice Io", f"{Io:.4f}")
            col2.metric("Índice Ii", f"{Ii:.4f}")
            col3.metric("💰 Reajuste (R)", f"R$ {R:,.2f}")

            st.markdown(f"""
### 📋 Memória de Cálculo — Reajuste Contrato {row['numero']}

**Fórmula Legal (Lei 14.133/2021):**
