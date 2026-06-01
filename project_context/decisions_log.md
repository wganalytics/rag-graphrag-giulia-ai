# PRJ-06 GraphRAG: Decisões Arquiteturais e Code Paths

Este documento centraliza as razões técnicas por trás das escolhas de código no PRJ-06, o Explorador de Relações via Grafos.

## 1. Por que usar Grafos de Conhecimento (Neo4j) em vez de apenas Vetores (ChromaDB)?
**Decisão:** Introdução de uma arquitetura GraphRAG suportada pelo Neo4j para armazenar dados no formato (Nó)-[Relação]->(Nó).
**Motivo:** Bancos vetoriais falham terrivelmente ao responder perguntas que exigem agregação ou entendimento estrutural complexo (ex: "Qual é a relação indireta entre a Empresa X e a Holding Y?"). Vetores buscam similaridade de texto, Grafos percorrem arestas estruturadas de forma determinística.

## 2. Por que usar `GraphCypherQAChain` do Langchain?
**Decisão:** O módulo de Retrieval usa um chain especializado em converter perguntas naturais para a linguagem de queries do Neo4j (Cypher).
**Motivo:** Escrever Cypher dinâmico "na mão" para cada intenção do usuário seria insustentável. Ao invés disso, fornecemos o *Schema* do Neo4j atualizado para o LLM via Langchain, e ele gera a query de travessia do grafo, executando a busca exata no banco de forma autônoma.

## 3. Por que mockar a interface do GraphExtractor nos Testes Iniciais?
**Decisão:** A suíte de TDD testa o pipeline simulando as saídas do LLM e a conexão do Neo4j via `@patch`.
**Motivo:** Garantir a robustez do fluxo lógico e das validações (DataOps) sem amarrar os testes automatizados (CI/CD) ao banco de grafos live. Testes que dependem de estado de banco externo e da API do Llama são lentos, instáveis e *flaky*. O Mock garante que o pipeline de software (Engenharia de verdade) funciona de forma isolada.
