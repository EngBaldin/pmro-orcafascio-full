import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import sqlite3
import io
import re
import pdfplumber
from datetime import datetime, date
import json

st.set_page_config(
    layout="wide",
    page_icon="🏗️",
    page_title="PMRO Enterprise | SEINFRA",
    initial_sidebar_state="expanded"
)

# ═══════════════════════════════
# CSS ENTERPRISE PROFISSIONAL
# ═══════════════════════════════
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    .main { background-color: #f1f5f9; }
    .block-container { padding-top: 1rem; padding-bottom: 1rem; }

    .pmro-header {
        background: linear-gradient(135deg, #0f172a 0%, #1e3a8a 50%, #3b82f6 100%);
        padding: 2rem 3rem;
        border-radius: 16px;
        color: white;
        margin-bottom: 1.5rem;
        box-shadow: 0 10px 40px rgba(30,58,138,0.3);
    }
    .pmro-header h1 { font-size: 2rem; font-weight: 700; margin: 0; letter-spacing: -0.5px; }
    .pmro-header p { font-size: 0.95rem; margin: 0.3rem 0 0 0; opacity: 0.8; }

    .kpi-card {
        background: white;
        border-radius: 12px;
        padding: 1.2rem 1.5rem;
        border-left: 4px solid #3b82f6;
        box-shadow: 0 2px 12px rgba(0,0,0,0.07);
        margin-bottom: 1rem;
    }
    .kpi-label { font-size: 0.78rem; color: #64748b; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; }
    .kpi-value { font-size: 1.8rem; font-weight: 700; color: #0f172a; margin-top: 0.2rem; }
    .kpi-sub { font-size: 0.78rem; color: #94a3b8; }

    .section-card {
        background: white;
        border-radius: 12px;
        padding: 1.5rem;
        box-shadow: 0 2px 12px rgba(0,0,0,0.06);
        margin-bottom: 1rem;
    }
    .section-title {
        font-size: 1.1rem;
        font-weight: 700;
        color: #1e3a8a;
        margin-bottom: 1rem;
        padding-bottom: 0.5rem;
        border-bottom: 2px solid #eff6ff;
    }
    div[data-testid="stTabs"] button {
        font-weight: 600;
        font-size: 0.9rem;
    }
</style>
""", unsafe_allow_html=True)

# ═══════════════════════════════
# BANCO DE DADOS
# ═══════════════════════════════
@st.cache_resource
def get_db():
    conn = sqlite3.connect("pmro_enterprise.db", check_same_thread=False)
    c = conn.cursor()
    c.executescript("""
        CREATE TABLE IF NOT EXISTS insumos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo TEXT, descricao TEXT, unidade TEXT,
            preco REAL, tabela TEXT, mes_ano TEXT, estado TEXT
        );
        CREATE TABLE IF NOT EXISTS composicoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo_comp TEXT, descricao_comp TEXT, unidade TEXT,
            codigo_insumo TEXT, descricao_insumo TEXT,
            coeficiente REAL, tipo TEXT
        );
        CREATE TABLE IF NOT EXISTS orcamentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            numero TEXT UNIQUE, obra TEXT, local TEXT,
            responsavel TEXT, data_orcamento DATE,
            bdi REAL DEFAULT 35.0, subtotal REAL, total_bdi REAL,
            status TEXT DEFAULT 'Rascunho', criado_em DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS orcamento_itens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            orcamento_id INTEGER, codigo TEXT, descricao TEXT,
            unidade TEXT, quantidade REAL, preco_unit REAL,
            subtotal REAL, tabela TEXT,
            FOREIGN KEY(orcamento_id) REFERENCES orcamentos(id)
        );
        CREATE TABLE IF NOT EXISTS contratos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            numero TEXT UNIQUE, objeto TEXT, empresa TEXT,
            valor REAL, reajuste_indice TEXT, reajuste_base REAL,
            data_assinatura DATE, data_vencimento DATE,
            status TEXT DEFAULT 'Ativo', pdf_nome TEXT,
            criado_em DATETIME DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.commit()
    return conn

conn = get_db()

# ═══════════════════════════════
# FUNÇÕES UTILITÁRIAS
# ═══════════════════════════════
def carregar_insumos():
    return pd.read_sql("SELECT * FROM insumos ORDER BY tabela, codigo", conn)

def carregar_composicoes():
    return pd.read_sql("SELECT * FROM composicoes", conn)

def carregar_orcamentos():
    return pd.read_sql("SELECT * FROM orcamentos ORDER BY criado_em DESC", conn)

def carregar_contratos():
    return pd.read_sql("SELECT * FROM contratos ORDER BY criado_em DESC", conn)

def importar_excel(file):
    try:
        df_ins = pd.read_excel(file, sheet_name="INSUMOS")
        df_ins.columns = [c.lower() for c in df_ins.columns]
        for _, r in df_ins.iterrows():
            conn.execute("""
                INSERT OR IGNORE INTO insumos (codigo, descricao, unidade, preco, tabela, mes_ano, estado)
                VALUES (?,?,?,?,?,?,?)
            """, (str(r.get("código","")).strip(), str(r.get("descrição","")).strip(),
                  str(r.get("unidade","")).strip(), float(r.get("preço_unitario",0)),
                  str(r.get("tabela_referencia","")).strip(), str(r.get("mês_ano","")).strip(),
                  str(r.get("estado","RO")).strip()))

        df_comp = pd.read_excel(file, sheet_name="COMPOSIÇÕES")
        df_comp.columns = [c.lower() for c in df_comp.columns]
        for _, r in df_comp.iterrows():
            conn.execute("""
                INSERT INTO composicoes (codigo_comp, descricao_comp, unidade, codigo_insumo, descricao_insumo, coeficiente, tipo)
                VALUES (?,?,?,?,?,?,?)
            """, (str(r.get("código_comp","")).strip(), str(r.get("descrição_composição","")).strip(),
                  str(r.get("unidade","")).strip(), str(r.get("código_insumo","")).strip(),
                  str(r.get("descrição_insumo","")).strip(), float(r.get("coef",0)),
                  str(r.get("tipo","")).strip()))
        conn.commit()
        return True, "✅ Importação realizada com sucesso!"
    except Exception as e:
        return False, f"❌ Erro na importação: {e}"

def calcular_reajuste(valor_inicial, indice_base, indice_atual):
    if indice_base and indice_base > 0:
        return valor_inicial * (indice_atual / indice_base)
    return valor_inicial

def extrair_pdf_contrato(pdf_file):
    texto = ""
    with pdfplumber.open(pdf_file) as pdf:
        for p in pdf.pages:
            texto += p.extract_text() or ""

    numero = re.search(r'(\d{3}/PGM/\d{4}|CONTRATO.*?N[°º].*?(\d+[/\-]\w+[/\-]\d+))', texto, re.I)
    valor = re.search(r'valor.*?R\$\s*([\d.,]+)', texto, re.I)
    empresa = re.search(r'CONTRATAD[AO].*?[:–-]\s*([A-ZÁÉÍÓÚÂÊÎÔÛÃÕ][\w\s,\.]+(?:LTDA|S\.A\.|ME|EPP))', texto, re.I)
    objeto = re.search(r'OBJETO[:–-]\s*(.{30,200}?)(?:\.|\n)', texto, re.I)

    numero_val = numero.group(1) if numero else ""
    valor_val = float(valor.group(1).replace('.','').replace(',','.')) if valor else 0.0
    empresa_val = empresa.group(1).strip() if empresa else ""
    objeto_val = objeto.group(1).strip() if objeto else ""

    return numero_val, valor_val, empresa_val, objeto_val, texto[:3000]

def gerar_excel_orcamento(orcamento_id, itens_df, bdi, total_bdi):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        wb = writer.book

        # Planilha principal
        resumo = pd.DataFrame({
            "CÓDIGO": itens_df["codigo"],
            "DESCRIÇÃO DO SERVIÇO": itens_df["descricao"],
            "UNID": itens_df["unidade"],
            "QTDE": itens_df["quantidade"],
            "PREÇO UNIT. (R$)": itens_df["preco_unit"],
            "SUBTOTAL (R$)": itens_df["subtotal"],
            "TABELA REF.": itens_df.get("tabela","")
        })
        resumo.to_excel(writer, sheet_name="Planilha Orçamentária", index=False)

        # Resumo executivo
        subtotal = itens_df["subtotal"].sum()
        encargos = subtotal * (bdi/100)
        res = pd.DataFrame({
            "RESUMO EXECUTIVO": ["SUBTOTAL SERVIÇOS", f"BDI {bdi}%", "TOTAL GERAL DA OBRA"],
            "VALOR (R$)": [subtotal, encargos, total_bdi]
        })
        res.to_excel(writer, sheet_name="Resumo Executivo", index=False)
    return output.getvalue()


# ═══════════════════════════════
# HEADER
# ═══════════════════════════════
st.markdown("""
<div class="pmro-header">
    <h1>🏗️ PMRO Enterprise</h1>
    <p>Sistema de Gestão de Obras Públicas · SEINFRA · Prefeitura Municipal de Porto Velho</p>
</div>
""", unsafe_allow_html=True)

# ═══════════════════════════════
# SIDEBAR
# ═══════════════════════════════
with st.sidebar:
    st.markdown("### 📂 Navegação")
    pagina = st.radio("", [
        "📊 Dashboard",
        "💰 Orçamento de Obras",
        "📋 Gestão de Contratos",
        "📅 Planejamento Gantt",
        "📱 Diário de Obras",
        "⚙️ Bases de Dados"
    ], label_visibility="collapsed")

    st.markdown("---")
    st.markdown(f"""
    <div style='text-align:center; color:#64748b; font-size:0.75rem;'>
        <strong>PMRO Enterprise v6.0</strong><br>
        Eng. Guilherme Ritter Baldin<br>
        SEINFRA · Porto Velho · RO<br>
        {datetime.now().strftime("%d/%m/%Y %H:%M")}
    </div>
    """, unsafe_allow_html=True)


# ═══════════════════════════════════════════
# PÁGINA 1: DASHBOARD
# ═══════════════════════════════════════════
if pagina == "📊 Dashboard":
    df_orc = carregar_orcamentos()
    df_cont = carregar_contratos()
    df_ins = carregar_insumos()

    col1, col2, col3, col4 = st.columns(4)
    total_orc = df_orc["total_bdi"].sum() if not df_orc.empty else 0
    total_cont = df_cont["valor"].sum() if not df_cont.empty else 0
    n_insumos = len(df_ins)

    col1.markdown(f"""<div class="kpi-card">
        <div class="kpi-label">📋 Orçamentos</div>
        <div class="kpi-value">{len(df_orc)}</div>
        <div class="kpi-sub">Elaborados no sistema</div></div>""", unsafe_allow_html=True)
    col2.markdown(f"""<div class="kpi-card">
        <div class="kpi-label">💰 Valor Orçado Total</div>
        <div class="kpi-value">R$ {total_orc:,.0f}</div>
        <div class="kpi-sub">Com BDI incluso</div></div>""", unsafe_allow_html=True)
    col3.markdown(f"""<div class="kpi-card">
        <div class="kpi-label">📄 Contratos Ativos</div>
        <div class="kpi-value">{len(df_cont)}</div>
        <div class="kpi-sub">Valor: R$ {total_cont:,.0f}</div></div>""", unsafe_allow_html=True)
    col4.markdown(f"""<div class="kpi-card">
        <div class="kpi-label">🗂️ Insumos na Base</div>
        <div class="kpi-value">{n_insumos}</div>
        <div class="kpi-sub">SINAPI + SICRO + PMRO</div></div>""", unsafe_allow_html=True)

    if not df_orc.empty:
        col1g, col2g = st.columns(2)
        with col1g:
            fig = px.bar(df_orc.head(8), x="numero", y="total_bdi",
                        title="Orçamentos por Valor (R$)", color="status",
                        color_discrete_map={"Rascunho":"#94a3b8","Aprovado":"#22c55e","Enviado":"#3b82f6"},
                        labels={"total_bdi":"Valor R$","numero":"Orçamento"})
            fig.update_layout(height=350, plot_bgcolor="white", paper_bgcolor="white")
            st.plotly_chart(fig, use_container_width=True)
        with col2g:
            if not df_cont.empty:
                fig2 = px.pie(df_cont, values="valor", names="status",
                             title="Contratos por Status", hole=0.4,
                             color_discrete_sequence=["#3b82f6","#22c55e","#f59e0b","#ef4444"])
                fig2.update_layout(height=350)
                st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("💡 Comece cadastrando insumos na aba **⚙️ Bases de Dados**, depois crie seu primeiro orçamento.")

# ═══════════════════════════════════════════
# PÁGINA 2: ORÇAMENTO
# ═══════════════════════════════════════════
elif pagina == "💰 Orçamento de Obras":
    tabs = st.tabs(["➕ Novo Orçamento", "📋 Gerenciar Orçamentos"])

    with tabs[0]:
        st.markdown('<div class="section-title">Novo Orçamento PMRO</div>', unsafe_allow_html=True)

        col1, col2, col3 = st.columns(3)
        num_orc = col1.text_input("Nº Orçamento*", placeholder="ORC-2026-001")
        nome_obra = col2.text_input("Nome da Obra*", placeholder="Pavimentação Av. Guaporé")
        local_obra = col3.text_input("Localização", placeholder="Bairro 3 Marias")
        resp = col1.text_input("Responsável Técnico", value="Eng. Guilherme Ritter Baldin")
        bdi = col2.number_input("BDI (%)", value=35.0, min_value=0.0, max_value=100.0)
        data_orc = col3.date_input("Data", value=date.today())

        st.markdown("---")
        st.markdown("#### 🔍 Buscar Insumo/Serviço na Base")

        df_ins = carregar_insumos()
        if df_ins.empty:
            st.warning("⚠️ Base de insumos vazia. Importe sua planilha em **⚙️ Bases de Dados** primeiro.")
        else:
            col_f1, col_f2 = st.columns([2,1])
            busca = col_f1.text_input("🔎 Pesquisar (nome, código ou tabela):", placeholder="ex: asfalto, PEAD, MOB-001")
            tabela_f = col_f2.selectbox("Filtrar tabela:", ["TODAS"] + sorted(df_ins["tabela"].unique().tolist()))

            df_filtrado = df_ins.copy()
            if busca:
                df_filtrado = df_filtrado[
                    df_filtrado["descricao"].str.contains(busca, case=False, na=False) |
                    df_filtrado["codigo"].str.contains(busca, case=False, na=False)
                ]
            if tabela_f != "TODAS":
                df_filtrado = df_filtrado[df_filtrado["tabela"] == tabela_f]

            if not df_filtrado.empty:
                st.dataframe(df_filtrado[["codigo","descricao","unidade","preco","tabela"]].head(15),
                           use_container_width=True, hide_index=True,
                           column_config={
                               "preco": st.column_config.NumberColumn("Preço Unit.", format="R$ %.2f"),
                               "codigo": "Código", "descricao": "Descrição",
                               "unidade": "Und", "tabela": "Ref."
                           })

        st.markdown("#### ➕ Adicionar Item ao Orçamento")
        if "itens_orcamento" not in st.session_state:
            st.session_state.itens_orcamento = []

        col1i, col2i, col3i, col4i, col5i = st.columns([2,4,1,2,2])
        cod_item = col1i.text_input("Código", key="cod_i")
        desc_item = col2i.text_input("Descrição", key="desc_i")
        und_item = col3i.text_input("Und", key="und_i")
        qtd_item = col4i.number_input("Qtde", min_value=0.0, step=1.0, key="qtd_i")
        preco_item = col5i.number_input("Preço Unit.", min_value=0.0, step=0.01, key="preco_i")

        col_auto, col_add = st.columns([3,1])
        # Auto-preencher pelo código
        if cod_item and not df_ins.empty:
            match = df_ins[df_ins["codigo"].str.strip() == cod_item.strip()]
            if not match.empty:
                col_auto.success(f"✅ Encontrado: {match.iloc[0]['descricao']} | {match.iloc[0]['unidade']} | R$ {match.iloc[0]['preco']:.2f}")

        if col_add.button("➕ Adicionar Item", type="primary"):
            if cod_item and desc_item and qtd_item > 0 and preco_item > 0:
                st.session_state.itens_orcamento.append({
                    "codigo": cod_item, "descricao": desc_item,
                    "unidade": und_item, "quantidade": qtd_item,
                    "preco_unit": preco_item, "subtotal": qtd_item * preco_item,
                    "tabela": ""
                })
                st.success(f"✅ {desc_item} adicionado!")
                st.rerun()

        if st.session_state.itens_orcamento:
            df_itens = pd.DataFrame(st.session_state.itens_orcamento)
            subtotal = df_itens["subtotal"].sum()
            total_final = subtotal * (1 + bdi/100)

            st.markdown("#### 📊 Planilha Orçamentária")
            st.dataframe(df_itens, use_container_width=True, hide_index=True,
                        column_config={
                            "subtotal": st.column_config.NumberColumn("Subtotal R$", format="R$ %.2f"),
                            "preco_unit": st.column_config.NumberColumn("Unit. R$", format="R$ %.2f"),
                            "quantidade": st.column_config.NumberColumn("Qtde", format="%.2f")
                        })

            col_s, col_b, col_t = st.columns(3)
            col_s.metric("📊 Subtotal", f"R$ {subtotal:,.2f}")
            col_b.metric(f"📈 Encargos BDI ({bdi}%)", f"R$ {subtotal*(bdi/100):,.2f}")
            col_t.metric("🏆 TOTAL GERAL", f"R$ {total_final:,.2f}")

            col_save, col_excel, col_clear = st.columns(3)

            if col_save.button("💾 Salvar Orçamento", type="primary"):
                try:
                    conn.execute("""
                        INSERT INTO orcamentos (numero, obra, local, responsavel, data_orcamento, bdi, subtotal, total_bdi)
                        VALUES (?,?,?,?,?,?,?,?)
                    """, (num_orc, nome_obra, local_obra, resp, data_orc, bdi, subtotal, total_final))
                    orc_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
                    for item in st.session_state.itens_orcamento:
                        conn.execute("""
                            INSERT INTO orcamento_itens (orcamento_id,codigo,descricao,unidade,quantidade,preco_unit,subtotal)
                            VALUES (?,?,?,?,?,?,?)
                        """, (orc_id, item["codigo"], item["descricao"], item["unidade"],
                              item["quantidade"], item["preco_unit"], item["subtotal"]))
                    conn.commit()
                    st.balloons()
                    st.success(f"✅ Orçamento {num_orc} salvo! Total: R$ {total_final:,.2f}")
                    st.session_state.itens_orcamento = []
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Erro: {e}")

            if col_excel.button("📥 Exportar Excel TCU"):
                excel_data = gerar_excel_orcamento(0, df_itens, bdi, total_final)
                st.download_button("⬇️ Baixar Planilha Oficial",
                    excel_data, f"PMRO_{num_orc}_{datetime.now().strftime('%Y%m%d')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

            if col_clear.button("🗑️ Limpar Itens"):
                st.session_state.itens_orcamento = []
                st.rerun()

    with tabs[1]:
        df_orc = carregar_orcamentos()
        if not df_orc.empty:
            st.dataframe(df_orc, use_container_width=True, hide_index=True,
                        column_config={
                            "total_bdi": st.column_config.NumberColumn("Total R$", format="R$ %.2f"),
                            "subtotal": st.column_config.NumberColumn("Subtotal R$", format="R$ %.2f"),
                            "bdi": st.column_config.NumberColumn("BDI %", format="%.1f%%")
                        })
            csv = df_orc.to_csv(index=False).encode()
            st.download_button("📥 Exportar CSV", csv, "PMRO_Orcamentos.csv")
        else:
            st.info("Nenhum orçamento salvo ainda.")

# ═══════════════════════════════════════════
# PÁGINA 3: CONTRATOS
# ═══════════════════════════════════════════
elif pagina == "📋 Gestão de Contratos":
    tabs = st.tabs(["➕ Novo Contrato", "🔄 Reajuste", "📋 Todos Contratos"])

    with tabs[0]:
        st.markdown('<div class="section-title">Cadastro de Contrato</div>', unsafe_allow_html=True)

        uploaded = st.file_uploader("📄 Upload PDF do Contrato (IA extrai dados)", type="pdf")

        numero_cont, valor_cont, empresa_cont, objeto_cont = "", 0.0, "", ""
        texto_pdf = ""

        if uploaded:
            with st.spinner("🤖 Analisando contrato..."):
                try:
                    numero_cont, valor_cont, empresa_cont, objeto_cont, texto_pdf = extrair_pdf_contrato(uploaded)
                    st.success("✅ IA extraiu dados do contrato!")
                    if texto_pdf:
                        with st.expander("🔍 Texto extraído do PDF"):
                            st.text_area("", texto_pdf, height=200)
                except Exception as e:
                    st.warning(f"PDF lido mas extração parcial: {e}")

        col1, col2 = st.columns(2)
        numero = col1.text_input("Nº Contrato*", value=numero_cont, placeholder="010/PGM/2026")
        empresa = col2.text_input("Empresa*", value=empresa_cont)
        objeto = st.text_area("Objeto do Contrato", value=objeto_cont, height=80)

        col1, col2, col3 = st.columns(3)
        valor = col1.number_input("Valor R$*", value=float(valor_cont), min_value=0.0, step=1000.0)
        dt_ass = col2.date_input("Data Assinatura", value=date.today())
        dt_venc = col3.date_input("Data Vencimento")

        col1, col2 = st.columns(2)
        indice = col1.selectbox("Índice Reajuste", ["INCC-DI","IPCA","IGP-M","INPC","Sem reajuste"])
        indice_base = col2.number_input("Índice Base (na assinatura)", value=100.0, step=0.01)

        if st.button("💾 Salvar Contrato", type="primary"):
            try:
                conn.execute("""
                    INSERT INTO contratos (numero,objeto,empresa,valor,reajuste_indice,reajuste_base,data_assinatura,data_vencimento,pdf_nome)
                    VALUES (?,?,?,?,?,?,?,?,?)
                """, (numero, objeto, empresa, valor, indice, indice_base, dt_ass, dt_venc, uploaded.name if uploaded else ""))
                conn.commit()
                st.balloons()
                st.success(f"✅ Contrato {numero} salvo! Valor: R$ {valor:,.2f}")
            except Exception as e:
                st.error(f"❌ Erro: {e}")

    with tabs[1]:
        st.markdown('<div class="section-title">Calculadora de Reajuste Contratual</div>', unsafe_allow_html=True)
        st.info("📐 Fórmula: R = V × (Ia / Ib) | Onde R = Valor Reajustado, V = Valor Original, Ia = Índice Atual, Ib = Índice Base")

        df_cont = carregar_contratos()
        if not df_cont.empty:
            sel = st.selectbox("Selecione o Contrato:", df_cont["numero"].tolist())
            cont_sel = df_cont[df_cont["numero"] == sel].iloc[0]

            col1, col2, col3 = st.columns(3)
            col1.metric("Valor Original", f"R$ {cont_sel['valor']:,.2f}")
            col2.metric("Índice Base", f"{cont_sel['reajuste_base']:.4f}")
            col3.metric("Índice (Referência)", cont_sel["reajuste_indice"])

            indice_atual = st.number_input("📈 Índice Atual (consulte IBGE/FGV):", value=float(cont_sel["reajuste_base"]), step=0.01)

            if indice_atual > 0 and cont_sel["reajuste_base"] > 0:
                valor_reaj = calcular_reajuste(cont_sel["valor"], cont_sel["reajuste_base"], indice_atual)
                variacao = ((indice_atual / cont_sel["reajuste_base"]) - 1) * 100
                acrescimo = valor_reaj - cont_sel["valor"]

                col1, col2, col3 = st.columns(3)
                col1.metric("💰 Valor Reajustado", f"R$ {valor_reaj:,.2f}", f"+R$ {acrescimo:,.2f}")
                col2.metric("📊 Variação Índice", f"{variacao:.2f}%")
                col3.metric("➕ Acréscimo", f"R$ {acrescimo:,.2f}")
        else:
            st.info("Cadastre contratos na aba anterior.")

    with tabs[2]:
        df_cont = carregar_contratos()
        if not df_cont.empty:
            st.dataframe(df_cont, use_container_width=True, hide_index=True,
                        column_config={
                            "valor": st.column_config.NumberColumn("Valor R$", format="R$ %.2f")
                        })
            csv = df_cont.to_csv(index=False).encode()
            st.download_button("📥 Exportar CSV", csv, "PMRO_Contratos.csv")
        else:
            st.info("Nenhum contrato cadastrado.")

# ═══════════════════════════════════════════
# PÁGINA 4: GANTT
# ═══════════════════════════════════════════
elif pagina == "📅 Planejamento Gantt":
    st.markdown('<div class="section-title">Cronograma Físico-Financeiro</div>', unsafe_allow_html=True)
    st.info("🚧 Módulo em desenvolvimento - disponível na próxima versão")
    st.markdown("**Em breve:** Gantt interativo com % execução, curva ABC 112/2009 e alertas de atraso.")

# ═══════════════════════════════════════════
# PÁGINA 5: DIÁRIO
# ═══════════════════════════════════════════
elif pagina == "📱 Diário de Obras":
    st.markdown('<div class="section-title">Diário de Obras</div>', unsafe_allow_html=True)
    st.info("🚧 Módulo em desenvolvimento - disponível na próxima versão")
    st.markdown("**Em breve:** Registro diário, controle de equipe, chuvas, relatório mensal automático.")

# ═══════════════════════════════════════════
# PÁGINA 6: BASES DE DADOS
# ═══════════════════════════════════════════
elif pagina == "⚙️ Bases de Dados":
    tabs = st.tabs(["📥 Importar Tabelas", "🔍 Visualizar Base", "➕ Insumo Manual"])

    with tabs[0]:
        st.markdown('<div class="section-title">Importar Tabela de Referência</div>', unsafe_allow_html=True)
        st.info("📌 Use o template Excel disponível abaixo. Funciona com SINAPI, SICRO, ORSE e base própria PMRO.")

        # Download template
        import io
from openpyxl import Workbook
tmpl = Workbook()
ws = tmpl.active
ws.title = "INSUMOS"
ws.append(["CÓDIGO","DESCRIÇÃO","UNIDADE","PREÇO_UNITARIO","TABELA_REFERENCIA","MÊS_ANO","ESTADO"])
ws.append(["SINAPI-001","Cimento Portland CP-II","kg",0.85,"SINAPI","03/2026","RO"])
ws.append(["SINAPI-002","Areia média lavada","m³",120.00,"SINAPI","03/2026","RO"])
ws.append(["SINAPI-003","Tubo PEAD DN200mm","m",156.20,"SINAPI","03/2026","RO"])
ws.append(["MOB-001","Pedreiro","h",25.80,"SINAPI","03/2026","RO"])
ws.append(["EQP-001","Retroescavadeira","h",185.00,"SINAPI","03/2026","RO"])
ws2 = tmpl.create_sheet("COMPOSIÇÕES")
ws2.append(["CÓDIGO_COMP","DESCRIÇÃO_COMPOSIÇÃO","UNIDADE","CÓDIGO_INSUMO","DESCRIÇÃO_INSUMO","COEF","TIPO"])
ws2.append(["COMP-001","Pavimentação CBUQ 4cm","m²","SINAPI-003","Tubo PEAD",1.0,"MATERIAL"])
buf = io.BytesIO()
tmpl.save(buf)
st.download_button(
    "⬇️ Baixar Template Excel PMRO",
    buf.getvalue(),
    "TEMPLATE_PMRO.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    type="primary"
)


st.markdown("---")
        upload_excel = st.file_uploader("📊 Upload Tabela Preenchida (.xlsx)", type=["xlsx"])
        if upload_excel:
            ok, msg = importar_excel(upload_excel)
            if ok:
                st.success(msg)
                st.rerun()
            else:
                st.error(msg)

    with tabs[1]:
        df_ins = carregar_insumos()
        if not df_ins.empty:
            col1, col2 = st.columns(2)
            busca = col1.text_input("🔍 Buscar:")
            tabela_f = col2.selectbox("Tabela:", ["TODAS"] + sorted(df_ins["tabela"].unique().tolist()))

            df_show = df_ins.copy()
            if busca:
                df_show = df_show[df_show["descricao"].str.contains(busca, case=False, na=False)]
            if tabela_f != "TODAS":
                df_show = df_show[df_show["tabela"] == tabela_f]

            st.metric("Insumos encontrados", len(df_show))
            st.dataframe(df_show, use_container_width=True, hide_index=True,
                        column_config={"preco": st.column_config.NumberColumn("Preço R$", format="R$ %.2f")})
        else:
            st.info("Base vazia. Importe a planilha na aba anterior.")

    with tabs[2]:
        st.markdown('<div class="section-title">Adicionar Insumo Manual</div>', unsafe_allow_html=True)
        col1, col2, col3 = st.columns(3)
        m_cod = col1.text_input("Código")
        m_desc = col2.text_input("Descrição")
        m_und = col3.text_input("Unidade")
        col1, col2, col3 = st.columns(3)
        m_preco = col1.number_input("Preço R$", min_value=0.0, step=0.01)
        m_tab = col2.selectbox("Tabela Referência", ["SINAPI","SICRO","ORSE","SEINFRA","BASE_PMRO"])
        m_mes = col3.text_input("Mês/Ano", value=datetime.now().strftime("%m/%Y"))

        if st.button("➕ Adicionar Insumo", type="primary"):
            if m_cod and m_desc and m_preco > 0:
                conn.execute("INSERT INTO insumos (codigo,descricao,unidade,preco,tabela,mes_ano,estado) VALUES (?,?,?,?,?,?,?)",
                           (m_cod, m_desc, m_und, m_preco, m_tab, m_mes, "RO"))
                conn.commit()
                st.success(f"✅ Insumo {m_cod} adicionado!")
                st.rerun()

# Footer
st.markdown("---")
st.markdown(f"""
<div style='text-align:center; color:#94a3b8; font-size:0.8rem; padding:1rem;'>
    🏛️ <strong>PMRO Enterprise v6.0</strong> · Sistema de Gestão de Obras Públicas · SEINFRA Porto Velho<br>
    © {datetime.now().year} Eng. Guilherme Ritter Baldin · Todos os direitos reservados
</div>
""", unsafe_allow_html=True)
