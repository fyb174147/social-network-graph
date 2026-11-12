# -*- coding: utf-8 -*-
"""
Graph Builder V3 for Approach 3: Infobox + NLP + Local LLM (qwen3:1.7b) Canonicalization.
Inherits helper methods from PoliticianGraphBuilder and adds an explicit
LLM canonicalization phase between extraction and graph assembly.
"""
from collections import defaultdict
from src.config import CENTRAL_AGENCIES
from src.infobox_parser import (
    parse_infobox, extract_province_from_text, extract_central_org_from_text,
    canonical_local_org, office_dedup_key
)
from src.graph_builder import PoliticianGraphBuilder
from src.llm_normalizer import (
    LocalLLMNormalizer, preclean_title, deterministic_expand
)


class LLMGraphBuilder(PoliticianGraphBuilder):
    def __init__(self, normalizer=None):
        super().__init__()
        self.normalizer = normalizer or LocalLLMNormalizer()
        self.canonicalization_stats = {}

    def build_from_raw_data(self, raw_pages):
        """Construct graph with Phase 1.5 Local LLM Canonicalization."""
        print(f"Building Approach 3 graph from {len(raw_pages)} politician articles...", flush=True)

        # --- PHASE 1: Infobox + NLP Extraction ---
        profiles = {}
        title_to_id = {}
        name_to_ids = defaultdict(list)
        co_leadership_index = defaultdict(list)
        raw_office_pool = []

        for title, item in raw_pages.items():
            wt = item.get('wikitext', '')
            if not wt or len(wt) < 200:
                continue

            info = parse_infobox(wt, title)
            norm_name = self.normalize_name(info['name'] or title)
            if not norm_name or len(norm_name) < 3:
                continue

            pol_id = self.make_pol_id(title)
            title_to_id[title.strip().lower()] = pol_id
            if pol_id not in name_to_ids[norm_name.lower()]:
                name_to_ids[norm_name.lower()].append(pol_id)

            for off in info.get('offices', []):
                if off.get('office'):
                    raw_office_pool.append(off['office'])

            career_sections = self.nlp.extract_career_text(wt)
            all_events = []
            for _, sec_text in career_sections:
                all_events.extend(self.nlp.parse_career_events(sec_text))

            grassroots = self.nlp.extract_grassroots_roots(norm_name, all_events)
            transfers = self.nlp.extract_transfers(norm_name, all_events)
            promotions = self.nlp.extract_promotions_to_central(norm_name, all_events)
            delegations = self.nlp.extract_delegations(norm_name, wt)

            cats = item.get('categories', [])
            party_terms_set = []
            for cat in cats:
                t_label = None
                if 'khóa XIII' in cat:
                    t_label = 'Khóa XIII (2021–2026)'
                elif 'khóa XII' in cat:
                    t_label = 'Khóa XII (2016–2021)'
                elif 'khóa XI' in cat:
                    t_label = 'Khóa XI (2011–2016)'
                elif 'khóa X' in cat:
                    t_label = 'Khóa X (2006–2011)'
                elif 'Bộ Chính trị' in cat:
                    t_label = 'Ủy viên Bộ Chính trị'
                if t_label and t_label not in party_terms_set:
                    party_terms_set.append(t_label)

            profiles[pol_id] = {
                'id': pol_id,
                'name': norm_name,
                'raw_title': title,
                'info': info,
                'events': all_events,
                'grassroots': grassroots,
                'transfers': transfers,
                'promotions': promotions,
                'delegations': delegations,
                'party_terms': party_terms_set
            }

            for term in party_terms_set:
                if pol_id not in co_leadership_index[term]:
                    co_leadership_index[term].append(pol_id)

        print(f"Parsed {len(profiles)} valid politician profiles.", flush=True)

        # --- PHASE 1.5: Local LLM Canonicalization (qwen3:1.7b) ---
        office_map = self.normalizer.canonicalize_positions(raw_office_pool, verbose=True)
        self.canonicalization_stats = dict(self.normalizer.stats)

        for p in profiles.values():
            for off in p['info'].get('offices', []):
                raw_o = (off.get('office') or '').strip()
                if raw_o:
                    canon_o = office_map.get(raw_o, raw_o)
                    off['raw_office'] = raw_o
                    off['office'] = canon_o
            for gr in p['grassroots']:
                gu = gr.get('grassroots_unit', '')
                if gu:
                    gr['grassroots_unit'] = deterministic_expand(preclean_title(gu))

        # --- PHASE 2: Knowledge Graph Assembly ---
        for pol_id, p in profiles.items():
            info = p['info']
            self.G.add_node(
                pol_id,
                label="Politician",
                name=p['name'],
                birth_year=info.get('birth_year') or 0,
                hometown=info.get('hometown') or "Việt Nam",
                education=info.get('education') or "Đại học",
                party="Đảng Cộng sản Việt Nam"
            )
            self.politician_nodes[pol_id] = p['name']

        seen_rel_edges = set()
        org_tenures = defaultdict(list)
        central_set_low = {c.lower() for c in CENTRAL_AGENCIES}

        def add_edge_once(u, v, r_type, dedup_key="", **attrs):
            sig = (u, v, r_type, dedup_key)
            if sig in seen_rel_edges:
                return False
            seen_rel_edges.add(sig)
            self.G.add_edge(u, v, type=r_type, **attrs)
            return True

        for pol_id, p in profiles.items():
            info = p['info']

            ht = info.get('hometown')
            if ht:
                prov = extract_province_from_text(ht)
                if prov:
                    loc_id = f"loc_{prov.replace(' ', '_').lower()}"
                    if loc_id not in self.G:
                        self.G.add_node(loc_id, label="Location", name=prov, type="Province")
                        self.loc_nodes[loc_id] = prov
                    add_edge_once(pol_id, loc_id, "NATIVE_OF", weight=1.0)

            for off in info.get('offices', []):
                off_name = off.get('office', '')
                if not off_name or len(off_name) < 3:
                    continue

                s_yr = off.get('start_year') or 0
                e_yr = off.get('end_year') or 0

                pos_id = self.make_pos_id(off_name)
                if pos_id not in self.G:
                    self.G.add_node(pos_id, label="Position", name=off_name[:150])
                    self.pos_nodes[pos_id] = off_name
                add_edge_once(
                    pol_id, pos_id, "HELD_POSITION", f"{s_yr}_{e_yr}",
                    start_year=s_yr, end_year=e_yr, weight=1.0
                )

                org_name = extract_central_org_from_text(off_name)
                prov_name = extract_province_from_text(off_name)
                off_key = office_dedup_key(off_name)

                target_org = org_name or canonical_local_org(prov_name)
                if target_org:
                    org_id = f"org_{target_org.replace(' ', '_').lower()}"
                    is_cent = bool(org_name)
                    if org_id not in self.G:
                        self.G.add_node(org_id, label="Organization", name=target_org, is_central=is_cent)
                        self.org_nodes[org_id] = target_org
                    add_edge_once(
                        pol_id, org_id, "BELONGS_TO_ORG", f"{off_key}_{s_yr}",
                        role=off_name[:120], start_year=s_yr, end_year=e_yr, weight=1.0
                    )
                    is_plain_mp = (
                        target_org == "Quốc hội"
                        and "đại biểu" in off_name.lower()
                        and not any(r in off_name.lower() for r in ("chủ tịch", "ủy viên thường vụ", "chủ nhiệm", "trưởng ban", "tổng thư ký"))
                    )
                    if s_yr >= 1975 and not is_plain_mp:
                        eff_end = e_yr if e_yr >= s_yr else (2026 if s_yr >= 2016 else s_yr + 4)
                        org_tenures[org_id].append((pol_id, s_yr, eff_end, target_org))

                off_label = off_name[:120]
                for p_cand in (off.get('predecessor_links') or []):
                    cand_id = self.resolve_politician_id(p_cand, title_to_id, name_to_ids)
                    if cand_id and cand_id in profiles and cand_id != pol_id:
                        add_edge_once(cand_id, pol_id, "PREDECESSOR_OF", off_key, role=off_label, office=off_label, weight=1.5)
                        add_edge_once(pol_id, cand_id, "SUCCESSOR_OF", off_key, role=off_label, office=off_label, weight=1.5)

                for s_cand in (off.get('successor_links') or []):
                    cand_id = self.resolve_politician_id(s_cand, title_to_id, name_to_ids)
                    if cand_id and cand_id in profiles and cand_id != pol_id:
                        add_edge_once(pol_id, cand_id, "PREDECESSOR_OF", off_key, role=off_label, office=off_label, weight=1.5)
                        add_edge_once(cand_id, pol_id, "SUCCESSOR_OF", off_key, role=off_label, office=off_label, weight=1.5)

                for dep in off.get('deputies', []):
                    dep_id = self.resolve_politician_id(dep, title_to_id, name_to_ids)
                    if dep_id and dep_id in profiles and dep_id != pol_id:
                        add_edge_once(dep_id, pol_id, "DEPUTY_OF", off_key, role=off_label, superior_role=off_label, weight=1.2)

                for sup in off.get('superiors', []):
                    sup_id = self.resolve_politician_id(sup, title_to_id, name_to_ids)
                    if sup_id and sup_id in profiles and sup_id != pol_id:
                        add_edge_once(pol_id, sup_id, "DEPUTY_OF", off_key, role=off_label, superior_role=off_label, weight=1.2)

            for gr in p['grassroots']:
                g_unit = gr['grassroots_unit']
                prov = gr.get('province')
                g_id = f"grassroots_{g_unit.replace(' ', '_').lower()}"
                if g_id not in self.G:
                    self.G.add_node(g_id, label="Organization", name=g_unit, is_central=False, org_type="Grassroots", province=prov or "Địa phương")
                    self.org_nodes[g_id] = g_unit
                add_edge_once(
                    pol_id, g_id, "ROSE_FROM_GRASSROOTS", g_unit,
                    role=gr.get('role', 'Cán bộ cơ sở'),
                    start_year=gr.get('year') or 0,
                    evidence=gr.get('evidence', '')[:120],
                    weight=1.5
                )

            for tr in p['transfers']:
                target = tr['target']
                tr_id = f"org_{target.replace(' ', '_').lower()}"
                is_cent = target.lower() in central_set_low
                if tr_id not in self.G:
                    self.G.add_node(tr_id, label="Organization", name=target, is_central=is_cent, org_type="Central" if is_cent else "Local")
                    self.org_nodes[tr_id] = target
                add_edge_once(
                    pol_id, tr_id, "TRANSFERRED_TO", f"{tr.get('direction')}_{tr.get('year') or 0}",
                    direction=tr.get('direction', 'TRANSFER'),
                    start_year=tr.get('year') or 0,
                    evidence=tr.get('evidence', '')[:120],
                    weight=1.5
                )

            for pr in p['promotions']:
                c_org = pr['to_central_org']
                c_id = f"org_{c_org.replace(' ', '_').lower()}"
                if c_id not in self.G:
                    self.G.add_node(c_id, label="Organization", name=c_org, is_central=True)
                    self.org_nodes[c_id] = c_org
                add_edge_once(
                    pol_id, c_id, "PROMOTED_TO_CENTRAL", f"{c_org}_{pr.get('year') or 0}",
                    from_province=pr.get('from_province', 'Địa phương'),
                    start_year=pr.get('year') or 0,
                    evidence=pr.get('evidence', '')[:120],
                    weight=2.0
                )

            for dlg in p['delegations']:
                prov = dlg['province']
                loc_id = f"loc_{prov.replace(' ', '_').lower()}"
                if loc_id not in self.G:
                    self.G.add_node(loc_id, label="Location", name=prov, type="Province")
                    self.loc_nodes[loc_id] = prov
                add_edge_once(
                    pol_id, loc_id, "DELEGATE_OF", dlg.get('term', 'Quốc hội'),
                    term=dlg.get('term', 'Quốc hội'),
                    weight=1.0
                )

            for t_name in p['party_terms']:
                term_id = f"term_{t_name.replace(' ', '_').lower()}"
                if term_id not in self.G:
                    self.G.add_node(term_id, label="Term", name=t_name)
                    self.term_nodes[term_id] = t_name
                add_edge_once(
                    pol_id, term_id, "CENTRAL_COMMITTEE_MEMBER", t_name,
                    term=t_name,
                    weight=1.2
                )

        # Rel 11: CO_LEADER
        print("Constructing CO_LEADER network edges...", flush=True)
        politburo_infobox_pairs = set()

        for org_id, records in org_tenures.items():
            by_pol = {}
            org_name = records[0][3]
            for pid, s_y, e_y, _ in records:
                if pid not in by_pol:
                    by_pol[pid] = [s_y, e_y]
                else:
                    by_pol[pid][0] = min(by_pol[pid][0], s_y)
                    by_pol[pid][1] = max(by_pol[pid][1], e_y)
            items = sorted([(pid, span[0], span[1]) for pid, span in by_pol.items()], key=lambda x: x[1])
            for i in range(len(items)):
                p1, s1, e1 = items[i]
                links_added = 0
                for j in range(i + 1, len(items)):
                    p2, s2, e2 = items[j]
                    if s2 > e1:
                        break
                    ov_start, ov_end = max(s1, s2), min(e1, e2)
                    if ov_start <= ov_end:
                        t_label = f"{org_name} ({ov_start}–{ov_end})"
                        add_edge_once(p1, p2, "CO_LEADER", org_id, term=t_label, start_year=ov_start, end_year=ov_end, weight=1.2)
                        add_edge_once(p2, p1, "CO_LEADER", org_id, term=t_label, start_year=ov_start, end_year=ov_end, weight=1.2)
                        if org_name == "Bộ Chính trị":
                            politburo_infobox_pairs.add((p1, p2))
                            politburo_infobox_pairs.add((p2, p1))
                        links_added += 1
                        if len(items) > 40 and links_added >= 10:
                            break

        for term, members in co_leadership_index.items():
            if len(members) > 1:
                max_span = len(members) if len(members) <= 25 else 15
                for i in range(len(members)):
                    p1 = members[i]
                    for j in range(i + 1, min(i + max_span, len(members))):
                        p2 = members[j]
                        if p1 != p2:
                            if term == 'Ủy viên Bộ Chính trị' and (p1, p2) in politburo_infobox_pairs:
                                continue
                            add_edge_once(p1, p2, "CO_LEADER", term, term=term, weight=1.0)
                            add_edge_once(p2, p1, "CO_LEADER", term, term=term, weight=1.0)

        print("Approach 3 graph construction completed!", flush=True)
        print(
            f"Total nodes: {self.G.number_of_nodes()} "
            f"(Politicians: {len(self.politician_nodes)}, Orgs: {len(self.org_nodes)}, "
            f"Positions: {len(self.pos_nodes)}, Locations: {len(self.loc_nodes)}, Terms: {len(self.term_nodes)})",
            flush=True
        )
        print(f"Total edges: {self.G.number_of_edges()}", flush=True)

        return self.G
