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

# Caminho padrão do arquivo caso esteja no repositório
CAMINHO_PADRAO = "CD2022_Populacao_2010_Compatibilizada_20231222.xlsx"

# ==============================================================================
# 2. FUNÇÕES DE LEITURA E LIMPEZA COM PANDAS
# ==============================================================================
@st.cache_data
def carregar_dados_populacao(caminho_ou_arquivo):
    """
    Lê a planilha do Censo do IBGE e padroniza as colunas para análise.
    Ignora as linhas de cabeçalho iniciais e rodapés comuns em planilhas do IBGE.
    """
    try:
        # Adicionado engine='openpyxl' explicitamente para evitar erros no Streamlit Cloud
        df = pd.read_excel(caminho_ou_arquivo, skiprows=4, skipfooter=10, engine='openpyxl')
        
        # Renomear colunas para facilitar manipulação baseado no padrão do IBGE
        colunas_esperadas = ["UF", "COD_UF", "COD_MUN", "MUNICÍPIO", "POP_2010", "POP_2022"]
        
        # Ajusta o número de colunas lidas (pega as 6 primeiras que costumam ter os dados chave)
        df = df.iloc[:, :6] 
        df.columns = colunas_esperadas
        
        # Limpeza e conversão de tipos
        df = df.dropna(subset=['UF', 'MUNICÍPIO'])
        df['POP_2010'] = pd.to_numeric(df['POP_2010'], errors='coerce').fillna(0)
        df['POP_2022'] = pd.to_numeric(df['POP_2022'], errors='coerce').fillna(0)
        
        # Cálculos de crescimento
        df['CRESCIMENTO_ABS'] = df['POP_2022'] - df['POP_2010']
        df['CRESCIMENTO_PCT'] = ((df['POP_2022'] - df['POP_2010']) / df['POP_2010'] * 100).round(2)
        
        # Tratar casos de divisão por zero
        df.loc[df['POP_2010'] == 0, 'CRESCIMENTO_PCT'] = 0 
        
        return df
    except Exception as e:
        # Exibe o erro técnico exato na tela para facilitar a correção
        st.error(f"🚨 Erro detalhado do Python ao ler o arquivo: {e}")
        return None

# ==============================================================================
# 3. BARRA LATERAL (SIDEBAR) - CARREGAMENTO DE DADOS E FILTROS
# ==============================================================================
st.sidebar.title("📌 Menu & Filtros")

st.sidebar.subheader("📂 Base de Dados")
file_populacao = st.sidebar.file_uploader(
    "Upload Arquivo IBGE (CD2022_Populacao...):", 
    type=["xls", "xlsx", "csv"]
)

df_pop = None

# Lógica de carregamento: arquivo do upload ou caminho padrão local/nuvem
if file_populacao is not None:
    df_pop = carregar_dados_populacao(file_populacao)
elif os.path.exists(CAMINHO_PADRAO):
    df_pop = carregar_dados_populacao(CAMINHO_PADRAO)
else:
    st.warning("⚠️ **Aguardando base de dados.**")
    st.info(f"Faça o upload do arquivo `{CAMINHO_PADRAO}` na barra lateral para iniciar a análise.")
    st.stop()

if df_pop is None or df_pop.empty:
    st.error("❌ Não foi possível extrair dados válidos do arquivo. Se houver um erro vermelho acima, verifique o motivo (ex: abas ou formato).")
    st.stop()

st.sidebar.markdown("---")
# Filtros Geográficos
ufs_disponiveis = sorted(df_pop['UF'].unique())
ufs_selecionadas = st.sidebar.multiselect(
    "Filtre por Estado (UF):", 
    ufs_disponiveis, 
    default=ufs_disponiveis[:5] if len(ufs_disponiveis) > 5 else ufs_disponiveis
)

if ufs_selecionadas:
    df_filtrado = df_pop[df_pop['UF'].isin(ufs_selecionadas)].copy()
else:
    df_filtrado = df_pop.copy()

# ==============================================================================
# 4. PÁGINA PRINCIPAL - KPIS E VISUALIZAÇÕES
# ==============================================================================
st.title("📊 Painel de Crescimento Demográfico (2010 - 2022)")
st.markdown("Análise baseada nos dados do Censo IBGE para identificação de padrões de crescimento populacional municipal.")

# --- Seção de KPIs ---
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

# --- Seção de Gráficos ---
col_graf1, col_graf2 = st.columns(2)

with col_graf1:
    st.subheader("Top 10 Municípios (Maior Crescimento Absoluto)")
    top10_abs = df_filtrado.nlargest(10, 'CRESCIMENTO_ABS')
    fig_bar = px.bar(
        top10_abs, 
        y='MUNICÍPIO', 
        x='CRESCIMENTO_ABS', 
        color='UF',
        orientation='h',
        text_auto='.2s',
        labels={'CRESCIMENTO_ABS': 'Aumento Populacional (hab)', 'MUNICÍPIO': ''},
        title="Cidades que mais ganharam habitantes"
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
        labels={'CRESCIMENTO_PCT': 'Crescimento (%)'},
        title="Distribuição do Crescimento Populacional Relativo"
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
    markers=True,
    title="Evolução da População 2010-2022 por UF"
)
st.plotly_chart(fig_line, use_container_width=True)

# --- Seção de Dados Tabulares ---
with st.expander("Visualizar Tabela Completa de Dados"):
    st.dataframe(df_filtrado.sort_values(by="CRESCIMENTO_PCT", ascending=False), use_container_width=True)

# --- Seção de Contexto (Requisito da Persona) ---
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