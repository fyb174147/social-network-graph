# -*- coding: utf-8 -*-
"""
Neo4j Exporter and Loader for Vietnamese Politicians Graph.
Generates Cypher scripts (.cql/.cypher), GraphML, CSVs, and interacts
directly with Neo4j via official Python driver.
"""
import os
import json
import csv
import networkx as nx
from src.config import EXPORT_DIR

class Neo4jGraphExporter:
    def __init__(self, G, export_dir=EXPORT_DIR):
        self.G = G
        self.export_dir = export_dir
        os.makedirs(export_dir, exist_ok=True)
        self.cypher_path = os.path.join(self.export_dir, "vietnamese_politicians.cypher")
        self.graphml_path = os.path.join(self.export_dir, "vietnamese_politicians.graphml")
        self.json_path = os.path.join(self.export_dir, "graph_data.json")
        self.nodes_csv_path = os.path.join(self.export_dir, "nodes.csv")
        self.edges_csv_path = os.path.join(self.export_dir, "edges.csv")

    def export_cypher_script(self):
        """Generate high-performance Cypher script with indexes and UNWIND batches."""
        print(f"Exporting Cypher script to {self.cypher_path}...", flush=True)
        
        with open(self.cypher_path, 'w', encoding='utf-8') as f:
            f.write("// =========================================================\n")
            f.write("// ĐỒ THỊ MẠNG LƯỚI CHÍNH TRỊ GIA VIỆT NAM\n")
            f.write("// Khai thác Infobox kết hợp NLP phân tích Quá trình công tác\n")
            f.write("// =========================================================\n\n")
            
            # Constraints & Indexes
            f.write("// --- 1. CONSTRAINTS & INDEXES ---\n")
            for label in ["Politician", "Organization", "Position", "Location", "Term"]:
                f.write(f"CREATE CONSTRAINT IF NOT EXISTS FOR (n:{label}) REQUIRE n.id IS UNIQUE;\n")
                f.write(f"CREATE INDEX IF NOT EXISTS FOR (n:{label}) ON (n.name);\n")
            f.write("\n")
            
            # Group nodes by label
            nodes_by_label = {}
            for node_id, data in self.G.nodes(data=True):
                lbl = data.get('label', 'Entity')
                if lbl not in nodes_by_label:
                    nodes_by_label[lbl] = []
                node_dict = {'id': node_id}
                for k, v in data.items():
                    if k != 'label':
                        # Escape strings
                        if isinstance(v, str):
                            node_dict[k] = v.replace('"', '\\"').replace('\n', ' ')
                        else:
                            node_dict[k] = v
                nodes_by_label[lbl].append(node_dict)
                
            # Write Nodes in UNWIND batches
            f.write("// --- 2. BATCH CREATE NODES ---\n")
            for lbl, nodes in nodes_by_label.items():
                batch_size = 500
                for b_i in range(0, len(nodes), batch_size):
                    batch = nodes[b_i:b_i + batch_size]
                    json_str = json.dumps(batch, ensure_ascii=False)
                    f.write(f":param batch_{lbl}_{b_i} => {json_str};\n")
                    f.write(f"UNWIND $batch_{lbl}_{b_i} AS row\n")
                    f.write(f"MERGE (n:{lbl} {{id: row.id}})\n")
                    f.write("SET n += row;\n\n")
                    
            # Group edges by relation type
            edges_by_type = {}
            for u, v, d in self.G.edges(data=True):
                rel_type = d.get('type', 'RELATED_TO')
                if rel_type not in edges_by_type:
                    edges_by_type[rel_type] = []
                edge_dict = {'source': u, 'target': v}
                for k, val in d.items():
                    if k != 'type':
                        if isinstance(val, str):
                            edge_dict[k] = val.replace('"', '\\"').replace('\n', ' ')
                        else:
                            edge_dict[k] = val
                edges_by_type[rel_type].append(edge_dict)
                
            # Write Edges in UNWIND batches
            f.write("// --- 3. BATCH CREATE RELATIONSHIPS ---\n")
            for r_type, edges in edges_by_type.items():
                batch_size = 500
                for b_i in range(0, len(edges), batch_size):
                    batch = edges[b_i:b_i + batch_size]
                    json_str = json.dumps(batch, ensure_ascii=False)
                    f.write(f":param batch_rel_{r_type}_{b_i} => {json_str};\n")
                    f.write(f"UNWIND $batch_rel_{r_type}_{b_i} AS row\n")
                    f.write("MATCH (u {id: row.source})\n")
                    f.write("MATCH (v {id: row.target})\n")
                    f.write(f"MERGE (u)-[r:{r_type}]->(v)\n")
                    f.write("SET r += apoc.map.clean(row, ['source', 'target'], []);\n\n")
                    
        print(f"Cypher script generated successfully: {self.cypher_path}", flush=True)

    def export_graphml(self):
        """Export graph to GraphML format for Gephi and Cytoscape."""
        print(f"Exporting GraphML to {self.graphml_path}...", flush=True)
        # Create a clean copy with string attributes
        clean_G = nx.MultiDiGraph()
        for n, d in self.G.nodes(data=True):
            clean_attrs = {}
            for k, v in d.items():
                clean_attrs[k] = str(v) if not isinstance(v, (int, float, bool)) else v
            clean_G.add_node(n, **clean_attrs)
            
        for u, v, k, d in self.G.edges(keys=True, data=True):
            clean_attrs = {}
            for prop, val in d.items():
                clean_attrs[prop] = str(val) if not isinstance(val, (int, float, bool)) else val
            clean_G.add_edge(u, v, key=k, **clean_attrs)
            
        nx.write_graphml(clean_G, self.graphml_path, encoding='utf-8')
        print(f"GraphML exported successfully: {self.graphml_path}", flush=True)

    def export_csv(self):
        """Export CSV files for Neo4j Bulk Import and tabular analytics."""
        print(f"Exporting CSVs to {self.nodes_csv_path} and {self.edges_csv_path}...", flush=True)
        
        # Nodes CSV
        with open(self.nodes_csv_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['id:ID', 'name', ':LABEL', 'birth_year', 'hometown', 'education', 'party', 'type', 'is_central'])
            for n, d in self.G.nodes(data=True):
                writer.writerow([
                    n,
                    d.get('name', ''),
                    d.get('label', 'Entity'),
                    d.get('birth_year', ''),
                    d.get('hometown', ''),
                    d.get('education', ''),
                    d.get('party', ''),
                    d.get('type', ''),
                    d.get('is_central', '')
                ])
                
        # Edges CSV
        with open(self.edges_csv_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([':START_ID', ':END_ID', ':TYPE', 'weight', 'start_year', 'end_year', 'term', 'role', 'direction', 'evidence'])
            for u, v, d in self.G.edges(data=True):
                writer.writerow([
                    u,
                    v,
                    d.get('type', 'RELATED_TO'),
                    d.get('weight', 1.0),
                    d.get('start_year', ''),
                    d.get('end_year', ''),
                    d.get('term', ''),
                    d.get('role') or d.get('office') or d.get('superior_role') or '',
                    d.get('direction', ''),
                    d.get('evidence', '')[:120]
                ])
        print(f"CSVs exported successfully.", flush=True)

    def export_json_for_web(self):
        """Export graph to JSON format for Vis.js / D3 interactive visualization."""
        print(f"Exporting Web JSON to {self.json_path}...", flush=True)
        
        nodes_list = []
        edges_list = []
        
        # Color mapping for node labels
        color_map = {
            'Politician': '#1E88E5',   # Blue
            'Organization': '#43A047', # Green
            'Position': '#FB8C00',     # Orange
            'Location': '#E53935',     # Red
            'Term': '#8E24AA'          # Purple
        }
        
        for n, d in self.G.nodes(data=True):
            lbl = d.get('label', 'Entity')
            nodes_list.append({
                'id': n,
                'label': d.get('name', n),
                'group': lbl,
                'color': color_map.get(lbl, '#757575'),
                'title': f"<b>{d.get('name', n)}</b><br>Loại: {lbl}<br>{d.get('hometown', '')}",
                'degree': self.G.degree(n)
            })
            
        edge_id = 0
        for u, v, d in self.G.edges(data=True):
            edge_id += 1
            edges_list.append({
                'id': f"e_{edge_id}",
                'from': u,
                'to': v,
                'label': d.get('type', ''),
                'title': f"Quan hệ: {d.get('type', '')}<br>{d.get('role', '')} {d.get('term', '')}",
                'arrows': 'to'
            })
            
        payload = {
            'nodes': nodes_list,
            'edges': edges_list,
            'stats': {
                'node_count': len(nodes_list),
                'edge_count': len(edges_list)
            }
        }
        
        with open(self.json_path, 'w', encoding='utf-8') as f:
            json.dump(payload, f, ensure_ascii=False)
            
        print(f"JSON data exported successfully: {self.json_path}", flush=True)

    def load_to_neo4j(self, uri="bolt://localhost:7687", user="neo4j", password="password"):
        """Attempt direct import into running Neo4j instance."""
        try:
            from neo4j import GraphDatabase
            driver = GraphDatabase.driver(uri, auth=(user, password))
            with driver.session() as session:
                # Test connectivity
                result = session.run("RETURN 1 AS connected")
                rec = result.single()
                if rec and rec["connected"] == 1:
                    print("Successfully connected to Neo4j database!", flush=True)
                    # Create constraints
                    for lbl in ["Politician", "Organization", "Position", "Location", "Term"]:
                        session.run(f"CREATE CONSTRAINT IF NOT EXISTS FOR (n:{lbl}) REQUIRE n.id IS UNIQUE")
                    
                    # Batch insert nodes
                    print("Importing nodes into Neo4j...", flush=True)
                    for n, d in self.G.nodes(data=True):
                        lbl = d.get('label', 'Entity')
                        props = {k: v for k, v in d.items() if k != 'label'}
                        session.run(f"MERGE (n:{lbl} {{id: $id}}) SET n += $props", id=n, props=props)
                        
                    # Batch insert edges
                    print("Importing relationships into Neo4j...", flush=True)
                    for u, v, d in self.G.edges(data=True):
                        rel_type = d.get('type', 'RELATED_TO')
                        session.run(
                            f"MATCH (u {{id: $u}}), (v {{id: $v}}) "
                            f"MERGE (u)-[r:{rel_type}]->(v) "
                            f"SET r += $props",
                            u=u, v=v, props=d
                        )
                    print("Neo4j import completed successfully!", flush=True)
                    return True
        except Exception as e:
            print(f"Notice: Could not connect to local Neo4j instance ({e}).", flush=True)
            print(f"The graph has been fully exported to Cypher ({self.cypher_path}), GraphML, CSV, and Web JSON.", flush=True)
            return False
