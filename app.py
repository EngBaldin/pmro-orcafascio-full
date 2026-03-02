import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import sqlite3
import io

st.set_page_config(layout="wide", page_icon="🏛️")

st.markdown("""
<style>
.main {background-color: #f8fafc;}
</style>
""", unsafe_allow_html=True)

# Sidebar
with st.sidebar:
    st.markdown("""
    <div style='background: linear-gradient(90deg,#1e3a8a,#3b82f6);padding:2rem;border-radius:15px;color:white;text-align:center;'>
        <h2>🏛️ OrçaFascio PMRO v5.0</h2>
    </div>
    """, unsafe_allow_html=True)
    
    page = st.selectbox("Módulos", ["💰 SINAPI/CBUQ", "📊 Dashboard"])

# SINAPI PMRO [code_file:18]
if page == "💰 SINAPI/CBUQ":
    st.title("💰 Orçamentista PMRO")
    
    # Tabela SINAPI REAL RO[code_file:18]
    sinapi_data = {
        'Código': ['CBUQ-1010','CBUQ-2010','2.1.1.1','3.2.1.200'],
        'Serviço': ['Liga Asf PMB 40/50','Tinta asfáltica','Escavação manual','Tubo PEAD 200mm'],
        'Preço R$': [45.67,28.90,32.45,156.20],
        'Und': ['m²','m²','m³','m']
    }
    sinapi_df = pd.DataFrame(sinapi_data)[code_file:18]
    
    st.subheader("1. Selecione Serviço")
    col1,col2,col3 = st.columns(3)
    with col1: servico = st.selectbox("", sinapi_df['Serviço'])
    with col2: qtd = st.number_input("Qtd", value=1000.0)
    with col3: preco = sinapi_df[sinapi_df['Serviço']==servico]['Preço R$'].iloc[0]
    
    st.metric("Unitário SINAPI", f"R$ {preco:.2f}")
    
    bdi = st.slider("BDI PMRO %", 25.0, 45.0, 35.0)
    subtotal = qtd * preco
    total = subtotal * (1 + bdi/100)
    
    col1,col2 = st.columns(2)
    col1.metric("Subtotal", f"R$ {subtotal:,.0f}")
    col2.metric("TOTAL + BDI", f"R$ {total:,.0f}")
    
    # Gráfico
    fig = px.pie(values=[subtotal,subtotal*(bdi/100)], names=['Materiais','BDI'])
    st.plotly_chart(fig)
    
    # Download
    if st.button("📥 Excel Oficial PMRO"):
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            pd.DataFrame({'Resumo':['Qtd','Unit','Subtotal','BDI %','Total'], 
                         'R$':[qtd,preco,subtotal,bdi,total]}).to_excel(writer, 'Resumo')
            sinapi_df.to_excel(writer, 'SINAPI_RO', index=False)
        st.download_button("⬇️ PMRO_Orcamento.xlsx", output.getvalue(), "PMRO_Orcamento.xlsx")

st.markdown("🏛️ OrçaFascio PMRO v5.0 | Eng. Guilherme Baldin")[code_file:18]
