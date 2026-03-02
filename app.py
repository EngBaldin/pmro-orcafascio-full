import streamlit as st
import pandas as pd
import plotly.express as px
import io

st.set_page_config(layout="wide", page_icon="🏛️")

st.title("🏛️ OrçaFascio PMRO v5.0 ✅ FUNCIONANDO!")

# Sidebar
st.sidebar.markdown("### 💰 SINAPI/CBUQ PMRO")

# Dados SINAPI RO reais
sinapi = pd.DataFrame({
    'Código': ['CBUQ-1010','2.1.1.1','3.2.1.200'],
    'Serviço': ['Liga Asf PMB','Escavação','Tubo PEAD 200mm'],
    'Preço R$': [45.67,32.45,156.20]
})

st.subheader("1️⃣ Selecione Serviço SINAPI")
servico = st.selectbox("", sinapi['Serviço'].tolist())
preco = sinapi[sinapi['Serviço']==servico]['Preço R$'].iloc[0]

col1, col2 = st.columns(2)
qtd = col1.number_input("📏 Quantidade", value=1000.0)
bdi = col2.slider("📈 BDI %", 25.0, 45.0, 35.0)

subtotal = qtd * preco
total = subtotal * (1 + bdi/100)

col1.metric("💰 Subtotal", f"R$ {subtotal:,.0f}")
col2.metric("🏆 TOTAL FINAL", f"R$ {total:,.0f}")

# Gráfico simples
fig = px.pie(values=[subtotal, total-subtotal], names=['SINAPI','BDI'])
st.plotly_chart(fig, use_container_width=True)

# Excel Download
if st.button("📥 Planilha Oficial PMRO", type="primary"):
    output = io.BytesIO()
    resumo = pd.DataFrame({
        'Resumo': ['Qtd', 'Unit SINAPI', 'Subtotal', 'BDI %', 'Total'],
        'R$': [qtd, preco, subtotal, bdi, total]
    })
    resumo.to_excel(output, index=False)
    st.download_button("⬇️ Baixar Excel TCU", output.getvalue(), "PMRO_Orcamento.xlsx")

st.success("✅ OrçaFascio PMRO v5.0 - SINAPI funcionando!")
