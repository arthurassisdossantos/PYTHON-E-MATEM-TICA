import streamlit as st
import pandas as pd
import plotly.express as px
import os

# ==============================================================================
# 1. CONFIGURAÇÃO DA PÁGINA STREAMLIT
# ==============================================================================
st.set_page_config(
    page_title="Dashboard IBGE - Crescimento Demográfico",
    page_icon="🌍",
    layout="wide",
    initial_sidebar_state="expanded"
)

CAMINHO_PADRAO = "CD2022_Populacao_2010_Compatibilizada_20231222.xlsx"

# ==============================================================================
# 2. FUNÇÃO DE LEITURA BASEADA NA ESTRUTURA EXATA DO ARQUIVO
# ==============================================================================
@st.cache_data
def carregar_dados_populacao(caminho_ou_arquivo):
    try:
        # 1. Lê a planilha bruta sem cabeçalho
        df_raw = pd.read_excel(caminho_ou_arquivo, engine='openpyxl', header=None)
        
        # 2. Com base na imagem, os dados começam na linha 4 (índice 3)
        # E as colunas corretas são: 1(UF), 2(COD_UF), 3(COD_MUN), 4(NOME), 6(POP_2010), 7(POP_2022)
        df = df_raw.iloc[3:, [1, 2, 3, 4, 6, 7]].copy()
        
        # 3. Renomeia as colunas para o padrão do nosso sistema
        df.columns = ["UF", "COD_UF", "COD_MUN", "MUNICÍPIO", "POP_2010", "POP_2022"]
        
        # 4. Remove linhas de rodapé ou cabeçalhos extras (onde COD_UF não é número)
        df = df[pd.to_numeric(df['COD_UF'], errors='coerce').notnull()].copy()
        df = df.dropna(subset=['UF', 'MUNICÍPIO'])
        
        # 5. Converte as colunas de população para número matemático
        df['POP_2010'] = pd.to_numeric(df['POP_2010'], errors='coerce').fillna(0)
        df['POP_2022'] = pd.to_numeric(df['POP_2022'], errors='coerce').fillna(0)
        
        # 6. Calcula os indicadores (Crescimento e Porcentagem)
        df['CRESCIMENTO_ABS'] = df['POP_2022'] - df['POP_2010']
        df['CRESCIMENTO_PCT'] = ((df['POP_2022'] - df['POP_2010']) / df['POP_2010'] * 100).round(2)
        df.loc[df['POP_2010'] == 0, 'CRESCIMENTO_PCT'] = 0 
        
        return df
    except Exception as e:
        st.error(f"🚨 Erro técnico ao processar: {e}")
        return pd.DataFrame()

# ==============================================================================
# 3. BARRA LATERAL (SIDEBAR) E VALIDAÇÃO DE ARQUIVO
# ==============================================================================
st.sidebar.title("📌 Menu & Filtros")
st.sidebar.subheader("📂 Base de Dados")

file_populacao = st.sidebar.file_uploader(
    "Upload Arquivo IBGE (CD2022_Populacao...):", 
    type=["xls", "xlsx", "csv"]
)

df_pop = None

if file_populacao is not None:
    df_pop = carregar_dados_populacao(file_populacao)
elif os.path.exists(CAMINHO_PADRAO):
    df_pop = carregar_dados_populacao(CAMINHO_PADRAO)
else:
    st.warning("⚠️ **Aguardando base de dados.**")
    st.info(f"Faça o upload do arquivo `{CAMINHO_PADRAO}` para iniciar.")
    st.stop()

if df_pop is None or df_pop.empty:
    st.error("❌ Os dados da planilha não puderam ser extraídos corretamente. Veja o formato bruto abaixo:")
    try:
        arquivo_leitura = file_populacao if file_populacao else CAMINHO_PADRAO
        raw_df = pd.read_excel(arquivo_leitura, engine='openpyxl', header=None)
        st.dataframe(raw_df.head(20), use_container_width=True)
    except:
        pass
    st.stop()

st.sidebar.markdown("---")
ufs_disponiveis = sorted(df_pop['UF'].unique())
ufs_selecionadas = st.sidebar.multiselect(
    "Filtre por Estado (UF):", 
    ufs_disponiveis, 
    default=ufs_disponiveis[:5] if len(ufs_disponiveis) > 5 else ufs_disponiveis
)

df_filtrado = df_pop[df_pop['UF'].isin(ufs_selecionadas)].copy() if ufs_selecionadas else df_pop.copy()

# ==============================================================================
# 4. PÁGINA PRINCIPAL - KPIS E VISUALIZAÇÕES
# ==============================================================================
st.title("📊 Painel de Crescimento Demográfico (2010 - 2022)")
st.markdown("Análise baseada nos dados do Censo IBGE para identificação de padrões de crescimento populacional municipal.")

st.subheader("📌 Indicadores Gerais (UFs Selecionadas)")
col1, col2, col3, col4 = st.columns(4)

total_2010 = df_filtrado['POP_2010'].sum()
total_2022 = df_filtrado['POP_2022'].sum()
crescimento_total_pct = ((total_2022 - total_2010) / total_2010 * 100) if total_2010 > 0 else 0

municipio_maior_crescimento = df_filtrado.loc[df_filtrado['CRESCIMENTO_PCT'].idxmax()]
municipio_menor_crescimento = df_filtrado.loc[df_filtrado['CRESCIMENTO_PCT'].idxmin()]

col1.metric("População Total (2022)", f"{total_2022:,.0f}".replace(",", "."))
col2.metric("Crescimento vs 2010", f"{crescimento_total_pct:.2f}%", f"{total_2022 - total_2010:,.0f} hab")
col3.metric("Maior Crescimento %", f"{municipio_maior_crescimento['MUNICÍPIO']}-{municipio_maior_crescimento['UF']}", f"{municipio_maior_crescimento['CRESCIMENTO_PCT']:.1f}%")
col4.metric("Maior Retração %", f"{municipio_menor_crescimento['MUNICÍPIO']}-{municipio_menor_crescimento['UF']}", f"{municipio_menor_crescimento['CRESCIMENTO_PCT']:.1f}%")

st.markdown("---")

col_graf1, col_graf2 = st.columns(2)

with col_graf1:
    st.subheader("Top 10 Municípios (Crescimento Absoluto)")
    top10_abs = df_filtrado.nlargest(10, 'CRESCIMENTO_ABS')
    fig_bar = px.bar(
        top10_abs, 
        y='MUNICÍPIO', 
        x='CRESCIMENTO_ABS', 
        color='UF',
        orientation='h',
        text_auto='.2s',
        labels={'CRESCIMENTO_ABS': 'Aumento (hab)', 'MUNICÍPIO': ''}
    )
    fig_bar.update_layout(yaxis={'categoryorder':'total ascending'})
    st.plotly_chart(fig_bar, use_container_width=True)

with col_graf2:
    st.subheader("Dispersão e Outliers (Crescimento %)")
    fig_box = px.box(
        df_filtrado, 
        x='UF', 
        y='CRESCIMENTO_PCT', 
        color='UF',
        points="all", 
        hover_data=['MUNICÍPIO', 'POP_2022'],
        labels={'CRESCIMENTO_PCT': 'Crescimento (%)'}
    )
    st.plotly_chart(fig_box, use_container_width=True)

st.markdown("---")
st.subheader("📈 Crescimento Agregado por Estado Selecionado")
df_uf = df_filtrado.groupby('UF')[['POP_2010', 'POP_2022']].sum().reset_index()
df_uf_melt = df_uf.melt(id_vars="UF", value_vars=["POP_2010", "POP_2022"], var_name="Ano", value_name="População")
df_uf_melt['Ano'] = df_uf_melt['Ano'].str.replace('POP_', '')

fig_line = px.line(
    df_uf_melt, 
    x="Ano", 
    y="População", 
    color="UF", 
    markers=True
)
st.plotly_chart(fig_line, use_container_width=True)

with st.expander("Visualizar Tabela Completa de Dados"):
    st.dataframe(df_filtrado.sort_values(by="CRESCIMENTO_PCT", ascending=False), use_container_width=True)

st.markdown("---")
st.subheader("📰 Contexto: A Transição Demográfica no Brasil")
col_noticia1, col_noticia2 = st.columns([2, 1])

with col_noticia1:
    st.info("""
    **Análise de Políticas Públicas:** 
    A desaceleração do crescimento populacional e o rápido envelhecimento trazem desafios imediatos para os gestores urbanos. Planos Diretores de capitais e regiões metropolitanas precisam ser readequados para investir menos na expansão de creches e mais em infraestrutura acessível e saúde focada na terceira idade, conforme observado na mudança drástica de certas pirâmides etárias municipais.
    """)
with col_noticia2:
    st.image("https://placehold.co/400x200/2b5c8f/ffffff?text=Expansao+Urbana+e+Demografia",
             caption="Readequação do espaço urbano.")