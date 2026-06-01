import os
from langchain_neo4j import Neo4jGraph

# Configurações do Banco
uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
username = os.getenv("NEO4J_USERNAME", "neo4j")
password = os.getenv("NEO4J_PASSWORD", "password123")

def seed_database():
    try:
        print("Conectando ao Neo4j...")
        graph = Neo4jGraph(url=uri, username=username, password=password)
        
        print("Limpando banco de dados atual...")
        graph.query("MATCH (n) DETACH DELETE n")
        
        print("Injetando relacionamentos complexos corporativos...")
        
        cypher_seed = """
        // Criando Pessoas
        CREATE (p1:Person {name: 'Carlos Silva', role: 'CEO'})
        CREATE (p2:Person {name: 'Ana Souza', role: 'CTO'})
        CREATE (p3:Person {name: 'Marcos Almeida', role: 'CFO'})
        CREATE (p4:Person {name: 'Julia Mendes', role: 'Diretora Jurídica'})
        
        // Criando Empresas
        CREATE (c1:Company {name: 'TechGlobal Holding', industry: 'Tecnologia'})
        CREATE (c2:Company {name: 'DataSolutions Ltda', industry: 'Dados'})
        CREATE (c3:Company {name: 'SecurAI Corp', industry: 'Cibersegurança'})
        CREATE (c4:Company {name: 'Venture Capital X', industry: 'Investimentos'})
        
        // Criando Projetos
        CREATE (pr1:Project {name: 'Projeto Alpha', status: 'Ativo'})
        CREATE (pr2:Project {name: 'Migração Cloud', status: 'Concluído'})
        
        // --- RELACIONAMENTOS ---
        
        // Estrutura Societária
        CREATE (c2)-[:SUBSIDIARIA_DE]->(c1)
        CREATE (c3)-[:SUBSIDIARIA_DE]->(c1)
        CREATE (c4)-[:INVESTE_EM {percentual: 30}]->(c1)
        
        // Cargos e Pessoas
        CREATE (p1)-[:TRABALHA_EM {cargo: 'CEO'}]->(c1)
        CREATE (p1)-[:CONSELHEIRO_DE]->(c4)
        
        CREATE (p2)-[:TRABALHA_EM {cargo: 'CTO'}]->(c1)
        CREATE (p2)-[:FUNDADOR_DE]->(c2)
        
        CREATE (p3)-[:TRABALHA_EM {cargo: 'CFO'}]->(c1)
        
        CREATE (p4)-[:TRABALHA_EM {cargo: 'Diretora Jurídica'}]->(c3)
        CREATE (p4)-[:RESPONDE_PARA]->(p1)
        
        // Projetos e Responsabilidades
        CREATE (p2)-[:GERENCIA]->(pr1)
        CREATE (p2)-[:GERENCIA]->(pr2)
        CREATE (c2)-[:DESENVOLVE]->(pr1)
        CREATE (c1)-[:FINANCIA]->(pr1)
        """
        
        graph.query(cypher_seed)
        
        print("✅ Injeção concluída com sucesso! Grafo populado com:")
        print("- 4 Pessoas")
        print("- 4 Empresas")
        print("- 2 Projetos")
        print("- Estrutura Societária e Múltiplos Relacionamentos Criados.")
        
    except Exception as e:
        print(f"Erro ao injetar dados: {e}")

if __name__ == "__main__":
    seed_database()
