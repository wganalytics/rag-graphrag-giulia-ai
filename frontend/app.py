import streamlit as st
import sys
import os

# Adiciona o diretório src ao path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.core.graph_engine import GraphExtractor, GraphRetrievalQA
from src.core.llm_factory import (
    LLMConfigError,
    PROVIDERS,
    PROVIDER_LABELS,
    SEM_CREDITO,
    CHAVE_INVALIDA,
    LIMITE_TAXA,
    MODELO_INEXISTENTE,
    list_provider_status,
    modelos_ollama,
    probe_provider,
    resolve_model,
    resolve_provider,
)

# O que fazer diante de cada categoria de falha.
SUGESTOES = {
    SEM_CREDITO: "Adicione crédito no painel do provider — a chave está correta.",
    CHAVE_INVALIDA: "Gere uma nova chave e atualize o .env.",
    LIMITE_TAXA: "Aguarde um pouco antes de tentar de novo.",
    MODELO_INEXISTENTE: "Confira o nome do modelo no .env.",
}


def icone_de(status):
    """✅ respondeu · ⚙️ configurado mas não testado · ⛔ falhou ou incompleto."""
    if not status.available:
        return "⛔"
    if status.verified is True:
        return "✅"
    if status.verified is False:
        return "⛔"
    return "⚙️"

st.set_page_config(page_title="GraphRAG Explorer", layout="wide")

st.title("🕸️ PRJ-06: GraphRAG - Explorador de Relações")
st.markdown("---")


# ---------------------------------------------------------------------------
# Sidebar: escolha do motor de LLM (local ou externo)
# ---------------------------------------------------------------------------
st.sidebar.title("Configurações")

@st.cache_resource(show_spinner="Testando os motores de LLM...")
def motores_testados():
    """
    Testa cada provider com uma chamada real, uma vez por processo.

    É feito no carregamento para que o seletor já ofereça só o que funciona:
    exigir um clique antes significaria oferecer motores quebrados na primeira
    tela, que é exatamente o que se quer evitar.
    """
    resultado = []
    for nome in PROVIDERS:
        try:
            resultado.append(probe_provider(nome))
        except LLMConfigError:
            pass
    return resultado


status_por_provider = {s.provider: s for s in motores_testados()}
funcionais = [p for p, s in status_por_provider.items() if s.verified is True]
quebrados = [p for p, s in status_por_provider.items() if s.verified is not True]

mostrar_todos = st.sidebar.checkbox(
    "Mostrar motores indisponíveis",
    value=not funcionais,
    help="Por padrão o seletor lista apenas os motores que responderam ao teste.",
)

ofertados = list(status_por_provider.keys()) if mostrar_todos else funcionais

if not ofertados:
    st.sidebar.error("Nenhum motor de LLM disponível.")
    st.error(
        "Nenhum motor de LLM está funcionando. Veja o motivo de cada um abaixo "
        "e ajuste o `.env` (ou suba o Ollama local)."
    )
    for s in status_por_provider.values():
        st.write(f"{icone_de(s)} **{s.provider}** — {s.reason}")
        if s.categoria in SUGESTOES:
            st.caption(SUGESTOES[s.categoria])
    st.stop()

padrao = resolve_provider()
provider_escolhido = st.sidebar.selectbox(
    "Motor de LLM",
    options=ofertados,
    index=ofertados.index(padrao) if padrao in ofertados else 0,
    format_func=lambda p: PROVIDER_LABELS[p],
    help="Ollama roda local, sem custo. Gemini, Grok e Groq são APIs externas.",
)

status = status_por_provider[provider_escolhido]

# No Ollama a máquina sabe quais modelos existem: oferecer a lista evita
# errar o nome e só descobrir na primeira pergunta. Nos providers de nuvem
# não há como listar, então segue campo livre.
modelos_locais = modelos_ollama() if provider_escolhido == "ollama" else []
padrao_modelo = resolve_model(provider_escolhido)

if modelos_locais:
    if padrao_modelo not in modelos_locais:
        modelos_locais = [padrao_modelo] + modelos_locais
    modelo_escolhido = st.sidebar.selectbox(
        "Modelo",
        options=modelos_locais,
        index=modelos_locais.index(padrao_modelo),
        help="Modelos instalados no Ollama desta máquina.",
    )
else:
    modelo_escolhido = st.sidebar.text_input(
        "Modelo",
        value=padrao_modelo,
        help="Nome do modelo no provider selecionado.",
    )

if status.verified is True:
    st.sidebar.success("Respondeu ao teste")
elif not status.available:
    st.sidebar.error(f"Indisponível: {status.reason}")
else:
    st.sidebar.error(status.reason)
    if status.categoria in SUGESTOES:
        st.sidebar.caption(SUGESTOES[status.categoria])

if quebrados:
    st.sidebar.caption(f"Fora do seletor: {', '.join(quebrados)}")

# Falta de crédito e chave revogada só aparecem numa chamada real — reexecutar
# o teste é a forma de reconhecer que um motor voltou a funcionar.
if st.sidebar.button("🔄 Testar motores de novo", use_container_width=True):
    motores_testados.clear()
    st.rerun()

with st.sidebar.expander("Status de todos os motores"):
    for s in status_por_provider.values():
        st.write(f"{icone_de(s)} **{s.provider}** — `{s.model}` — {s.reason}")
        if s.detail:
            st.caption(s.detail[:180])
        if s.categoria in SUGESTOES:
            st.caption(SUGESTOES[s.categoria])


@st.cache_resource(show_spinner="Inicializando motores...")
def get_engines(provider: str, model: str):
    """Cria os motores para a combinação provider+modelo (cacheados por chave)."""
    return GraphExtractor(provider=provider, model=model), GraphRetrievalQA(provider=provider, model=model)


# Só é possível chegar aqui com um motor quebrado marcando "mostrar
# indisponíveis" — nesse caso explicamos o motivo em vez de deixar o usuário
# descobrir com um erro no meio da consulta.
if status.verified is not True:
    st.error(f"O motor **{provider_escolhido}** não está operacional: {status.reason}")
    if status.categoria in SUGESTOES:
        st.info(SUGESTOES[status.categoria])
    if status.detail:
        st.caption(status.detail[:300])
    st.stop()

try:
    extractor, qa_engine = get_engines(provider_escolhido, modelo_escolhido)
except LLMConfigError as e:
    st.error(f"Erro de configuração do LLM: {e}")
    st.stop()

st.caption(f"Motor ativo: **{PROVIDER_LABELS[provider_escolhido]}** · modelo `{modelo_escolhido}`")

tab1, tab2, tab3 = st.tabs(["📥 Ingestão de Conhecimento", "💬 Chat de Relações", "🔍 Schema do Grafo"])

with tab1:
    st.header("Alimentar o Grafo")
    st.info("Insira um texto rico em relacionamentos (ex: 'A Empresa X é sócia da Empresa Y que pertence ao Grupo Z').")

    text_input = st.text_area("Texto para Extração", height=150, placeholder="Digite aqui...")

    if st.button("Extrair e Salvar no Neo4j"):
        if text_input:
            with st.spinner("O LLM está extraindo entidades e relações..."):
                result = extractor.extract_and_store(text_input)
                st.success(result)
        else:
            st.warning("Por favor, insira um texto.")

with tab2:
    st.header("Consultar o Grafo (Cypher QA)")
    st.markdown("""
    Perguntas ideais para GraphRAG:
    - *'Quem são os sócios da Empresa X?'*
    - *'Qual a relação entre a Entidade A e a Entidade B?'*
    - *'Liste todas as subsidiárias do Grupo Y.'*
    """)

    if "messages" not in st.session_state:
        st.session_state.messages = []

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if prompt := st.chat_input("Pergunte ao Grafo..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Navegando nas arestas do grafo..."):
                response = qa_engine.ask(prompt)
                st.markdown(response)
                st.session_state.messages.append({"role": "assistant", "content": response})

with tab3:
    st.header("Schema Atual")
    if st.button("Atualizar Schema"):
        schema = extractor.get_schema()
        st.code(schema, language="text")
    else:
        st.write("Clique no botão para carregar o schema do banco de dados.")

st.sidebar.markdown("---")
if extractor.graph:
    st.sidebar.success("Conectado ao Neo4j (Porta 7687)")
else:
    st.sidebar.error("Neo4j indisponível")

if st.sidebar.button("Limpar Banco de Dados (Cuidado!)"):
    if extractor.graph:
        extractor.graph.query("MATCH (n) DETACH DELETE n")
        st.sidebar.warning("Banco de dados resetado.")
        st.rerun()
