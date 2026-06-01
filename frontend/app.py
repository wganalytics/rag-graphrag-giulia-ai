import streamlit as st
import sys
import os

# Adiciona o diretório src ao path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.core.graph_engine import GraphExtractor, GraphRetrievalQA

st.set_page_config(page_title="GraphRAG Explorer", layout="wide")

st.title("🕸️ PRJ-06: GraphRAG - Explorador de Relações")
st.markdown("---")

# Inicializa os motores
@st.cache_resource
def get_engines():
    return GraphExtractor(), GraphRetrievalQA()

extractor, qa_engine = get_engines()

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

st.sidebar.title("Configurações")
st.sidebar.success("Conectado ao Neo4j (Porta 7687)")
st.sidebar.info(f"Modelo Ativo: {os.getenv('ENGINE_MODEL_NAME', 'llama3.2')}")

if st.sidebar.button("Limpar Banco de Dados (Cuidado!)"):
    if extractor.graph:
        extractor.graph.query("MATCH (n) DETACH DELETE n")
        st.sidebar.warning("Banco de dados resetado.")
        st.rerun()
