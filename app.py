**Índice utilizado:** {indice_tipo}
**Data do cálculo:** {hoje.strftime("%d/%m/%Y")}
**Valor Remanescente (V):** R$ {V:,.2f}
**Reajuste Apurado (R):** R$ {R:,.2f}
**Novo Valor Total:** R$ {float(row['valor_total']) + R:,.2f}
            """)

            if st.button("💾 Salvar Reajuste"):
                conn.execute(
                    "UPDATE contratos SET indice_atual=?, reajuste_calculado=? WHERE id=?",
                    (Ii, R, sel))
                conn.commit()
                st.success("Reajuste salvo no contrato!")

# ─────────────────────────────────────────
# 4. SINAPI / SICRO
# ─────────────────────────────────────────
elif page == "🔍 SINAPI/SICRO":
    st.header("🔍 Consulta SINAPI/SICRO — Rondônia")
    st.caption("Tabela local atualizada Mar/2026 | Atualização via API em breve")

    df_sinapi = pd.DataFrame(SINAPI_INSUMOS)

    col1, col2, col3 = st.columns(3)
    busca   = col1.text_input("🔎 Buscar insumo")
    familia = col2.selectbox("Família", ["Todos"] + sorted(df_sinapi['familia'].unique()))
    tipo    = col3.selectbox("Tipo", ["Todos"] + sorted(df_sinapi['tipo'].unique()))

    df_filtrado = df_sinapi.copy()
    if busca:
        df_filtrado = df_filtrado[df_filtrado['nome'].str.contains(busca, case=False)]
    if familia != "Todos":
        df_filtrado = df_filtrado[df_filtrado['familia'] == familia]
    if tipo != "Todos":
        df_filtrado = df_filtrado[df_filtrado['tipo'] == tipo]

    st.dataframe(df_filtrado.style.format({'preco': 'R$ {:.2f}'}), use_container_width=True)
    st.caption(f"📦 {len(df_filtrado)} itens encontrados de {len(df_sinapi)} no banco local")

# ─────────────────────────────────────────
# 5. ORÇAMENTO
# ─────────────────────────────────────────
elif page == "➕ Orçamento":
    st.header("➕ Elaboração de Orçamento — SINAPI RO")

    df_sinapi = pd.DataFrame(SINAPI_INSUMOS)

    col1, col2 = st.columns([3, 1])
    with col2:
        bdi       = st.number_input("BDI (%)", value=25.0)
        encargos  = st.number_input("Encargos Sociais (%)", value=120.0)
        regime    = st.selectbox("Regime", ["NÃO DESONERADO", "DESONERADO"])

    with col1:
        st.subheader("Selecione os itens e quantidades:")
        itens_orc = []
        for _, row in df_sinapi.iterrows():
            c1, c2, c3 = st.columns([4, 1, 1])
            c1.write(f"**{row['codigo']}** — {row['nome']}")
            qtd = c2.number_input("Qtd", min_value=0.0, value=0.0,
                                  key=f"qtd_{row['codigo']}", format="%.2f", label_visibility="collapsed")
            c3.write(f"R$ {row['preco']:.2f}/{row['unidade']}")
            if qtd > 0:
                itens_orc.append({**row.to_dict(), 'qtd': qtd,
                                  'total': row['preco'] * qtd})

    if st.button("🧮 Gerar Orçamento") and itens_orc:
        df_orc  = pd.DataFrame(itens_orc)
        subtotal = df_orc['total'].sum()
        total_bdi = subtotal * (1 + bdi / 100)

        st.markdown("---")
        st.subheader("📊 Orçamento Gerado")
        st.dataframe(df_orc[['codigo','nome','unidade','qtd','preco','total']]
                     .style.format({'preco':'R$ {:.2f}','total':'R$ {:.2f}'}),
                     use_container_width=True)

        col1, col2, col3 = st.columns(3)
        col1.metric("Subtotal s/ BDI", f"R$ {subtotal:,.2f}")
        col2.metric(f"BDI {bdi}%",     f"R$ {subtotal*(bdi/100):,.2f}")
        col3.metric("TOTAL c/ BDI",    f"R$ {total_bdi:,.2f}")

        # Excel
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_orc.to_excel(writer, sheet_name='Orçamento', index=False)
            pd.DataFrame({
                'Item':  ['Subtotal', f'BDI {bdi}%', 'TOTAL'],
                'Valor': [subtotal, subtotal*(bdi/100), total_bdi]
            }).to_excel(writer, sheet_name='Resumo', index=False)
        st.download_button("📥 Baixar Excel",
                           output.getvalue(),
                           "orcamento_pmro_ro.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# ─────────────────────────────────────────
# 6. RELATÓRIOS
# ─────────────────────────────────────────
elif page == "📄 Relatórios":
    st.header("📄 Relatórios e Exportações")

    df_c = pd.read_sql("SELECT * FROM contratos", conn)

    if df_c.empty:
        st.info("Nenhum contrato cadastrado para exportar.")
    else:
        st.subheader("📋 Contratos Completos")
        st.dataframe(df_c, use_container_width=True)

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_c.to_excel(writer, sheet_name='Contratos', index=False)
            # Resumo financeiro
            pd.DataFrame({
                'Indicador': ['Total Contratos', 'Valor Carteira', 'Total Reajustes'],
                'Valor': [len(df_c),
                          df_c['valor_total'].sum(),
                          df_c['reajuste_calculado'].sum()]
            }).to_excel(writer, sheet_name='Resumo', index=False)

        st.download_button("📥 Exportar Excel Completo",
                           output.getvalue(),
                           "relatorio_pmro.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# ─────────────────────────────────────────
# FOOTER
# ─────────────────────────────────────────
st.markdown("---")
st.markdown(f"© {date.today().year} · Eng. Guilherme Ritter Baldin · PMRO Enterprise SEINFRA v6.3 | Porto Velho/RO")
