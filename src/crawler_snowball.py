# -*- coding: utf-8 -*-
"""
Ý tưởng 2: Hybrid Snowball BFS Crawler (Thu thập loang theo chiều rộng từ trang gốc).
Quy trình:
  1. Bắt đầu từ các trang gốc bộ máy chính quyền VN (Chính phủ VN, Bộ Chính trị, BCH TW, Quốc hội...).
  2. Duyệt đồ thị theo chiều rộng (BFS) qua các cạnh liên kết (Tiền nhiệm, Kế nhiệm, Cấp phó, Đồng nhiệm kỳ).
  3. Bộ lọc chống trôi chủ đề (Anti-Drift Filter): loại bỏ chính khách nước ngoài, trang chức vụ/tổ chức, ngày tháng.
  4. Bộ đếm cnt dừng khi đạt >= 2,000 chính khách hợp lệ; có cơ chế Fallback Refill nếu BFS bị cạn hàng đợi.
"""
import os
import sys
import re
import json
import time
import requests
from collections import deque

sys.stdout.reconfigure(encoding='utf-8')

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from src.infobox_parser import extract_wiki_links
from src.config import PROVINCES

USER_AGENT = 'VietnamesePoliticiansResearch/2.0 (Hybrid Snowball BFS; contact: student2026@university.edu.vn)'
WIKI_API_URL = 'https://vi.wikipedia.org/w/api.php'

SEED_INSTITUTION_PAGES = [
    "Chính phủ Việt Nam",
    "Bộ Chính trị Ban Chấp hành Trung ương Đảng Cộng sản Việt Nam",
    "Ban Chấp hành Trung ương Đảng Cộng sản Việt Nam khóa XIII",
    "Ban Chấp hành Trung ương Đảng Cộng sản Việt Nam khóa XII",
    "Ban Chấp hành Trung ương Đảng Cộng sản Việt Nam khóa XI",
    "Danh sách Đại biểu Quốc hội Việt Nam khóa XV",
    "Danh sách Đại biểu Quốc hội Việt Nam khóa XIV",
    "Danh sách Đại biểu Quốc hội Việt Nam khóa XIII",
    "Phạm Minh Chính",
    "Tô Lâm",
    "Nguyễn Phú Trọng",
    "Lương Cường",
    "Trần Thanh Mẫn",
    "Vương Đình Huệ"
]

NON_PERSON_PREFIXES = (
    "Danh sách", "Bản mẫu:", "Thể loại:", "Tập tin:", "File:", "Chế định",
    "Bầu cử", "Bộ trưởng ", "Thứ trưởng ", "Chủ tịch ", "Thủ tướng ", "Phó Thủ tướng",
    "Tổng Bí thư ", "Bí thư ", "Ủy ban ", "Ban Chấp hành", "Ban Bí thư",
    "Bộ Chính trị", "Quốc hội ", "Chính phủ ", "Đảng ", "Đại hội ",
    "Tỉnh ", "Thành phố ", "Quận ", "Huyện ", "Xã ", "Phường ",
    "Hiến pháp", "Văn phòng ", "Bộ ", "Hội đồng ", "Tòa án ", "Viện kiểm sát",
    "Quân khu ", "Quân đoàn ", "Sư đoàn ", "Công an ", "Mặt trận ",
    "Huân chương", "Huy chương", "Giải thưởng", "Chiến dịch", "Trận ", "Năm ", "Tháng "
)

VN_POLITICIAN_CAT_KEYWORDS = [
    "chính khách việt nam", "chính trị gia việt nam", "đại biểu quốc hội việt nam",
    "ủy viên ban chấp hành trung ương", "bộ trưởng việt nam", "thứ trưởng việt nam",
    "bí thư tỉnh ủy", "bí thư thành ủy", "chủ tịch ủy ban nhân dân", "chủ tịch hội đồng nhân dân",
    "tướng lĩnh quân đội nhân dân việt nam", "tướng lĩnh công an nhân dân việt nam",
    "thủ tướng việt nam", "phó thủ tướng việt nam", "chủ tịch nước việt nam", "chủ tịch quốc hội việt nam",
    "tổng bí thư", "ủy viên bộ chính trị"
]

FOREIGN_STOP_KEYWORDS = [
    "chính khách hoa kỳ", "chính khách trung quốc", "chính khách nga", "chính khách pháp",
    "chính khách anh", "chính khách nhật bản", "chính khách hàn quốc", "chính khách đức",
    "thủ tướng thái lan", "tổng thống hoa kỳ", "tổng thống mỹ", "tổng thống nga",
    "chủ tịch trung quốc", "ca sĩ việt nam", "diễn viên việt nam", "cầu thủ bóng đá",
    "huấn luyện viên", "nhà văn việt nam", "nhà thơ việt nam", "hoa hậu"
]


class HybridSnowballCrawler:
    def __init__(self, output_raw_dir, local_cache_file=None, fallback_titles_file=None):
        self.output_raw_dir = output_raw_dir
        os.makedirs(self.output_raw_dir, exist_ok=True)
        self.pages_file = os.path.join(self.output_raw_dir, "raw_politicians_snowball.json")
        self.trace_file = os.path.join(self.output_raw_dir, "snowball_trace.json")

        self.session = requests.Session()
        self.session.headers.update({'User-Agent': USER_AGENT})

        # Load local cache from Approach 1 if available to avoid redundant Wikipedia API hits
        self.local_cache = {}
        if local_cache_file and os.path.exists(local_cache_file):
            try:
                with open(local_cache_file, 'r', encoding='utf-8') as f:
                    self.local_cache = json.load(f)
                print(f"Loaded {len(self.local_cache)} pages into local cache for fast BFS lookup.", flush=True)
            except Exception as e:
                print(f"Warning loading local cache: {e}", flush=True)

        self.fallback_titles = []
        if fallback_titles_file and os.path.exists(fallback_titles_file):
            with open(fallback_titles_file, 'r', encoding='utf-8') as f:
                self.fallback_titles = json.load(f)

        self.provinces_set = set(p.lower() for p in PROVINCES)

    def looks_like_vietnamese_name(self, title):
        """Quick heuristic filter before querying Wikipedia API to avoid obvious non-person links."""
        if not title or len(title) < 4 or len(title) > 65:
            return False
        if any(char.isdigit() for char in title):
            # Allow disambiguation like "Trần Hồng Hà (chính khách)" but reject dates/years
            if not re.search(r'\(.*\)$', title):
                return False
        if title.startswith(NON_PERSON_PREFIXES):
            return False
        if ':' in title or '/' in title:
            return False
        clean_t = title.split('(')[0].strip()
        if clean_t.lower() in self.provinces_set:
            return False
        words = clean_t.split()
        if not (2 <= len(words) <= 5):
            return False
        # Vietnamese names typically have capitalized words
        if not all(w[0].isupper() for w in words if w):
            return False
        return True

    def is_disambiguation_page(self, title, wikitext, categories):
        """Detect Wikipedia disambiguation (trang định hướng) pages."""
        t_low = title.lower()
        if "định hướng" in t_low or "disambiguation" in t_low:
            return True
        cats_lower = " | ".join(categories).lower()
        if "trang định hướng" in cats_lower or "disambiguation" in cats_lower:
            return True
        wt_head = wikitext[:1200].lower()
        if any(m in wt_head for m in [
            "{{trang định hướng", "{{định hướng", "{{disambig",
            "là một tên người việt", "là tên người việt", "nhân vật này có thể là:"
        ]):
            return True
        return False

    def is_valid_vn_politician(self, title, wikitext, categories):
        """Anti-Drift Filter: verify the fetched article is actually a Vietnamese politician."""
        if not wikitext or len(wikitext) < 200:
            return False
        if title.startswith(NON_PERSON_PREFIXES):
            return False
        if self.is_disambiguation_page(title, wikitext, categories):
            return False

        cats_lower = " | ".join(categories).lower()
        wt_head = wikitext[:2500].lower()

        # Check explicit non-politician/foreign signals
        if any(fk in cats_lower for fk in FOREIGN_STOP_KEYWORDS):
            return False

        # Must match Vietnamese politician categories or infobox + Vietnam context
        has_pol_cat = any(k in cats_lower for k in VN_POLITICIAN_CAT_KEYWORDS)
        has_pol_infobox = any(tpl in wt_head for tpl in [
            "{{thông tin viên chức", "{{thông tin chính khách", "{{viên chức",
            "đại biểu quốc hội", "ủy viên ban chấp hành trung ương", "bộ trưởng", "bí thư tỉnh ủy", "chủ tịch ủy ban nhân dân"
        ])
        has_vn_context = ("việt nam" in cats_lower) or ("việt nam" in wt_head)

        return (has_pol_cat or has_pol_infobox) and has_vn_context

    def extract_candidate_neighbors(self, wikitext):
        """Extract person2 link candidates from Infobox & article text."""
        candidates = []
        # 1. Prioritize links in Infobox / succession fields and career sections
        raw_links = extract_wiki_links(wikitext)
        seen = set()
        for link in raw_links:
            link_clean = link.split('#')[0].strip()
            if link_clean not in seen and self.looks_like_vietnamese_name(link_clean):
                seen.add(link_clean)
                candidates.append(link_clean)
        return candidates

    def fetch_pages_batch(self, titles_batch):
        """Fetch pages from local cache first, then Wikipedia API for missing ones."""
        results = {}
        to_fetch_online = []

        for t in titles_batch:
            if t in self.local_cache:
                results[t] = self.local_cache[t]
            else:
                to_fetch_online.append(t)

        if to_fetch_online:
            pipe_titles = "|".join(to_fetch_online)
            params = {
                'action': 'query',
                'prop': 'revisions|categories',
                'rvslots': '*',
                'rvprop': 'content',
                'cllimit': 50,
                'redirects': 1,
                'titles': pipe_titles,
                'format': 'json'
            }
            for attempt in range(3):
                try:
                    resp = self.session.post(WIKI_API_URL, data=params, timeout=25)
                    if resp.status_code == 429:
                        print("Rate limited (429), sleeping 5s...", flush=True)
                        time.sleep(5)
                        continue
                    if resp.status_code == 200:
                        data = resp.json()
                        pages_dict = data.get('query', {}).get('pages', {})
                        for pid, p in pages_dict.items():
                            if int(pid) < 0:
                                continue
                            t_actual = p.get('title')
                            revs = p.get('revisions', [])
                            content = revs[0].get('slots', {}).get('main', {}).get('*', '') if revs else ''
                            cats = [c.get('title', '') for c in p.get('categories', [])]
                            results[t_actual] = {
                                'pageid': p.get('pageid'),
                                'title': t_actual,
                                'categories': cats,
                                'wikitext': content
                            }
                        break
                except Exception as e:
                    print(f"API fetch error (attempt {attempt+1}): {e}", flush=True)
                    time.sleep(2)
            time.sleep(0.35)

        return results

    def crawl_snowball_bfs(self, target_count=2050):
        """Execute Hybrid Snowball BFS until target_count valid politicians are collected."""
        if os.path.exists(self.pages_file):
            with open(self.pages_file, 'r', encoding='utf-8') as f:
                existing = json.load(f)
            # Load existing snowball pages into local_cache so valid pages are reused without re-fetching
            for k, v in existing.items():
                if k not in self.local_cache:
                    self.local_cache[k] = v

            if os.path.exists(self.trace_file):
                with open(self.trace_file, 'r', encoding='utf-8') as tf:
                    trace = json.load(tf)
                valid_existing = {
                    k: v for k, v in existing.items()
                    if self.is_valid_vn_politician(k, v.get('wikitext', ''), v.get('categories', []))
                }
                if len(valid_existing) >= target_count and len(valid_existing) == len(existing):
                    print(f"Loaded {len(valid_existing)} validated Snowball BFS pages from cache.", flush=True)
                    return valid_existing, trace

        print(f"=== BẮT ĐẦU HYBRID SNOWBALL BFS CRAWLER (Mục tiêu: {target_count} chính khách) ===", flush=True)

        accepted_A = {}         # Tập A các chính khách hợp lệ
        visited_titles = set()  # Tập các tiêu đề đã từng đưa vào hàng đợi / kiểm tra
        queue = deque()         # Hàng đợi BFS: (title, depth, discovered_from)

        stats = {
            'seed_pages_used': len(SEED_INSTITUTION_PAGES),
            'total_checked': 0,
            'topic_drift_filtered': 0,
            'disambig_filtered': 0,
            'pure_bfs_count': 0,
            'fallback_refill_count': 0,
            'max_bfs_depth': 0,
            'depth_distribution': {}
        }

        # Step 1: Fetch Seed Institution Pages
        print(f"[Seed] Đang cào {len(SEED_INSTITUTION_PAGES)} trang gốc bộ máy nhà nước...", flush=True)
        seed_data = self.fetch_pages_batch(SEED_INSTITUTION_PAGES)
        for s_title, s_page in seed_data.items():
            wt = s_page.get('wikitext', '')
            cats = s_page.get('categories', [])
            if self.is_valid_vn_politician(s_title, wt, cats):
                # Seed itself is a politician (e.g., Phạm Minh Chính, Tô Lâm)
                visited_titles.add(s_title)
                accepted_A[s_title] = s_page
                stats['pure_bfs_count'] += 1
                stats['depth_distribution']['0'] = stats['depth_distribution'].get('0', 0) + 1

            cands = self.extract_candidate_neighbors(wt)
            for c in cands:
                if c not in visited_titles:
                    visited_titles.add(c)
                    queue.append((c, 1, s_title))

        print(f"[Seed] Khởi tạo hàng đợi Q = {len(queue)} ứng viên từ các trang gốc. (cnt = {len(accepted_A)})", flush=True)

        # Step 2: BFS Snowball Loop
        batch_size = 40
        used_fallback = False
        fallback_idx = 0

        while len(accepted_A) < target_count:
            if not queue:
                if not used_fallback:
                    stats['pure_bfs_count'] = len(accepted_A)
                    used_fallback = True
                    print(f"\n[Fallback] Hàng đợi BFS thuần túy dừng ở {len(accepted_A)} chính khách. Kích hoạt bơm thêm hạt giống...", flush=True)
                # Refill queue from fallback titles
                added = 0
                while fallback_idx < len(self.fallback_titles) and added < 200:
                    ft = self.fallback_titles[fallback_idx]
                    fallback_idx += 1
                    if ft not in visited_titles and self.looks_like_vietnamese_name(ft):
                        visited_titles.add(ft)
                        queue.append((ft, 99, "Fallback_Category_Refill"))
                        added += 1
                if added == 0:
                    print("Hết nguồn ứng viên bổ sung. Dừng vòng lặp.", flush=True)
                    break

            batch_items = []
            while queue and len(batch_items) < batch_size:
                batch_items.append(queue.popleft())

            batch_titles = [item[0] for item in batch_items]
            depth_map = {item[0]: item[1] for item in batch_items}

            fetched = self.fetch_pages_batch(batch_titles)
            stats['total_checked'] += len(batch_titles)

            for title, page_obj in fetched.items():
                if len(accepted_A) >= target_count:
                    break
                if title in accepted_A:
                    continue

                wt = page_obj.get('wikitext', '')
                cats = page_obj.get('categories', [])
                depth = depth_map.get(title, 1)

                if self.is_disambiguation_page(title, wt, cats):
                    stats['disambig_filtered'] += 1
                    stats['topic_drift_filtered'] += 1
                    # Bridge through disambiguation page to actual politician links (e.g. "Tên (chính khách)")
                    for nb in self.extract_candidate_neighbors(wt):
                        if nb not in visited_titles:
                            visited_titles.add(nb)
                            queue.append((nb, depth, title))
                    continue

                if self.is_valid_vn_politician(title, wt, cats):
                    accepted_A[title] = page_obj
                    d_key = str(depth)
                    stats['depth_distribution'][d_key] = stats['depth_distribution'].get(d_key, 0) + 1
                    if depth < 99:
                        stats['max_bfs_depth'] = max(stats['max_bfs_depth'], depth)
                    else:
                        stats['fallback_refill_count'] += 1

                    # Snowball Expansion: Extract person2 links and enqueue
                    neighbors = self.extract_candidate_neighbors(wt)
                    for nb in neighbors:
                        if nb not in visited_titles:
                            visited_titles.add(nb)
                            queue.append((nb, depth + 1 if depth < 99 else 99, title))
                else:
                    stats['topic_drift_filtered'] += 1

            print(
                f"  -> Đã thu thập cnt = {len(accepted_A)}/{target_count} | "
                f"Hàng đợi Q = {len(queue)} | Đã lọc nhiễu = {stats['topic_drift_filtered']} "
                f"(định hướng = {stats['disambig_filtered']})",
                flush=True
            )

        if not used_fallback:
            stats['pure_bfs_count'] = len(accepted_A)

        print(f"\n✔ Hoàn tất Hybrid Snowball BFS! Tổng chính khách hợp lệ: {len(accepted_A)}", flush=True)
        print(f"  - Thuần BFS loang được: {stats['pure_bfs_count']}", flush=True)
        print(f"  - Bộ lọc chống trôi chủ đề đã loại: {stats['topic_drift_filtered']} trang nhiễu (trong đó {stats['disambig_filtered']} trang định hướng)", flush=True)

        with open(self.pages_file, 'w', encoding='utf-8') as f:
            json.dump(accepted_A, f, ensure_ascii=False)
        with open(self.trace_file, 'w', encoding='utf-8') as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)

        return accepted_A, stats
