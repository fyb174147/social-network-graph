# -*- coding: utf-8 -*-
"""
End-to-End Pipeline for Vietnamese Politicians Knowledge Graph (Approach 3):
Hybrid Snowball BFS Corpus + Infobox/NLP Extraction + Local LLM Entity Canonicalization (qwen3.5-custom:latest).
"""
import os
import sys
import json
import time

sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from src.config import RAW_DATA_DIR, PROCESSED_DATA_DIR, EXPORT_DIR, REPORT_FIG_DIR
from src.crawler_snowball import HybridSnowballCrawler
from src.llm_normalizer import LocalLLMNormalizer, DEFAULT_MODEL
from src.llm_graph_builder import LLMGraphBuilder
from src.neo4j_loader import Neo4jGraphExporter
from src.graph_analyzer import PoliticianGraphAnalyzer


def _model_slug(model_name):
    return "".join(ch if ch.isalnum() or ch in ("-", "_", ".") else "_" for ch in model_name)


def load_or_crawl_raw_corpus(raw_dir, refresh=False, target_count=2050):
    raw_file = os.path.join(raw_dir, "raw_politicians_snowball.json")
    trace_file = os.path.join(raw_dir, "snowball_trace.json")

    if not refresh and os.path.exists(raw_file):
        with open(raw_file, 'r', encoding='utf-8') as f:
            raw_pages = json.load(f)
        trace = {}
        if os.path.exists(trace_file):
            with open(trace_file, 'r', encoding='utf-8') as f:
                trace = json.load(f)
        print(f"-> Đã nạp {len(raw_pages)} bài viết từ {raw_file}", flush=True)
        return raw_pages, trace

    crawler = HybridSnowballCrawler(raw_dir)
    return crawler.crawl_snowball_bfs(target_count=target_count)


def run(model_name=DEFAULT_MODEL, batch_size=15, refresh_crawl=False, target_count=2050):
    print("=" * 72)
    print(f" APPROACH 3: HYBRID NLP + LOCAL LLM ({model_name}) CANONICALIZATION")
    print("=" * 72)
    t0 = time.time()

    for d in (RAW_DATA_DIR, PROCESSED_DATA_DIR, EXPORT_DIR, REPORT_FIG_DIR):
        os.makedirs(d, exist_ok=True)

    print("\n[BƯỚC 1/5] Nạp / Thu thập dữ liệu Wikipedia tiếng Việt (Hybrid Snowball)...", flush=True)
    raw_pages, bfs_trace = load_or_crawl_raw_corpus(
        RAW_DATA_DIR, refresh=refresh_crawl, target_count=target_count
    )

    cache_filename = f"llm_canonical_cache_{_model_slug(model_name)}.json"
    print(f"\n[BƯỚC 2/5] Trích xuất Infobox/NLP & Chuẩn hóa thực thể bằng {model_name}...", flush=True)
    normalizer = LocalLLMNormalizer(
        model=model_name,
        cache_path=os.path.join(PROCESSED_DATA_DIR, cache_filename),
        report_path=os.path.join(PROCESSED_DATA_DIR, "llm_canonical_mapping_report.json"),
        batch_size=batch_size
    )
    builder = LLMGraphBuilder(normalizer=normalizer)
    G = builder.build_from_raw_data(raw_pages)
    subG = builder.project_politician_subgraph()

    print("\n[BƯỚC 3/5] Xuất dữ liệu đồ thị (Cypher, GraphML, CSV, JSON)...", flush=True)
    exporter = Neo4jGraphExporter(G, export_dir=EXPORT_DIR)
    exporter.export_cypher_script()
    exporter.export_graphml()
    exporter.export_csv()
    exporter.export_json_for_web()

    print("\n[BƯỚC 4/5] Phân tích mạng xã hội & tính các chỉ số đồ thị...", flush=True)
    analyzer = PoliticianGraphAnalyzer(G, subG, fig_dir=REPORT_FIG_DIR)
    stats = analyzer.compute_summary_stats()
    centralities = analyzer.compute_centralities()
    communities = analyzer.detect_communities()
    mobility = analyzer.analyze_cadre_mobility()

    summary = {
        'bfs_trace': bfs_trace,
        'llm_canonicalization': builder.canonicalization_stats,
        'stats': stats,
        'centralities': centralities,
        'communities': communities,
        'mobility': mobility
    }
    stats_file = os.path.join(PROCESSED_DATA_DIR, "network_stats.json")
    with open(stats_file, 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print("\n[BƯỚC 5/5] Vẽ biểu đồ phân tích cho báo cáo...", flush=True)
    analyzer.generate_all_plots(stats, centralities, communities)

    elapsed = time.time() - t0
    print("\n" + "=" * 72)
    print(f" HOÀN TẤT PIPELINE TRONG {elapsed:.1f} GIÂY!")
    print(f" Tổng số nút (Nodes): {stats['total_nodes']}")
    print(f" Tổng số cạnh (Edges): {stats['total_edges']}")
    print(f" Số nút Position sau chuẩn hóa: {stats['node_labels'].get('Position', 0)}")
    print(f" Thành phần liên thông lớn nhất (LCC): {stats['largest_connected_component_size']} chính khách")
    print("=" * 72)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description="Run Standalone Approach 3 Pipeline")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Ollama model tag (default: qwen3.5-custom:latest)")
    parser.add_argument("--batch-size", type=int, default=15, help="Items per Ollama batch (default: 15)")
    parser.add_argument("--refresh-crawl", action="store_true", help="Re-crawl Wikipedia instead of reading local raw JSON")
    parser.add_argument("--target-count", type=int, default=2050, help="Target politician count when crawling")
    args = parser.parse_args()
    run(
        model_name=args.model,
        batch_size=args.batch_size,
        refresh_crawl=args.refresh_crawl,
        target_count=args.target_count
    )
