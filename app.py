import streamlit as st
import pandas as pd
import plotly.express as px
import sqlite3
import io
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
    <h1>&#127959; PMRO Enterprise SEINFRA v6.3</h1>
    <p>Gestao de Contratos · SINAPI/SICRO · Reajustes · Orcamentos</p>
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
    conn.commit()
    return conn

conn = init_db()

# ─────────────────────────────────────────
# SINAPI RO LOCAL
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
# SIDEBAR
# ─────────────────────────────────────────
st.sidebar.title("Menu Principal")
page = st.sidebar.radio("", [
    "Dashboard",
    "Contratos",
    "Reajustes",
    "SINAPI/SICRO",
    "Orcamento",
    "Relatorios"
])

if st.sidebar.button("Atualizar Dados BCB"):
    st.cache_data.clear()
    st.rerun()

# ─────────────────────────────────────────
# 1. DASHBOARD
# ─────────────────────────────────────────
if page == "Dashboard":
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
elif page == "Contratos":
    st.header("Gestao de Contratos")

    tab1, tab2 = st.tabs(["Novo Contrato", "Contratos Cadastrados"])

    with tab1:
        with st.form("form_contrato"):
            col1, col2 = st.columns(2)
            with col1:
                numero   = st.text_input("Numero do Contrato", placeholder="Ex: 001/2026")
                objeto   = st.text_area("Objeto", height=100)
                data_est = st.date_input("Data Orcamento Estimado", value=date.today())
                dt_base  = st.date_input("Data-Base Io", value=date(2025, 1, 1))
            with col2:
                ind_base  = st.number_input("Indice Base Io (SINAPI/SICRO)", value=100.0, format="%.4f")
                val_total = st.number_input("Valor Total Contratado R$", value=1000000.0, format="%.2f")
                val_rem   = st.number_input("Valor Remanescente R$", value=800000.0, format="%.2f")
                st.caption("Periodo minimo 1 ano para reajuste (Lei 14.133)")

            salvar = st.form_submit_button("Salvar Contrato")
            if salvar:
                if not numero or not objeto:
                    st.error("Preencha todos os campos obrigatorios!")
                else:
                    conn.execute(
                        "INSERT INTO contratos (numero, objeto, data_estimado, reajuste_base, dt_base, valor_total, valor_remanescente) VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (numero, objeto, str(data_est), ind_base, str(dt_base), val_total, val_rem)
                    )
                    conn.commit()
                    st.success("Contrato " + numero + " salvo!")
                    st.balloons()

    with tab2:
        df_c = pd.read_sql("SELECT * FROM contratos", conn)
        if df_c.empty:
            st.info("Nenhum contrato cadastrado.")
        else:
            st.dataframe(df_c, use_container_width=True)
            del_id = st.number_input("ID para excluir", min_value=0, step=1)
            if st.button("Excluir Contrato") and del_id > 0:
                conn.execute("DELETE FROM contratos WHERE id=?", (del_id,))
                conn.commit()
                st.success("Excluido!")
                st.rerun()

# ─────────────────────────────────────────
# 3. REAJUSTES
# ─────────────────────────────────────────
elif page == "Reajustes":
    st.header("Calculo de Reajustes - Lei 14.133")

    df_c = pd.read_sql("SELECT * FROM contratos", conn)
    if df_c.empty:
        st.warning("Cadastre contratos primeiro.")
    else:
        sel = st.selectbox(
            "Selecionar Contrato",
            df_c['id'],
            format_func=lambda x: df_c[df_c['id']==x]['numero'].values[0]
        )
        row = df_c[df_c['id']==sel].iloc[0]

        col1, col2, col3 = st.columns(3)
        col1.metric("Contrato", str(row['numero']))
        col1.metric("Indice Io", "{:.4f}".format(row['reajuste_base']))
        col2.metric("Data-Base", str(row['dt_base'])[:10])
        col2.metric("Valor Total", "R$ " + "{:,.2f}".format(row['valor_total']))

        hoje = date.today()
        try:
            dt_est = datetime.strptime(str(row['data_estimado'])[:10], "%Y-%m-%d").date()
            dias = (hoje - dt_est).days
            if dias < 365:
                col3.warning("Periodo minimo nao atingido! " + str(365 - dias) + " dias restantes.")
            else:
                col3.success("Elegivel para reajuste!")
        except:
            pass

        st.markdown("---")
        col1, col2 = st.columns(2)
        with col1:
            indice_tipo = st.selectbox("Indice de Reajuste", ["SINAPI-RO", "SICRO-DNIT", "INCC", "IPCA", "IGP-M"])
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

            linha_formula  = "R = ((Ii - Io) / Io) x V"
            linha_valores  = "R = ((" + "{:.4f}".format(Ii) + " - " + "{:.4f}".format(Io) + ") / " + "{:.4f}".format(Io) + ") x " + "{:,.2f}".format(V)
            linha_resultado = "R = R$ " + "{:,.2f}".format(R)

            st.code(linha_formula + "\n" + linha_valores + "\n" + linha_resultado, language="")

            col1, col2 = st.columns(2)
            col1.info("Indice utilizado: " + indice_tipo)
            col1.info("Data do calculo: " + hoje.strftime("%d/%m/%Y"))
            col2.success("Valor Remanescente V: R$ " + "{:,.2f}".format(V))
            col2.success("Reajuste Apurado R: R$ " + "{:,.2f}".format(R))

            novo_total = float(row['valor_total']) + R
            st.metric("Novo Valor Total do Contrato", "R$ " + "{:,.2f}".format(novo_total))

            if st.button("Salvar Reajuste"):
                conn.execute(
                    "UPDATE contratos SET indice_atual=?, reajuste_calculado=? WHERE id=?",
                    (Ii, R, sel)
                )
                conn.commit()
                st.success("Reajuste salvo!")

# ─────────────────────────────────────────
# 4. SINAPI / SICRO
# ─────────────────────────────────────────
elif page == "SINAPI/SICRO":
    st.header("Consulta SINAPI/SICRO - Rondonia")
    st.caption("Tabela local atualizada Mar/2026 | Integracao API em breve")

    df_sinapi = pd.DataFrame(SINAPI_INSUMOS)

    col1, col2, col3 = st.columns(3)
    busca   = col1.text_input("Buscar insumo")
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
    st.caption(str(len(df_f)) + " itens encontrados de " + str(len(df_sinapi)) + " no banco local")

# ─────────────────────────────────────────
# 5. ORCAMENTO
# ─────────────────────────────────────────
elif page == "Orcamento":
    st.header("Elaboracao de Orcamento - SINAPI RO")

    df_sinapi = pd.DataFrame(SINAPI_INSUMOS)

    col1, col2 = st.columns([3, 1])
    with col2:
        bdi      = st.number_input("BDI (%)", value=25.0)
        encargos = st.number_input("Encargos Sociais (%)", value=120.0)

    itens_orc = []
    with col1:
        st.subheader("Selecione itens e quantidades:")
        for _, r in df_sinapi.iterrows():
            c1, c2, c3 = st.columns([4, 1, 2])
            c1.write(r['codigo'] + " - " + r['nome'])
            qtd = c2.number_input(
                "qtd",
                min_value=0.0, value=0.0,
                key="qtd_" + r['codigo'],
                format="%.2f",
                label_visibility="collapsed"
            )
            c3.write("R$ " + "{:.2f}".format(r['preco']) + "/" + r['unidade'])
            if qtd > 0:
                item = dict(r)
                item['qtd']   = qtd
                item['total'] = r['preco'] * qtd
                itens_orc.append(item)

    if st.button("Calcular Orcamento") and itens_orc:
        df_orc   = pd.DataFrame(itens_orc)
        subtotal = df_orc['total'].sum()
        total_bdi = subtotal * (1 + bdi / 100)

        st.markdown("---")
        st.subheader("Orcamento Gerado")
        st.dataframe(df_orc[['codigo','nome','unidade','qtd','preco','total']], use_container_width=True)

        col1, col2, col3 = st.columns(3)
        col1.metric("Subtotal s/ BDI", "R$ " + "{:,.2f}".format(subtotal))
        col2.metric("BDI " + str(bdi) + "%", "R$ " + "{:,.2f}".format(subtotal * (bdi / 100)))
        col3.metric("TOTAL c/ BDI",    "R$ " + "{:,.2f}".format(total_bdi))

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_orc.to_excel(writer, sheet_name='Orcamento', index=False)
            pd.DataFrame({
                'Item':  ['Subtotal', 'BDI', 'TOTAL'],
                'Valor': [subtotal, subtotal * (bdi / 100), total_bdi]
            }).to_excel(writer, sheet_name='Resumo', index=False)

        st.download_button(
            "Baixar Excel",
            output.getvalue(),
            "orcamento_pmro_ro.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

# ─────────────────────────────────────────
# 6. RELATORIOS
# ─────────────────────────────────────────
elif page == "Relatorios":
    st.header("Relatorios e Exportacoes")

    df_c = pd.read_sql("SELECT * FROM contratos", conn)

    if df_c.empty:
        st.info("Nenhum contrato para exportar.")
    else:
        st.dataframe(df_c, use_container_width=True)

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_c.to_excel(writer, sheet_name='Contratos', index=False)
            pd.DataFrame({
                'Indicador': ['Total Contratos', 'Valor Carteira', 'Total Reajustes'],
                'Valor': [len(df_c), df_c['valor_total'].sum(), df_c['reajuste_calculado'].sum()]
            }).to_excel(writer, sheet_name='Resumo', index=False)

        st.download_button(
            "Exportar Excel Completo",
            output.getvalue(),
            "relatorio_pmro.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

# ─────────────────────────────────────────
# FOOTER
# ─────────────────────────────────────────
st.markdown("---")
st.caption("PMRO Enterprise SEINFRA v6.3 | Eng. Guilherme Ritter Baldin | Porto Velho/RO | " + str(date.today().year))
