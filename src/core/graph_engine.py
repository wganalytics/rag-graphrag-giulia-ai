import os
from typing import List
from dotenv import load_dotenv
from langchain_ollama import ChatOllama
from langchain_neo4j import Neo4jGraph, GraphCypherQAChain
from langchain_experimental.graph_transformers import LLMGraphTransformer
from langchain_core.documents import Document

# Carregar variáveis de ambiente
load_dotenv()

class GraphExtractor:
    """
    Extrator responsável por converter texto livre em Nós e Arestas do Grafo no Neo4j.
    """
    def __init__(self):
        model_name = os.getenv("ENGINE_MODEL_NAME", "llama3.2:latest")
        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self.llm = ChatOllama(model=model_name, base_url=base_url, temperature=0.0)
        
        # Conexão com o Banco de Grafos
        uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        username = os.getenv("NEO4J_USERNAME", "neo4j")
        password = os.getenv("NEO4J_PASSWORD", "password123")
        
        try:
            self.graph = Neo4jGraph(url=uri, username=username, password=password)
            self.transformer = LLMGraphTransformer(llm=self.llm)
        except Exception as e:
            print(f"Erro ao conectar ao Neo4j: {e}")
            self.graph = None

    def extract_and_store(self, text: str):
        """
        Extrai entidades e relações de um texto e as salva no Neo4j.
        """
        if not self.graph:
            return "Erro: Conexão com Neo4j não estabelecida."

        # Converte texto para Documento LangChain
        docs = [Document(page_content=text)]
        
        # Extrai grafos do documento
        graph_documents = self.transformer.convert_to_graph_documents(docs)
        
        # Ajuste: Garantir que as entidades tenham 'name' para facilitar o QA
        for graph_doc in graph_documents:
            for node in graph_doc.nodes:
                if 'name' not in node.properties:
                    node.properties['name'] = node.id
        
        # Salva no Neo4j
        self.graph.add_graph_documents(graph_documents)

        
        return f"Sucesso: {len(graph_documents)} documentos de grafo processados."

    def get_schema(self):
        if self.graph:
            return self.graph.schema
        return "Schema indisponível."


class GraphRetrievalQA:
    """
    Motor que recebe a pergunta do usuário e a converte em linguagem Cypher 
    para navegar nas arestas do Grafo e encontrar a resposta.
    """
    def __init__(self):
        model_name = os.getenv("ENGINE_MODEL_NAME", "llama3.2:latest")
        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self.llm = ChatOllama(model=model_name, base_url=base_url, temperature=0.0)
        
        # Conexão com o Grafo
        uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        username = os.getenv("NEO4J_USERNAME", "neo4j")
        password = os.getenv("NEO4J_PASSWORD", "password123")
        
        try:
            self.graph = Neo4jGraph(url=uri, username=username, password=password)
        except Exception as e:
            print(f"Erro ao conectar ao Neo4j: {e}")
            self.graph = None

    def ask(self, question: str) -> str:
        if not self.graph:
            return "Erro: Neo4j indisponível."
            
        try:
            # Refresh schema to ensure LLM knows latest nodes/relationships
            self.graph.refresh_schema()
            
            chain = GraphCypherQAChain.from_llm(
                cypher_llm=self.llm,
                qa_llm=self.llm,
                graph=self.graph,
                verbose=True,
                allow_dangerous_requests=True
            )
            response = chain.invoke({"query": question})
            return response.get("result", "Desculpe, não encontrei uma resposta baseada nas relações do grafo.")
        except Exception as e:
            return f"Erro na travessia do grafo: {str(e)}"
