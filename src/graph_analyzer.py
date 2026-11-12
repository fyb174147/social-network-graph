# -*- coding: utf-8 -*-
"""
Graph Analyzer for Vietnamese Politicians Network.
Computes comprehensive graph metrics, degree distributions, centrality
measures (Degree, Betweenness, PageRank), community detection, and
cadre mobility patterns. Generates plots for the final report.
"""
import os
import json
import networkx as nx
import matplotlib.pyplot as plt
import seaborn as sns
from collections import Counter
from src.config import REPORT_FIG_DIR

# Set clean styling for matplotlib
plt.rcParams['font.family'] = 'DejaVu Sans'
plt.rcParams['figure.autolayout'] = True

class PoliticianGraphAnalyzer:
    def __init__(self, G, subG=None, fig_dir=REPORT_FIG_DIR):
        self.G = G
        self.subG = subG if subG is not None else self._build_politician_subgraph()
        self.fig_dir = fig_dir
        os.makedirs(fig_dir, exist_ok=True)
        
    def _build_politician_subgraph(self):
        sub = nx.Graph()
        for n, d in self.G.nodes(data=True):
            if d.get('label') == 'Politician':
                sub.add_node(n, **d)
        for u, v, d in self.G.edges(data=True):
            if u in sub and v in sub and u != v:
                w = sub[u][v].get('weight', 0) if sub.has_edge(u, v) else 0
                sub.add_edge(u, v, weight=w + d.get('weight', 1.0))
        return sub

    def compute_summary_stats(self):
        """Calculate high-level graph topology statistics."""
        num_nodes = self.G.number_of_nodes()
        num_edges = self.G.number_of_edges()
        
        # Node labels breakdown
        labels_counter = Counter([d.get('label', 'Unknown') for _, d in self.G.nodes(data=True)])
        
        # Relation types breakdown
        rels_counter = Counter([d.get('type', 'Unknown') for _, _, d in self.G.edges(data=True)])
        
        # Degree statistics
        degrees = [d for _, d in self.G.degree()]
        avg_degree = sum(degrees) / len(degrees) if degrees else 0
        max_degree = max(degrees) if degrees else 0
        
        # Subgraph connectivity
        num_components = nx.number_connected_components(self.subG) if len(self.subG) > 0 else 0
        largest_cc_size = len(max(nx.connected_components(self.subG), key=len)) if len(self.subG) > 0 else 0
        
        density = nx.density(self.G)
        
        stats = {
            'total_nodes': num_nodes,
            'total_edges': num_edges,
            'node_labels': dict(labels_counter),
            'relation_types': dict(rels_counter),
            'avg_degree': round(avg_degree, 2),
            'max_degree': max_degree,
            'density': f"{density:.6f}",
            'politician_count': len(self.subG),
            'politician_components': num_components,
            'largest_connected_component_size': largest_cc_size
        }
        return stats

    def compute_centralities(self):
        """Compute Degree, Betweenness, and PageRank centralities on politician network."""
        print("Computing network centralities...", flush=True)
        # Degree Centrality
        deg_centrality = nx.degree_centrality(self.subG)
        
        # PageRank
        try:
            pagerank = nx.pagerank(self.subG, weight='weight')
        except Exception:
            pagerank = deg_centrality
            
        # Betweenness Centrality
        try:
            betweenness = nx.betweenness_centrality(self.subG, weight='weight', k=min(200, len(self.subG)))
        except Exception:
            betweenness = deg_centrality
            
        # Helper to sort and format top items
        def get_top_k(metric_dict, k=15):
            sorted_items = sorted(metric_dict.items(), key=lambda x: x[1], reverse=True)[:k]
            res = []
            for node_id, val in sorted_items:
                name = self.G.nodes[node_id].get('name', node_id)
                hometown = self.G.nodes[node_id].get('hometown', '')
                res.append({'id': node_id, 'name': name, 'score': round(val, 5), 'hometown': hometown})
            return res
            
        return {
            'top_degree': get_top_k(deg_centrality, 15),
            'top_pagerank': get_top_k(pagerank, 15),
            'top_betweenness': get_top_k(betweenness, 15)
        }

    def detect_communities(self):
        """Perform Louvain / Greedy modularity community detection."""
        print("Detecting network communities...", flush=True)
        try:
            from networkx.algorithms.community import greedy_modularity_communities
            communities = list(greedy_modularity_communities(self.subG))
            # Sort communities by size
            communities.sort(key=len, reverse=True)
            
            comm_summary = []
            for idx, comm in enumerate(communities[:8]):
                top_members = sorted(comm, key=lambda n: self.subG.degree[n], reverse=True)[:5]
                names = [self.G.nodes[n].get('name', n) for n in top_members]
                comm_summary.append({
                    'community_id': idx + 1,
                    'size': len(comm),
                    'key_figures': names
                })
            return comm_summary
        except Exception as e:
            print(f"Community detection error: {e}", flush=True)
            return []

    def analyze_cadre_mobility(self):
        """Analyze personnel rotation and career progression statistics."""
        grassroots_count = 0
        transfer_counts = Counter()
        promotions_count = 0
        
        for _, _, d in self.G.edges(data=True):
            r_type = d.get('type')
            if r_type == 'ROSE_FROM_GRASSROOTS':
                grassroots_count += 1
            elif r_type == 'TRANSFERRED_TO':
                direction = d.get('direction', 'TRANSFER')
                transfer_counts[direction] += 1
            elif r_type == 'PROMOTED_TO_CENTRAL':
                promotions_count += 1
                
        return {
            'grassroots_count': grassroots_count,
            'transfer_breakdown': dict(transfer_counts),
            'promotions_to_central': promotions_count
        }

    def generate_all_plots(self, stats, centralities, communities):
        """Generate high-resolution PNG charts for the report."""
        print(f"Generating charts into {self.fig_dir}...", flush=True)
        
        # 1. Degree Distribution Plot
        degrees = [d for _, d in self.G.degree()]
        plt.figure(figsize=(8, 5))
        plt.hist(degrees, bins=40, color='#1E88E5', edgecolor='black', alpha=0.8)
        plt.title('Degree Distribution of Vietnamese Politicians Graph', fontsize=13, fontweight='bold')
        plt.xlabel('Degree (k)', fontsize=11)
        plt.ylabel('Frequency', fontsize=11)
        plt.grid(axis='y', linestyle='--', alpha=0.7)
        plt.savefig(os.path.join(self.fig_dir, 'degree_distribution.png'), dpi=300)
        plt.close()

        # 2. Relation Types Breakdown Bar Chart
        rels = stats.get('relation_types', {})
        if rels:
            plt.figure(figsize=(10, 6))
            sorted_rels = sorted(rels.items(), key=lambda x: x[1], reverse=True)
            names = [r[0] for r in sorted_rels]
            counts = [r[1] for r in sorted_rels]
            colors = sns.color_palette('tab10', len(names))
            bars = plt.barh(names[::-1], counts[::-1], color=colors)
            plt.title('Distribution of 10+ Relationship Types in the Network', fontsize=13, fontweight='bold')
            plt.xlabel('Edge Count', fontsize=11)
            for bar in bars:
                plt.text(bar.get_width() + 10, bar.get_y() + bar.get_height()/4, f"{int(bar.get_width())}", fontsize=9)
            plt.grid(axis='x', linestyle='--', alpha=0.7)
            plt.savefig(os.path.join(self.fig_dir, 'relation_types_pie.png'), dpi=300)
            plt.close()

        # 3. Top PageRank Politicians Bar Chart
        top_pr = centralities.get('top_pagerank', [])[:10]
        if top_pr:
            plt.figure(figsize=(9, 5))
            names = [item['name'] for item in top_pr]
            scores = [item['score'] for item in top_pr]
            plt.barh(names[::-1], scores[::-1], color='#43A047')
            plt.title('Top 10 Influential Politicians by PageRank Centrality', fontsize=13, fontweight='bold')
            plt.xlabel('PageRank Score', fontsize=11)
            plt.grid(axis='x', linestyle='--', alpha=0.7)
            plt.savefig(os.path.join(self.fig_dir, 'top_pagerank.png'), dpi=300)
            plt.close()

        # 4. Top Betweenness Centrality Bar Chart
        top_bc = centralities.get('top_betweenness', [])[:10]
        if top_bc:
            plt.figure(figsize=(9, 5))
            names = [item['name'] for item in top_bc]
            scores = [item['score'] for item in top_bc]
            plt.barh(names[::-1], scores[::-1], color='#FB8C00')
            plt.title('Top 10 Bridge Politicians by Betweenness Centrality', fontsize=13, fontweight='bold')
            plt.xlabel('Betweenness Centrality', fontsize=11)
            plt.grid(axis='x', linestyle='--', alpha=0.7)
            plt.savefig(os.path.join(self.fig_dir, 'top_betweenness.png'), dpi=300)
            plt.close()

        # 5. Cadre Mobility & Rotation Breakdown
        mobility = self.analyze_cadre_mobility()
        tb = mobility.get('transfer_breakdown', {})
        if tb or mobility.get('grassroots_count'):
            plt.figure(figsize=(8, 5))
            labels = ['Trưởng thành từ cơ sở', 'Điều động lên TW', 'Luân chuyển TW -> Địa phương', 'Luân chuyển Địa phương -> Địa phương']
            vals = [
                mobility.get('grassroots_count', 0),
                mobility.get('promotions_to_central', 0),
                tb.get('CENTRAL_TO_LOCAL', 0),
                tb.get('LOCAL_TRANSFER', 0)
            ]
            plt.bar(labels, vals, color=['#8E24AA', '#D81B60', '#3949AB', '#00897B'])
            plt.title('Personnel Mobility and Rotation Patterns (Luân chuyển cán bộ)', fontsize=13, fontweight='bold')
            plt.ylabel('Detected Instances', fontsize=11)
            plt.xticks(rotation=15, ha='right')
            plt.grid(axis='y', linestyle='--', alpha=0.7)
            plt.savefig(os.path.join(self.fig_dir, 'rotation_flows.png'), dpi=300)
            plt.close()

        # 6. Community Sizes
        if communities:
            plt.figure(figsize=(8, 4))
            c_ids = [f"Nhóm {c['community_id']}" for c in communities]
            c_sizes = [c['size'] for c in communities]
            plt.bar(c_ids, c_sizes, color='#00ACC1')
            plt.title('Size of Detected Politician Cohorts / Communities', fontsize=13, fontweight='bold')
            plt.ylabel('Number of Members', fontsize=11)
            plt.grid(axis='y', linestyle='--', alpha=0.7)
            plt.savefig(os.path.join(self.fig_dir, 'community_distribution.png'), dpi=300)
            plt.close()

        print("Charts generated successfully!", flush=True)
