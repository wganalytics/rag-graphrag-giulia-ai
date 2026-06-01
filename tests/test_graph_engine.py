import pytest
from unittest.mock import patch, MagicMock
from src.core.graph_engine import GraphExtractor, GraphRetrievalQA

@patch('src.core.graph_engine.Neo4jGraph')
@patch('src.core.graph_engine.LLMGraphTransformer')
@patch('src.core.graph_engine.ChatOllama')
def test_graph_extraction_pipeline(mock_llm, mock_transformer, mock_graph):
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
@patch('src.core.graph_engine.ChatOllama')
def test_cypher_qa_navigation(mock_llm, mock_chain, mock_graph):
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

def test_neo4j_unavailable_handling():
    with patch('src.core.graph_engine.Neo4jGraph', side_effect=Exception("Connection Refused")):
        extractor = GraphExtractor()
        assert extractor.graph is None
        result = extractor.extract_and_store("Teste")
        assert "Erro" in result
