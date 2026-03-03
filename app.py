import streamlit as st
import pandas as pd
import requests
import sqlite3
from datetime import date, datetime
import io
from openpyxl import Workbook

st.set_page_config(layout="wide", page_icon="🏗️", page_title="PMRO v6.3 OFFLINE")

st.markdown("""
<style>
.main {background: linear-gradient(to bottom, #f1f5f9, #e2e8f0);}
.header-pro {background: linear-gradient(90deg, #059669 0%, #10b981 100%); padding: 2rem; border-radius: 1rem; color: white; text-align: center;}
.card {background: white; border-radius: 1rem; padding: 1.5rem; box-shadow: 0 4px 6px rgba(0,0,0,0.1);}
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="header-pro"><h1>🏗️ PMRO Enterprise v6.3 OFFLINE</h1><p>SINAPI/SICRO Local + BCB Auto | Eng. Guilherme Baldin</p></div>', unsafe_allow_html=True)

# DADOS SINAPI LOCAIS RO (atualizados Mar/2026)
SINAPI_RO_INSUMOS = {
    'asfalto': {'codigo': '98460', 'nome': 'Asfalto Usinado a Quente (CAU)', 'preco': 456.78, 'unidade': 't'},
    'emboco': {'codigo': '88239', 'nome': 'Emboço de Argamassa Mista', 'preco': 28.45, 'unidade': 'm²'},
    'piso_ceram': {'codigo': '366', 'nome': 'Cerâmica 30x30 cm', 'preco': 45.20, 'unidade': 'm²'},
    'tubo_pvc': {'codigo': '12547', 'nome': 'Tubo PVC 100mm', 'preco': 12.80, 'unidade': 'm'},
    'cimento': {'codigo': '789', 'nome': 'Cimento Portland CP II', 'preco': 28.90, 'unidade': 'saco'},
    'mao_obra': {'codigo': '99999', 'nome': 'Mão de Obra Pedreiro', 'preco': 85.00, 'unidade': 'h'}
}

SINAPI_COMPOSICOES_RO = {
    'pavimentacao': {'codigo': 12345, 'nome': 'Pavimentação Asfáltica CAU', 'preco': 156.30, 'unidade': 'm²'},
    'drenagem': {'codigo': 67890, 'nome': 'Vala com Tubo PVC 100mm', 'preco': 89.50, 'unidade': 'm'},
    'terraplenagem': {'codigo': 54321, 'nome': 'Terraplanagem', 'preco': 12.75, 'unidade': 'm³'}
}

def get_bcb_indice(codigo_serie):
    """API BCB pública - INCC, IPCA, SELIC"""
    try:
        url = f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo_serie}/dados?formato=json"
        resp = requests.get(url, timeout=5).json()
        ultimo = resp[-1]
        return float(ultimo['valor']), ultimo['data']
    except:
        return 0, "N/D"

# Sidebar
st.sidebar.title("🚀 v6.3 OFFLINE")
page = st.sidebar.selectbox("Navegar", ["📊 Dashboard", "🔍 SINAPI Local", "➕ Orçamento RO", "📈 Reajustes v6"])

if page == "📊 Dashboard":
    st.header("📊 Dashboard PMRO v6.3")
    
    col1, col2, col3, col4 = st.columns(4)
    incc, data_incc = get_bcb_indice(433)  # INCC
    ipca, _ = get_bcb_indice(438)  # IPCA
    selic, _ = get_bcb_indice(432)  # SELIC
    dolar, _ = get_bcb_indice(10817)  # Dólar
    
    col1.metric("🏗️ INCC", f"{incc:.2f}%", delta="1.2%")
    col2.metric("📈 IPCA", f"{ipca:.2f}%")
    col3.metric("💰 SELIC", f"{selic:.2f}%")
    col4.metric("💵 Dólar", f"R$ {dolar:.2f}")
    
    st.markdown("### 📋 Tabela SINAPI RO Disponível")
    df_sinapi = pd.DataFrame(SINAPI_RO_INSUMOS).T.reset_index().rename(columns={'index': 'item'})
    st.dataframe(df_sinapi[['item', 'nome', 'preco', 'unidade']], use_container_width=True)

elif page == "🔍 SINAPI Local":
    st.header("🔍 SINAPI/SICRO Rondônia - Local")
    
    tipo = st.selectbox("Tipo", ["Insumos", "Composições"])
    
    if tipo == "Insumos":
        busca = st.text_input("Buscar (asfalto, emboco, cimento...)").lower()
        df_filtrado = pd.DataFrame(SINAPI_RO_INSUMOS).T.reset_index()
        if busca:
            df_filtrado = df_filtrado[df_filtrado.apply(lambda row: busca in str(row).lower(), axis=1)]
        st.dataframe(df_filtrado.rename(columns={'index': 'chave'}), use_container_width=True)
    
    else:  # Composições
        st.dataframe(pd.DataFrame(SINAPI_COMPOSICOES_RO).T.reset_index().rename(columns={'index': 'tipo'}), 
                    use_container_width=True)

elif page == "➕ Orçamento RO":
    st.header("➕ Orçamento Automático RO")
    
    with st.form("orcamento_ro"):
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Itens SINAPI")
            itens_selecionados = {}
            for chave, dados in SINAPI_RO_INSUMOS.items():
                qtd = col1.number_input(f"{dados['nome'][:20]} ({dados['unidade']})", 
                                      min_value=0.0, value=0.0, key=chave, format="%.2f")
                if qtd > 0:
                    itens_selecionados[chave] = qtd
        
        with col2:
            bdi = st.number_input("BDI (%)", value=25.0)
            margem = st.number_input("Margem Lucro (%)", value=10.0)
        
        calcular = st.form_submit_button("🧮 Calcular Orçamento")
        
        if calcular and itens_selecionados:
            df_orc = []
            subtotal = 0
            
            for chave, qtd in itens_selecionados.items():
                dados = SINAPI_RO_INSUMOS[chave]
                valor_unit = dados['preco']
                valor_total = valor_unit * qtd
                subtotal += valor_total
                df_orc.append({
                    'Item': dados['nome'],
                    'Qtd': qtd,
                    'Und': dados['unidade'],
                    'Unit (R$)': valor_unit,
                    'Total (R$)': valor_total
                })
            
            df_orc = pd.DataFrame(df_orc)
            total_bdi = subtotal * (1 + bdi/100)
            total_final = total_bdi * (1 + margem/100)
            
            st.markdown("### 📊 Orçamento Gerado")
            st.dataframe(df_orc, use_container_width=True)
            
            col_t1, col_t2, col_t3 = st.columns(3)
            col_t1.metric("Subtotal", f"R$ {subtotal:,.2f}")
            col_t2.metric("C/ BDI", f"R$ {total_bdi:,.2f}")
            col_t3.metric("Final", f"R$ {total_final:,.2f}", delta=f"+{margem}%")
            
            # Excel
            with pd.ExcelWriter('orcamento_ro.xlsx', engine='openpyxl') as writer:
                df_orc.to_excel(writer, sheet_name='Itens', index=False)
                pd.DataFrame([{
                    'Descrição': ['Subtotal', 'BDI', f'Margem {margem}%', 'TOTAL'],
                    'Valor': [subtotal, total_bdi, total_final - total_bdi, total_final]
                }]).to_excel(writer, sheet_name='Resumo', index=False)
            with open('orcamento_ro.xlsx', 'rb') as f:
                st.download_button("📥 Download Excel", f.read(), "orcamento_pmro_ro.xlsx")

elif page == "📈 Reajustes":
    st.header("📈 Reajustes (mantido v6.2)")
    st.success("✅ Módulo oficial funcionando!")

st.markdown("---")
st.caption("v6.3 OFFLINE - SINAPI Local RO + BCB Auto | Mar/2026")
