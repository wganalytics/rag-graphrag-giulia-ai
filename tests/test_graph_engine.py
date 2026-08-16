import pytest
from unittest.mock import patch, MagicMock
from src.core.graph_engine import GraphExtractor, GraphRetrievalQA


@patch('src.core.graph_engine.Neo4jGraph')
@patch('src.core.graph_engine.LLMGraphTransformer')
@patch('src.core.graph_engine.get_llm')
def test_graph_extraction_pipeline(mock_get_llm, mock_transformer, mock_graph):
    # Setup mocks
    mock_transformer_instance = mock_transformer.return_value
    mock_transformer_instance.convert_to_graph_documents.return_value = [MagicMock(), MagicMock()]

    extractor = GraphExtractor()
    texto = "João trabalha na Google que fica em Mountain View."

    # Execução
    result = extractor.extract_and_store(texto)

    # Asserções
    assert "Sucesso" in result
    assert mock_transformer_instance.convert_to_graph_documents.called
    assert extractor.graph.add_graph_documents.called


@patch('src.core.graph_engine.Neo4jGraph')
@patch('src.core.graph_engine.GraphCypherQAChain')
@patch('src.core.graph_engine.get_llm')
def test_cypher_qa_navigation(mock_get_llm, mock_chain, mock_graph):
    # Setup
    mock_chain_instance = mock_chain.from_llm.return_value
    mock_chain_instance.invoke.return_value = {"result": "A Google fica em Mountain View."}

    qa_engine = GraphRetrievalQA()
    pergunta = "Onde fica a empresa que o João trabalha?"

    # Execução
    resposta = qa_engine.ask(pergunta)

    # Asserção
    assert "Mountain View" in resposta
    assert mock_chain_instance.invoke.called


@patch('src.core.graph_engine.get_llm')
def test_neo4j_unavailable_handling(mock_get_llm):
    with patch('src.core.graph_engine.Neo4jGraph', side_effect=Exception("Connection Refused")):
        extractor = GraphExtractor()
        assert extractor.graph is None
        result = extractor.extract_and_store("Teste")
        assert "Erro" in result


# ---------------------------------------------------------------------------
# Seleção de provider: o motor deve repassar provider/modelo para a fábrica
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("provider,modelo", [
    ("ollama", "llama3.2:3b"),
    ("gemini", "gemini-2.5-flash"),
    ("grok", "grok-4-latest"),
    ("groq", "llama-3.3-70b-versatile"),
])
@patch('src.core.graph_engine.Neo4jGraph')
@patch('src.core.graph_engine.LLMGraphTransformer')
@patch('src.core.graph_engine.get_llm')
def test_extrator_usa_provider_solicitado(mock_get_llm, _transformer, _graph, provider, modelo):
    extractor = GraphExtractor(provider=provider, model=modelo)

    assert extractor.provider == provider
    assert extractor.model_name == modelo
    mock_get_llm.assert_called_once_with(provider, modelo, temperature=0.0)


@pytest.mark.parametrize("provider", ["ollama", "gemini", "grok", "groq"])
@patch('src.core.graph_engine.Neo4jGraph')
@patch('src.core.graph_engine.get_llm')
def test_qa_usa_provider_solicitado(mock_get_llm, _graph, provider):
    qa_engine = GraphRetrievalQA(provider=provider, model="modelo-x")

    assert qa_engine.provider == provider
    mock_get_llm.assert_called_once_with(provider, "modelo-x", temperature=0.0)


@patch('src.core.graph_engine.Neo4jGraph')
@patch('src.core.graph_engine.get_llm')
def test_provider_padrao_vem_do_ambiente(mock_get_llm, _graph, monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_MODEL_NAME", "gemini-2.5-pro")

    qa_engine = GraphRetrievalQA()

    assert qa_engine.provider == "gemini"
    assert qa_engine.model_name == "gemini-2.5-pro"
