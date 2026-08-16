import os
from typing import Optional
from dotenv import load_dotenv
from langchain_neo4j import Neo4jGraph, GraphCypherQAChain
from langchain_experimental.graph_transformers import LLMGraphTransformer
from langchain_core.documents import Document
from langchain_core.prompts import PromptTemplate

from src.core.llm_factory import (
    get_llm,
    registrar_falha,
    registrar_sucesso,
    resolve_provider,
    resolve_model,
)

# Carregar variáveis de ambiente
load_dotenv()


# Prompt de geração de Cypher.
#
# O prompt padrão do LangChain não impõe nenhuma regra e os modelos erram de
# formas previsíveis: truncam o nome da entidade ("Projeto Alpha" vira "Alpha"),
# inventam relações que não existem no schema e tentam resolver dois saltos num
# padrão só. As regras abaixo existem por causa de falhas observadas.
CYPHER_GENERATION_TEMPLATE = """Você escreve consultas Cypher para o Neo4j.

Schema do grafo:
{schema}

REGRAS OBRIGATÓRIAS:
1. Use SOMENTE os rótulos e tipos de relação que aparecem no schema acima.
   Nunca invente um tipo de relação.
2. Para localizar uma entidade pelo nome, NUNCA use igualdade exata.
   Use sempre: toLower(x.name) CONTAINS toLower('termo')
   Isso protege contra diferenças de acento, caixa e nome parcial.
3. Use o nome COMPLETO como aparece na pergunta. Se a pergunta diz
   "Projeto Alpha", o termo de busca é 'Projeto Alpha' — nunca apenas 'Alpha'.
4. Se a pergunta exige dois passos (ex: "quem gerencia X e onde essa pessoa
   trabalha"), escreva os dois padrões encadeados na mesma consulta, cada um
   com sua própria relação. Não tente resolver com um padrão só.
5. Preste atenção na DIREÇÃO das setas do schema. Se estiver em dúvida entre
   -[:REL]-> e <-[:REL]-, use a relação sem direção: -[:REL]-
5b. Pronomes ("essa pessoa", "ele", "ela", "essa empresa") se referem à
   entidade que a PRIMEIRA parte da pergunta procura, não à entidade usada
   como referência. Em "quem responde para o CEO e onde essa pessoa trabalha",
   'essa pessoa' é quem responde — não o CEO. Ligue o segundo padrão à
   variável correta.
6. Retorne propriedades legíveis (ex: p.name), nunca o nó inteiro.
7. RETORNE TAMBÉM as entidades usadas como filtro, não só a resposta.
   Em "quem gerencia o Projeto Alpha e onde trabalha", retorne o nome do
   projeto além da pessoa e da empresa. Um resultado que não mostra o que foi
   filtrado parece incompleto para quem vai redigir a resposta.
8. Responda APENAS com a consulta Cypher, sem explicação e sem markdown.

Pergunta: {question}

Cypher:"""

CYPHER_GENERATION_PROMPT = PromptTemplate(
    input_variables=["schema", "question"],
    template=CYPHER_GENERATION_TEMPLATE,
)

# Prompt de síntese da resposta.
#
# O prompt padrão é conservador demais: modelos menores (e às vezes os grandes)
# respondem "não sei" mesmo com o resultado correto na mão, porque o resultado
# chega como lista de dicionários e não como texto. Aqui deixamos explícito que
# esses dados SÃO a resposta e que só lista vazia justifica não saber.
QA_TEMPLATE = """Você responde perguntas sobre um grafo de conhecimento.

A consulta ao banco já foi executada. O resultado abaixo é a VERDADE e é a
única fonte que você deve usar.

Resultado da consulta:
{context}

REGRAS:
1. Se o resultado tiver qualquer linha, ele contém a resposta. Formule uma
   frase natural em português usando esses valores. NÃO diga que não sabe.
2. Os dados chegam como lista de dicionários (ex: [{{'p.name': 'Ana'}}]).
   Isso é normal: use os valores, ignore os nomes técnicos das colunas.
3. Só responda "Não encontrei essa informação no grafo." se o resultado for
   uma lista vazia [].
4. Não invente nada que não esteja no resultado. Não peça mais contexto.
5. A consulta JÁ foi construída a partir da pergunta e já aplicou todos os
   filtros dela. Se existe uma linha no resultado, ela satisfaz a pergunta
   inteira — mesmo que alguma entidade citada na pergunta não apareça nas
   colunas. NUNCA responda "não é possível determinar" nem duvide do vínculo:
   o banco já confirmou.

Pergunta: {question}

Resposta:"""

QA_PROMPT = PromptTemplate(
    input_variables=["context", "question"],
    template=QA_TEMPLATE,
)


def connect_graph() -> Optional[Neo4jGraph]:
    """
    Abre a conexão com o Neo4j. Retorna None se o banco estiver indisponível,
    para que a aplicação suba e mostre o erro em vez de estourar no import.
    """
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    username = os.getenv("NEO4J_USERNAME", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "password123")

    try:
        return Neo4jGraph(url=uri, username=username, password=password)
    except Exception as e:
        print(f"Erro ao conectar ao Neo4j: {e}")
        return None


class GraphExtractor:
    """
    Extrator responsável por converter texto livre em Nós e Arestas do Grafo no Neo4j.

    O LLM usado na extração é definido pela fábrica: local (Ollama) ou externo
    (Gemini / Grok), conforme o provider recebido ou o LLM_PROVIDER do .env.
    """
    def __init__(self, provider: Optional[str] = None, model: Optional[str] = None):
        self.provider = resolve_provider(provider)
        self.model_name = resolve_model(self.provider, model)
        self.llm = get_llm(self.provider, self.model_name, temperature=0.0)

        # Conexão com o Banco de Grafos
        self.graph = connect_graph()
        if self.graph:
            self.transformer = LLMGraphTransformer(llm=self.llm)

    def extract_and_store(self, text: str):
        """
        Extrai entidades e relações de um texto e as salva no Neo4j.
        """
        if not self.graph:
            return "Erro: Conexão com Neo4j não estabelecida."

        # Converte texto para Documento LangChain
        docs = [Document(page_content=text)]

        # Extrai grafos do documento
        try:
            graph_documents = self.transformer.convert_to_graph_documents(docs)
            registrar_sucesso(self.provider)
        except Exception as e:
            registrar_falha(self.provider, e)
            raise

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

    Aceita o mesmo conjunto de providers do extrator — o LLM que traduz para
    Cypher pode ser local ou externo sem nenhuma outra mudança no fluxo.
    """
    def __init__(self, provider: Optional[str] = None, model: Optional[str] = None):
        self.provider = resolve_provider(provider)
        self.model_name = resolve_model(self.provider, model)
        self.llm = get_llm(self.provider, self.model_name, temperature=0.0)

        # Conexão com o Grafo
        self.graph = connect_graph()

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
                cypher_prompt=CYPHER_GENERATION_PROMPT,
                qa_prompt=QA_PROMPT,
                verbose=True,
                allow_dangerous_requests=True
            )
            response = chain.invoke({"query": question})
            registrar_sucesso(self.provider)
            return response.get("result", "Desculpe, não encontrei uma resposta baseada nas relações do grafo.")
        except Exception as e:
            # Alimenta o diagnóstico: assim a interface deixa de exibir
            # "Configurado" para um provider que na prática está recusando.
            registrar_falha(self.provider, e)
            return f"Erro na travessia do grafo: {str(e)}"
