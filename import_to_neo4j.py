# -*- coding: utf-8 -*-
"""
Fast Batch Importer for Neo4j (No APOC plugin required).
Loads Approach 3 exported CSVs from data/export/ into a Neo4j instance.
"""
import os
import sys
import csv
import getpass
from collections import defaultdict
from neo4j import GraphDatabase

sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def get_export_paths():
    exp_dir = os.path.join(BASE_DIR, "data", "export")
    return (
        os.path.join(exp_dir, "nodes.csv"),
        os.path.join(exp_dir, "edges.csv")
    )


def load_csv_data(nodes_csv, edges_csv):
    nodes_by_label = defaultdict(list)
    node_label_map = {}

    with open(nodes_csv, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            lbl = row[':LABEL'] or 'Entity'
            nid = row['id:ID']
            node_label_map[nid] = lbl

            node_props = {
                'id': nid,
                'name': row['name'],
            }
            if row.get('birth_year') and row['birth_year'].isdigit() and int(row['birth_year']) > 0:
                node_props['birth_year'] = int(row['birth_year'])
            if row.get('hometown'):
                node_props['hometown'] = row['hometown']
            if row.get('education'):
                node_props['education'] = row['education']
            if row.get('party'):
                node_props['party'] = row['party']
            if row.get('type'):
                node_props['type'] = row['type']
            if row.get('is_central') in ('True', 'False'):
                node_props['is_central'] = (row['is_central'] == 'True')
            nodes_by_label[lbl].append(node_props)

    edges_grouped = defaultdict(list)
    with open(edges_csv, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            rel_type = row[':TYPE'] or 'RELATED_TO'
            src_id = row[':START_ID']
            dst_id = row[':END_ID']
            src_lbl = node_label_map.get(src_id, 'Politician')
            dst_lbl = node_label_map.get(dst_id, 'Organization')

            props = {}
            if row.get('weight'):
                try:
                    props['weight'] = float(row['weight'])
                except ValueError:
                    pass
            if row.get('start_year') and row['start_year'].isdigit() and int(row['start_year']) > 0:
                props['start_year'] = int(row['start_year'])
            if row.get('end_year') and row['end_year'].isdigit() and int(row['end_year']) > 0:
                props['end_year'] = int(row['end_year'])
            if row.get('term'):
                props['term'] = row['term']
            if row.get('role'):
                props['role'] = row['role']
            if row.get('direction'):
                props['direction'] = row['direction']
            if row.get('evidence'):
                props['evidence'] = row['evidence']

            edges_grouped[(rel_type, src_lbl, dst_lbl)].append({
                'source': src_id,
                'target': dst_id,
                'props': props
            })

    return nodes_by_label, edges_grouped


def import_to_neo4j(uri="bolt://localhost:7687", user="neo4j", password=None):
    if not password:
        password = os.environ.get("NEO4J_PASSWORD")
    if not password:
        password = getpass.getpass(f"Nhập mật khẩu Neo4j (user '{user}'): ")

    nodes_csv, edges_csv = get_export_paths()
    print(f"Nguồn dữ liệu: {nodes_csv}", flush=True)
    print(f"Đang kết nối tới Neo4j tại {uri}...", flush=True)
    driver = GraphDatabase.driver(uri, auth=(user, password))

    try:
        driver.verify_connectivity()
        print("✔ Kết nối Neo4j thành công!", flush=True)
    except Exception as e:
        print(f"❌ Không thể kết nối hoặc sai mật khẩu: {e}")
        return False

    nodes_by_label, edges_grouped = load_csv_data(nodes_csv, edges_csv)

    with driver.session() as session:
        print("0. Làm sạch dữ liệu cũ trong Neo4j...", flush=True)
        session.run(
            "MATCH (n) "
            "WHERE n.id STARTS WITH 'pol_' OR n.id STARTS WITH 'org_' OR n.id STARTS WITH 'pos_' "
            "OR n.id STARTS WITH 'loc_' OR n.id STARTS WITH 'term_' OR n.id STARTS WITH 'grassroots_' "
            "DETACH DELETE n"
        )

        print("1. Tạo Constraints & Indexes...", flush=True)
        for lbl in ["Politician", "Organization", "Position", "Location", "Term"]:
            session.run(f"CREATE CONSTRAINT IF NOT EXISTS FOR (n:{lbl}) REQUIRE n.id IS UNIQUE")
            session.run(f"CREATE INDEX IF NOT EXISTS FOR (n:{lbl}) ON (n.name)")

        total_nodes = 0
        print("2. Đang nạp các nút (Nodes)...", flush=True)
        for lbl, rows in nodes_by_label.items():
            for i in range(0, len(rows), 1000):
                batch = rows[i:i + 1000]
                session.run(
                    f"UNWIND $batch AS row "
                    f"MERGE (n:{lbl} {{id: row.id}}) "
                    f"SET n += row",
                    batch=batch
                )
            total_nodes += len(rows)
            print(f"   - :{lbl}: {len(rows)} nút", flush=True)

        total_edges = 0
        counts_by_rel = defaultdict(int)
        print("3. Đang nạp các quan hệ (Relationships)...", flush=True)
        for (rel_type, src_lbl, dst_lbl), rows in edges_grouped.items():
            for i in range(0, len(rows), 1000):
                batch = rows[i:i + 1000]
                session.run(
                    f"UNWIND $batch AS row "
                    f"MATCH (u:{src_lbl} {{id: row.source}}) "
                    f"MATCH (v:{dst_lbl} {{id: row.target}}) "
                    f"CREATE (u)-[r:{rel_type}]->(v) "
                    f"SET r = row.props",
                    batch=batch
                )
            counts_by_rel[rel_type] += len(rows)
            total_edges += len(rows)

        for rel_type, cnt in sorted(counts_by_rel.items(), key=lambda x: -x[1]):
            print(f"   - [:{rel_type}]: {cnt} cạnh", flush=True)

        db_nodes = session.run("MATCH (n) RETURN count(n) AS c").single()["c"]
        db_edges = session.run("MATCH ()-[r]->() RETURN count(r) AS c").single()["c"]

    driver.close()
    print("\n✔ HOÀN TẤT! Đã nạp xong vào Neo4j.")
    print(f"   Kiểm chứng trực tiếp trong DB Neo4j: {db_nodes:,} nút và {db_edges:,} cạnh.")
    return True


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description="Import Vietnamese Politicians Graph (Approach 3) into Neo4j")
    parser.add_argument("password", nargs="?", default=None, help="Neo4j password")
    parser.add_argument("--uri", default="bolt://localhost:7687", help="Neo4j Bolt URI")
    parser.add_argument("--user", default="neo4j", help="Neo4j username")
    args = parser.parse_args()
    import_to_neo4j(uri=args.uri, user=args.user, password=args.password)
