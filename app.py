import json
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title="População e Crescimento Demográfico", page_icon="📊", layout="wide", initial_sidebar_state="expanded")
BASE = Path(__file__).resolve().parent
REGIOES = {"Norte": ["AC", "AP", "AM", "PA", "RO", "RR", "TO"], "Nordeste": ["AL", "BA", "CE", "MA", "PB", "PE", "PI", "RN", "SE"], "Centro-Oeste": ["DF", "GO", "MT", "MS"], "Sudeste": ["ES", "MG", "RJ", "SP"], "Sul": ["PR", "RS", "SC"]}
UF_COD = {"11":"RO","12":"AC","13":"AM","14":"RR","15":"PA","16":"AP","17":"TO","21":"MA","22":"PI","23":"CE","24":"RN","25":"PB","26":"PE","27":"AL","28":"SE","29":"BA","31":"MG","32":"ES","33":"RJ","35":"SP","41":"PR","42":"SC","43":"RS","50":"MS","51":"MT","52":"GO","53":"DF"}
CAPITAIS = {"Elisa — Belo Horizonte": "Belo Horizonte", "Carlos — Curitiba": "Curitiba", "Eduardo — Porto Alegre": "Porto Alegre", "Jorge — Salvador": "Salvador", "Roberto — Florianópolis": "Florianópolis"}
MAPA_REGIAO = {uf: regiao for regiao, ufs in REGIOES.items() for uf in ufs}
PADRAO = BASE / "H:\Demografia_Inteligente_Elisa_BH\populacao_2010_2022.csv"


def ler_arquivo(arquivo):
    nome = getattr(arquivo, "name", str(arquivo)).lower()
    if nome.endswith(".csv"):
        try:
            return pd.read_csv(arquivo, sep=None, engine="python", dtype=str)
        except UnicodeDecodeError:
            arquivo.seek(0) if hasattr(arquivo, "seek") else None
            return pd.read_csv(arquivo, sep=None, engine="python", dtype=str, encoding="latin1")
    if nome.endswith(".ods"):
        return pd.read_excel(arquivo, header=None, dtype=str, engine="odf")
    return pd.read_excel(arquivo, header=None, dtype=str, engine="openpyxl")


def numero(serie):
    s = serie.astype("string").str.strip().str.replace(r"\s", "", regex=True)
    s = s.str.replace(r"(?<=\d)\.(?=\d{3}(?:\D|$))", "", regex=True)
    s = s.str.replace(",", ".", regex=False)
    return pd.to_numeric(s, errors="coerce")


def tratar_dados(bruto):
    nomes = {str(c).strip().lower() for c in bruto.columns}
    if {"uf", "municipio", "pop2010", "pop2022"}.issubset(nomes):
        df = bruto.copy()
        df.columns = [str(c).strip().lower() for c in df.columns]
        df = df.rename(columns={"municipio": "nome_munic", "pop2010": "pop2010", "pop2022": "pop2022"})
        df["uf"] = df["uf"].astype(str).str.upper().str.strip()
    else:
        # Planilha IBGE: detecta linhas municipais pelo código de município (7 dígitos).
        # Layout usual: UF/região, código UF, código municipal, município, e três valores de população.
        candidatos = []
        for i in range(min(bruto.shape[1], 12)):
            col = bruto.iloc[:, i].astype("string").str.strip().str.replace(r"\.0$", "", regex=True)
            contagem = col.str.fullmatch(r"\d{7}", na=False).sum()
            candidatos.append((int(contagem), i))
        quantidade, indice = max(candidatos)
        if quantidade < 10:
            raise ValueError("Não foi possível identificar a coluna de código municipal de 7 dígitos. Confira o layout do arquivo.")
        if indice + 4 >= bruto.shape[1]:
            raise ValueError("Não há colunas suficientes após o código municipal para localizar as populações.")
        codigos = bruto.iloc[:, indice].astype("string").str.strip().str.replace(r"\.0$", "", regex=True)
        valido = codigos.str.fullmatch(r"\d{7}", na=False)
        df = pd.DataFrame({
            "codigo_municipio": codigos[valido],
            "nome_munic": bruto.iloc[:, indice + 1][valido],
            "pop2010": bruto.iloc[:, indice + 3][valido],
            "pop2022": bruto.iloc[:, indice + 4][valido],
        })
        df["uf"] = df["codigo_municipio"].str[:2].map(UF_COD)
    df["nome_munic"] = df["nome_munic"].astype("string").str.strip()
    df["pop2010"] = numero(df["pop2010"])
    df["pop2022"] = numero(df["pop2022"])
    df = df.dropna(subset=["uf", "nome_munic", "pop2010", "pop2022"])
    df = df[(df.pop2010 > 0) & (df.pop2022 >= 0) & df.uf.isin(MAPA_REGIAO)]
    df = df.drop_duplicates(subset=["uf", "nome_munic"], keep="first").copy()
    if df.empty:
        raise ValueError("O arquivo não contém municípios com populações válidas nos dois censos.")
    df["regiao"] = df["uf"].map(MAPA_REGIAO)
    df["variacao_abs"] = df.pop2022 - df.pop2010
    df["crescimento_pct"] = (df.pop2022 / df.pop2010 - 1) * 100
    df["taxa_anual_pct"] = ((df.pop2022 / df.pop2010) ** (1 / 12) - 1) * 100
    return df.reset_index(drop=True)


@st.cache_data(show_spinner="Lendo dados do IBGE...")
def carregar_padrao(caminho):
    return tratar_dados(ler_arquivo(caminho))


@st.cache_data(show_spinner="Processando arquivo enviado...")
def carregar_upload(conteudo, nome):
    from io import BytesIO
    arquivo = BytesIO(conteudo)
    arquivo.name = nome
    return tratar_dados(ler_arquivo(arquivo))


def fmt(valor):
    return f"{valor:,.0f}".replace(",", ".")


def crescimento(a, b):
    return (b / a - 1) * 100 if a > 0 else np.nan


st.sidebar.title("📌 Menu & Filtros")
st.sidebar.subheader("📂 Arquivo de entrada (Pandas)")
upload = st.sidebar.file_uploader("Enviar tabela do IBGE", type=["xlsx", "csv", "ods"])
try:
    if upload is not None:
        dados = carregar_upload(upload.getvalue(), upload.name)
    elif PADRAO.exists():
        dados = carregar_padrao(str(PADRAO))
    else:
        st.warning("⚠️ Aguardando leitura dos dados pelo Pandas.")
        st.info(f"Envie a planilha pelo menu lateral ou coloque o arquivo **{PADRAO.name}** na pasta do app.py.")
        st.stop()
except Exception as erro:
    st.error(f"Erro ao carregar a tabela: {erro}")
    st.stop()

persona = st.sidebar.selectbox("👤 Persona / Gestor", list(CAPITAIS))
regiao = st.sidebar.selectbox("🌎 Região", ["Todas"] + list(REGIOES), index=0)
ufs = sorted(dados.loc[dados.regiao.eq(regiao) if regiao != "Todas" else dados.uf.notna(), "uf"].unique().tolist())
selecao_uf = st.sidebar.multiselect("Unidade da Federação", ufs, default=["MG"] if "MG" in ufs else ufs)
municipios = dados[dados.uf.isin(selecao_uf)].copy()
if municipios.empty:
    st.warning("Selecione pelo menos uma UF com dados.")
    st.stop()
nomes = sorted(municipios.nome_munic.unique().tolist())
filtro_municipio = st.sidebar.multiselect("Municípios (opcional)", nomes)
if filtro_municipio:
    municipios = municipios[municipios.nome_munic.isin(filtro_municipio)].copy()
anos = st.sidebar.multiselect("Anos do censo", [2010, 2022], default=[2010, 2022])
faixa = st.sidebar.selectbox("Faixa etária", ["Todas", "0–14", "15–29", "30–59", "60+"])
pagina = st.sidebar.radio("📊 Página", ["Visão geral", "Crescimento e outliers", "Mapa por UF", "Pirâmide etária", "Projeções", "Contexto"])

st.title("📊 População e Crescimento Demográfico")
st.caption("Censo IBGE 2010 (população compatibilizada) e Censo 2022")
st.info(f"**Gestor selecionado:** {persona}. Objetivo: apoiar o Plano Diretor e os investimentos em saúde, mobilidade e infraestrutura.")
if set(anos) != {2010, 2022}:
    st.warning("O cálculo de crescimento usa os dois censos (2010 e 2022), independentemente do filtro de visualização.")
if faixa != "Todas":
    st.caption("A faixa etária só é aplicada na página Pirâmide etária, mediante arquivo complementar com idade e sexo.")

if pagina == "Visão geral":
    p10, p22 = municipios.pop2010.sum(), municipios.pop2022.sum()
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("População 2010", fmt(p10))
    col2.metric("População 2022", fmt(p22))
    col3.metric("Crescimento acumulado", f"{crescimento(p10, p22):.2f}%")
    col4.metric("Crescimento anual médio", f"{((p22 / p10) ** (1/12) - 1)*100:.2f}%")
    st.subheader("Comparação entre capitais")
    capitais = municipios[municipios.nome_munic.isin(CAPITAIS.values())]
    if capitais.empty:
        st.info("Nenhuma das cinco capitais está no filtro atual.")
    else:
        fig = px.bar(capitais, x="nome_munic", y="crescimento_pct", color="crescimento_pct", color_continuous_scale="RdYlGn", labels={"nome_munic":"Capital", "crescimento_pct":"Crescimento (%)"})
        st.plotly_chart(fig, width="stretch")
    st.subheader("Dados tratados")
    colunas = ["regiao", "uf", "nome_munic"] + (["pop2010"] if 2010 in anos else []) + (["pop2022"] if 2022 in anos else []) + ["variacao_abs", "crescimento_pct", "taxa_anual_pct"]
    st.dataframe(municipios[colunas], width="stretch", hide_index=True)
    st.download_button("📥 Baixar dados filtrados (CSV)", municipios.to_csv(index=False).encode("utf-8-sig"), "dados_demograficos.csv", "text/csv")
elif pagina == "Crescimento e outliers":
    st.subheader("Municípios que mais cresceram e encolheram")
    minimo = st.slider("População mínima em 2010", 0, 100000, 1000, 1000)
    base = municipios[municipios.pop2010 >= minimo].copy()
    if len(base) < 4:
        st.warning("São necessários pelo menos quatro municípios após o filtro.")
    else:
        q1, q3 = base.crescimento_pct.quantile([.25, .75]); iqr = q3 - q1
        base["outlier"] = np.select([base.crescimento_pct > q3 + 1.5 * iqr, base.crescimento_pct < q1 - 1.5 * iqr], ["Crescimento excepcional", "Queda excepcional"], default="Faixa usual")
        st.plotly_chart(px.box(base, x="uf", y="crescimento_pct", points="outliers", labels={"crescimento_pct":"Crescimento (%)"}), width="stretch")
        esquerda, direita = st.columns(2)
        esquerda.write("**Maiores crescimentos**")
        esquerda.dataframe(base.nlargest(10, "crescimento_pct")[["nome_munic", "uf", "crescimento_pct", "outlier"]], hide_index=True)
        direita.write("**Maiores quedas**")
        direita.dataframe(base.nsmallest(10, "crescimento_pct")[["nome_munic", "uf", "crescimento_pct", "outlier"]], hide_index=True)
        st.caption("Outliers identificados pelo intervalo interquartil (IQR), calculado apenas nos municípios filtrados.")
elif pagina == "Mapa por UF":
    st.subheader("Crescimento populacional por UF")
    agregado = municipios.groupby("uf", as_index=False)[["pop2010", "pop2022"]].sum()
    agregado["crescimento_pct"] = (agregado.pop2022 / agregado.pop2010 - 1) * 100
    geo = BASE / "dados" / "br_ufs.geojson"
    if geo.exists():
        try:
            geojson = json.loads(geo.read_text(encoding="utf-8"))
            fig = px.choropleth_map(agregado, geojson=geojson, locations="uf", featureidkey="properties.sigla", color="crescimento_pct", color_continuous_scale="RdYlGn", map_style="carto-positron", zoom=3, center={"lat": -14.2, "lon": -51.9}, opacity=.75)
            fig.update_layout(height=550, margin=dict(l=0, r=0, t=0, b=0))
            st.plotly_chart(fig, width="stretch")
        except Exception as erro:
            st.warning(f"Não foi possível exibir o GeoJSON: {erro}")
    else:
        st.info("Para exibir o mapa geográfico, coloque dados/br_ufs.geojson com a propriedade 'sigla' em cada UF.")
    st.plotly_chart(px.bar(agregado.sort_values("crescimento_pct"), x="uf", y="crescimento_pct", color="crescimento_pct", color_continuous_scale="RdYlGn"), width="stretch")
elif pagina == "Pirâmide etária":
    st.subheader("Pirâmide etária")
    st.write("Envie CSV com colunas **uf, faixa_etaria, sexo, populacao**. O arquivo de população municipal não contém idades.")
    etario = st.file_uploader("Arquivo etário complementar (CSV)", type=["csv"])
    if etario:
        try:
            et = pd.read_csv(etario, sep=None, engine="python")
            et.columns = et.columns.str.strip().str.lower()
            if not {"uf", "faixa_etaria", "sexo", "populacao"}.issubset(et.columns):
                st.error("Colunas necessárias: uf, faixa_etaria, sexo, populacao.")
            else:
                et["populacao"] = numero(et["populacao"])
                et = et[et.uf.astype(str).str.upper().isin(selecao_uf)].dropna(subset=["populacao"])
                if faixa != "Todas":
                    et = et[et.faixa_etaria.astype(str).eq(faixa)]
                et = et.groupby(["faixa_etaria", "sexo"], as_index=False).populacao.sum()
                et["valor"] = np.where(et.sexo.astype(str).str.lower().str.contains("masc|homem"), -et.populacao, et.populacao)
                if et.empty:
                    st.info("Sem dados etários para os filtros escolhidos.")
                else:
                    st.plotly_chart(px.bar(et, x="valor", y="faixa_etaria", color="sexo", orientation="h", barmode="relative", labels={"valor":"População", "faixa_etaria":"Faixa etária"}), width="stretch")
        except Exception as erro:
            st.error(f"Erro no arquivo etário: {erro}")
    else:
        st.info("Aguardando arquivo complementar. Nenhum dado etário é simulado.")
elif pagina == "Projeções":
    st.subheader("Cenário matemático de projeção")
    opcoes = sorted(municipios[["uf", "nome_munic"]].itertuples(index=False, name=None))
    rotulos = [f"{nome} — {uf}" for uf, nome in opcoes]
    preferido = CAPITAIS[persona]
    inicial = next((i for i, (uf, nome) in enumerate(opcoes) if nome == preferido), 0)
    indice = st.selectbox("Município", range(len(opcoes)), index=inicial, format_func=lambda i: rotulos[i])
    uf_escolhida, nome_escolhido = opcoes[indice]
    m = municipios[(municipios.uf == uf_escolhida) & (municipios.nome_munic == nome_escolhido)].iloc[0]
    ajuste = st.slider("Ajuste da taxa anual (pontos percentuais)", -3.0, 3.0, 0.0, .1)
    horizonte = st.slider("Ano final", 2023, 2050, 2035)
    proj = pd.DataFrame({"ano": range(2022, horizonte + 1)})
    proj["populacao"] = m.pop2022 * (1 + (m.taxa_anual_pct + ajuste) / 100) ** (proj.ano - 2022)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=[2010, 2022], y=[m.pop2010, m.pop2022], mode="lines+markers", name="Censos observados"))
    fig.add_trace(go.Scatter(x=proj.ano, y=proj.populacao, mode="lines", name="Cenário ilustrativo", line_dash="dash"))
    st.plotly_chart(fig, width="stretch")
    st.metric(f"População estimada em {horizonte}", fmt(proj.populacao.iloc[-1]))
    st.warning("Este cenário extrapola a taxa de 2010–2022. Não é projeção oficial do IBGE e não modela separadamente migração, fecundidade e mortalidade.")
else:
    st.subheader("Contexto e decisões de gestão")
    st.write("O crescimento populacional pode orientar políticas de habitação, transporte, saneamento e serviços públicos. O envelhecimento exige dados adicionais por idade e sexo.")
    st.markdown("**Fontes:** [Censo 2022](https://censo2022.ibge.gov.br/) · [IBGE Cidades](https://cidades.ibge.gov.br/) · [Agência IBGE Notícias](https://agenciadenoticias.ibge.gov.br/)")

st.divider()
st.caption("Crescimento acumulado = (P2022 / P2010 − 1) × 100. Taxa anual = ((P2022 / P2010)^(1/12) − 1) × 100. Verifique a correspondência das colunas populacionais no arquivo de origem.")
