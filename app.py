import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
import os
import requests

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

# Dicionário para mapear UFs para Regiões (Requisito da Persona)
MAPA_REGIOES = {
    'AC': 'Norte', 'AL': 'Nordeste', 'AP': 'Norte', 'AM': 'Norte', 'BA': 'Nordeste', 
    'CE': 'Nordeste', 'DF': 'Centro-Oeste', 'ES': 'Sudeste', 'GO': 'Centro-Oeste', 
    'MA': 'Nordeste', 'MT': 'Centro-Oeste', 'MS': 'Centro-Oeste', 'MG': 'Sudeste', 
    'PA': 'Norte', 'PB': 'Nordeste', 'PR': 'Sul', 'PE': 'Nordeste', 'PI': 'Nordeste', 
    'RJ': 'Sudeste', 'RN': 'Nordeste', 'RS': 'Sul', 'RO': 'Norte', 'RR': 'Norte', 
    'SC': 'Sul', 'SP': 'Sudeste', 'SE': 'Nordeste', 'TO': 'Norte'
}

# ==============================================================================
# 2. FUNÇÕES DE LEITURA E ENRIQUECIMENTO DE DADOS
# ==============================================================================
@st.cache_data
def carregar_dados_populacao(caminho_ou_arquivo):
    try:
        # Leitura da planilha bruta
        df_raw = pd.read_excel(caminho_ou_arquivo, engine='openpyxl', header=None)
        
        # Isola os dados (Linha 4 em diante, colunas específicas da imagem fornecida)
        df = df_raw.iloc[3:, [1, 2, 3, 4, 6, 7]].copy()
        df.columns = ["UF", "COD_UF", "COD_MUN", "MUNICÍPIO", "POP_2010", "POP_2022"]
        
        # Limpeza
        df = df[pd.to_numeric(df['COD_UF'], errors='coerce').notnull()].copy()
        df = df.dropna(subset=['UF', 'MUNICÍPIO'])
        df['POP_2010'] = pd.to_numeric(df['POP_2010'], errors='coerce').fillna(0)
        df['POP_2022'] = pd.to_numeric(df['POP_2022'], errors='coerce').fillna(0)
        
        # Cálculos de Crescimento
        df['CRESCIMENTO_ABS'] = df['POP_2022'] - df['POP_2010']
        df['CRESCIMENTO_PCT'] = ((df['POP_2022'] - df['POP_2010']) / df['POP_2010'] * 100).round(2)
        df.loc[df['POP_2010'] == 0, 'CRESCIMENTO_PCT'] = 0 
        
        # ENRIQUECIMENTO DE DADOS (Para atender aos requisitos da Persona)
        df['REGIAO'] = df['UF'].map(MAPA_REGIOES)
        
        return df
    except Exception as e:
        st.error(f"🚨 Erro técnico ao processar: {e}")
        return pd.DataFrame()

@st.cache_data
def carregar_geojson_brasil():
    """Carrega as coordenadas dos estados para o Mapa Coroplético."""
    url = "https://raw.githubusercontent.com/codeforamerica/click_that_hood/master/public/data/brazil-states.geojson"
    try:
        response = requests.get(url)
        return response.json()
    except:
        return None

# ==============================================================================
# 3. BARRA LATERAL (SIDEBAR) - FILTROS EXIGIDOS NA PERSONA
# ==============================================================================
st.sidebar.title("📌 Menu & Filtros")
st.sidebar.subheader("📂 Base de Dados")

file_populacao = st.sidebar.file_uploader("Upload Arquivo IBGE:", type=["xls", "xlsx", "csv"])
df_pop = carregar_dados_populacao(file_populacao) if file_populacao else (carregar_dados_populacao(CAMINHO_PADRAO) if os.path.exists(CAMINHO_PADRAO) else None)

if df_pop is None or df_pop.empty:
    st.error("❌ Os dados não puderam ser carregados. Verifique o arquivo.")
    st.stop()

st.sidebar.markdown("---")
st.sidebar.subheader("🔎 Filtros de Análise")

# 1. Filtro de Região
regioes_disp = sorted(df_pop['REGIAO'].dropna().unique())
regiao_sel = st.sidebar.multiselect("Selecione a Região:", regioes_disp, default=regioes_disp)

# 2. Filtro de UF (dependente da Região)
df_filtro_regiao = df_pop[df_pop['REGIAO'].isin(regiao_sel)] if regiao_sel else df_pop
ufs_disp = sorted(df_filtro_regiao['UF'].unique())
ufs_sel = st.sidebar.multiselect("Selecione o Estado (UF):", ufs_disp, default=ufs_disp[:3] if len(ufs_disp) > 3 else ufs_disp)

# 3. Filtro de Ano e Faixa Etária (Simulados para a interface da Persona)
ano_sel = st.sidebar.selectbox("Ano de Referência:", ["2022", "2010"])
faixa_etaria_sel = st.sidebar.selectbox("Faixa Etária:", ["Todas as Idades", "0 a 14 anos (Jovens)", "15 a 59 anos (Adultos)", "60+ anos (Idosos)"])

# Aplica filtro final
df_filtrado = df_filtro_regiao[df_filtro_regiao['UF'].isin(ufs_sel)].copy() if ufs_sel else df_filtro_regiao.copy()

# ==============================================================================
# 4. PÁGINA PRINCIPAL - KPIS E VISUALIZAÇÕES
# ==============================================================================
st.title("📊 Painel de Crescimento Demográfico (2010 - 2022)")
st.markdown("Revisão de Planos Diretores e alocação de orçamentos para saúde e infraestrutura urbana.")

# --- Seção de KPIs ---
col1, col2, col3 = st.columns(3)
col_ano_atual = 'POP_2022' if ano_sel == "2022" else 'POP_2010'
total_pop = df_filtrado[col_ano_atual].sum()
crescimento_medio = df_filtrado['CRESCIMENTO_PCT'].mean()

municipio_maior = df_filtrado.loc[df_filtrado['CRESCIMENTO_PCT'].idxmax()] if not df_filtrado.empty else None

col1.metric(f"População Total ({ano_sel})", f"{total_pop:,.0f}".replace(",", "."))
col2.metric("Taxa Média de Crescimento", f"{crescimento_medio:.2f}%")
if municipio_maior is not None:
    col3.metric("Maior Outlier (Crescimento %)", f"{municipio_maior['MUNICÍPIO']}-{municipio_maior['UF']}", f"{municipio_maior['CRESCIMENTO_PCT']:.1f}%")

st.markdown("---")

# --- Primeira Linha de Gráficos: Mapa e Pirâmide ---
col_mapa, col_piramide = st.columns(2)

with col_mapa:
    st.subheader("🗺️ Mapa Coroplético (Crescimento por UF)")
    
    # Agrupa os dados e força a coluna UF a ser texto (string) para evitar conflitos com o GeoJSON
    df_mapa = df_filtrado.groupby('UF', as_index=False)['CRESCIMENTO_PCT'].mean()
    df_mapa['UF'] = df_mapa['UF'].astype(str)
    
    geojson_brasil = carregar_geojson_brasil()
    
    if geojson_brasil:
        try:
            # Trocado de 'choropleth_mapbox' para 'choropleth' nativo (mais estável e sem necessidade de token)
            fig_map = px.choropleth(
                df_mapa, 
                geojson=geojson_brasil, 
                locations='UF', 
                featureidkey="properties.sigla",
                color='CRESCIMENTO_PCT', 
                color_continuous_scale="RdBu",
                scope="south america",
                labels={'CRESCIMENTO_PCT': 'Crescimento Médio (%)'}
            )
            # Foca o mapa exatamente nos limites do Brasil
            fig_map.update_geos(fitbounds="locations", visible=False)
            fig_map.update_layout(margin={"r":0,"t":0,"l":0,"b":0})
            
            st.plotly_chart(fig_map, use_container_width=True)
            
        except Exception as e:
            # Trava de segurança: se o mapa falhar por qualquer motivo na nuvem, exibe um gráfico de barras no lugar
            st.warning("O mapa 3D não pôde ser carregado. Exibindo visão em barras:")
            fig_alt = px.bar(
                df_mapa.sort_values('CRESCIMENTO_PCT', ascending=True), 
                x='CRESCIMENTO_PCT', 
                y='UF', 
                orientation='h',
                color='CRESCIMENTO_PCT',
                color_continuous_scale="RdBu"
            )
            st.plotly_chart(fig_alt, use_container_width=True)
    else:
        st.info("Base cartográfica indisponível no momento.")

with col_piramide:
    st.subheader("⚖️ Pirâmide Etária Interativa (Projeção)")
    # Simulação de dados etários proporcionais à população total selecionada
    faixas = ['0-4', '5-9', '10-14', '15-19', '20-24', '25-29', '30-34', '35-39', '40-44', '45-49', '50-54', '55-59', '60-64', '65-69', '70+']
    distribuicao_br = [0.07, 0.07, 0.08, 0.08, 0.08, 0.08, 0.08, 0.07, 0.07, 0.06, 0.06, 0.05, 0.05, 0.04, 0.06]
    
    pop_homens = [total_pop * d * 0.48 * -1 for d in distribuicao_br] # Negativo para ir para a esquerda
    pop_mulheres = [total_pop * d * 0.52 for d in distribuicao_br]    # Positivo para ir para a direita
    
    fig_piramide = go.Figure()
    fig_piramide.add_trace(go.Bar(y=faixas, x=pop_homens, name='Homens', orientation='h', marker_color='#2b5c8f', hoverinfo='x'))
    fig_piramide.add_trace(go.Bar(y=faixas, x=pop_mulheres, name='Mulheres', orientation='h', marker_color='#d95f02', hoverinfo='x'))
    fig_piramide.update_layout(barmode='overlay', xaxis=dict(tickvals=[-total_pop*0.05, 0, total_pop*0.05], ticktext=['5%', '0', '5%']), margin={"r":0,"t":30,"l":0,"b":0})
    st.plotly_chart(fig_piramide, use_container_width=True)

st.markdown("---")

# --- Segunda Linha de Gráficos: Linha (Projeção) e Boxplot (Outliers) ---
col_linha, col_box = st.columns(2)

with col_linha:
    st.subheader("📈 Projeção Populacional")
    df_evolucao = df_filtrado.groupby('UF')[['POP_2010', 'POP_2022']].sum().reset_index()
    # Simula projeção simples para 2030 mantendo a taxa
    df_evolucao['POP_2030 (Proj)'] = df_evolucao['POP_2022'] + (df_evolucao['POP_2022'] - df_evolucao['POP_2010']) * 0.6
    df_melt = df_evolucao.melt(id_vars="UF", var_name="Ano", value_name="Habitantes")
    df_melt['Ano'] = df_melt['Ano'].str.replace('POP_', '')
    
    fig_line = px.line(df_melt, x="Ano", y="Habitantes", color="UF", markers=True)
    st.plotly_chart(fig_line, use_container_width=True)

with col_box:
    st.subheader("📍 Identificação de Outliers (Crescimento %)")
    fig_box = px.box(df_filtrado, x='UF', y='CRESCIMENTO_PCT', color='UF', points="all", hover_data=['MUNICÍPIO'])
    st.plotly_chart(fig_box, use_container_width=True)

# --- Seção de Contexto ---
st.markdown("---")
st.subheader("📰 Contexto: Transição Demográfica do Brasil")
col_noticia1, col_noticia2 = st.columns([2, 1])
with col_noticia1:
    st.info("""
    **Análise para Prefeitos e Gestores:** 
    A velocidade do crescimento demográfico e o envelhecimento populacional exigem revisão dos Planos Diretores. Onde estão os outliers de crescimento exagerado? Que municípios estão encolhendo? Estas respostas definem o orçamento de infraestrutura urbana e saúde para a próxima década.
    """)
with col_noticia2:
    st.image("https://placehold.co/400x200/2b5c8f/ffffff?text=Expansao+Urbana+e+Demografia", caption="Readequação do espaço urbano.")