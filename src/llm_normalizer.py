# -*- coding: utf-8 -*-
"""
Local LLM Entity Canonicalizer for Approach 3 (Hybrid NLP + Ollama qwen3:1.7b).
Combines deterministic pre-cleaning, strict skeleton clustering, batched Ollama
canonicalization (with thinking disabled for fast JSON output), structural safety
guardrails, and a persistent disk cache.
"""
import os
import re
import json
import time
import requests
from collections import defaultdict
from src.config import PROVINCES, PROVINCE_CANONICAL

OLLAMA_CHAT_URL = "http://localhost:11434/api/chat"
DEFAULT_MODEL = "qwen3.5-custom:latest"

# Known safe administrative words allowed ONLY when expanding abbreviations (no role/rank words)
SAFE_EXPANSION_WORDS = {
    "ủy", "ban", "nhân", "dân", "hội", "đồng", "đại", "biểu", "quốc",
    "thành", "phố", "hồ", "chí", "minh", "trung", "ương", "chấp", "hành",
    "việt", "nam", "đảng", "cộng", "sản", "chính", "trị", "kiểm", "tra",
    "mặt", "trận", "tổ", "đoàn", "thanh", "niên", "quản", "tổng", "công",
    "ty", "cổ", "phần", "liên", "hiệp", "phụ", "nữ", "lao", "động"
}

NOISY_CANDIDATE_PATTERN = re.compile(
    r'\(|\b(?:CHXHCN|CHXHCNVN|BCH|ĐCSVN|UBKT|BCT|MTTQ|ĐTNCSHCM|HĐBT|HĐQT|TCT|CP|VN|Phụ trách|Cộng hòa xã hội chủ nghĩa Việt Nam)\b|;|\/',
    re.IGNORECASE
)

ROMAN_TERM_PATTERN = re.compile(r'\b(XVII|XVI|XV|XIV|XIII|XII|XI|IX|X|VIII|VII|VI|IV|V|III|II|I)\b')


def preclean_title(text):
    """Strip wiki syntax residue, fix common Vietnamese typos, and remove status/ordinal notes."""
    if not text:
        return ""
    s = re.sub(r'[\{\}\[\]]+', ' ', str(text))
    for old_v, new_v in (
        ('tòan', 'toàn'), ('Tòan', 'Toàn'),
        ('uỷ', 'ủy'), ('Uỷ', 'Ủy'),
        ('uý', 'úy'), ('Uý', 'Úy'),
        ('hoà', 'hòa'), ('Hoà', 'Hòa'),
        ('toà', 'tòa'), ('Toà', 'Tòa'),
        ('khoá', 'khóa'), ('Khoá', 'Khóa'),
        ('xoá', 'xóa'), ('Xoá', 'Xóa'),
    ):
        s = s.replace(old_v, new_v)

    s = re.sub(r'\bnước\s+nước\b', 'nước', s, flags=re.IGNORECASE)
    # Remove closed status / assignment / ordinal parenthetical annotations
    s = re.sub(
        r'\s*\([^)]*(?:lần\s*\d|bãi nhiệm|cách chức|xóa tư cách|thôi việc|từ trần|qua đời|tạm quyền|quyền|khuyết|miễn nhiệm|kỷ luật|thôi chức|nghỉ hưu|phụ trách|nhiệm kỳ|nay là|\d{4})[^)]*\)',
        '', s, flags=re.IGNORECASE
    )
    # Remove unclosed truncated trailing notes (e.g. "(Phụ trách Khoa học, Công nghệ,...")
    s = re.sub(r'\s*\((?:Phụ trách|Đã bị|lần\s*\d).*$', '', s, flags=re.IGNORECASE)
    # Remove trailing unparenthesized "Phụ trách ..." appended from wiki <small>/<br/>
    s = re.sub(
        r'^((?:Phó\s+)?(?:Thủ tướng Chính phủ|Chủ tịch Quốc hội|Chủ tịch nước|Bộ trưởng[^,;]*))\s+Phụ trách\b.*$',
        r'\1', s, flags=re.IGNORECASE
    )
    s = re.sub(r'\s*[-–—]\s*', ' - ', s)
    return re.sub(r'\s+', ' ', s).strip(' .;,:-–—')


def deterministic_expand(text):
    """Expand standard Vietnamese administrative abbreviations and fix phrasing noise."""
    if not text:
        return ""
    s = text
    s = re.sub(r'\bUBND\b', 'Ủy ban nhân dân', s)
    s = re.sub(r'\bHĐND\b', 'Hội đồng nhân dân', s)
    s = re.sub(r'\bĐBQH\b', 'Đại biểu Quốc hội', s)
    s = re.sub(r'\bTPHCM\b|\bTP\.?\s*HCM\b', 'Thành phố Hồ Chí Minh', s, flags=re.IGNORECASE)
    s = re.sub(r'\b(?:TP|Tp)\.?\s*HN\b', 'Thành phố Hà Nội', s)
    s = re.sub(r'\b(?:TP|Tp)\.?\s+(?=[A-ZÀ-ỸĐ])', 'Thành phố ', s)
    s = re.sub(r'\bTW\b', 'Trung ương', s)
    s = re.sub(
        r'\b(Chủ tịch nước|Thủ tướng Chính phủ|Phó Thủ tướng Chính phủ|Chủ tịch Quốc hội|Tổng Bí thư)\s+(?:nước\s+)?(?:Cộng hòa xã hội chủ nghĩa Việt Nam|CHXHCNVN|Đảng Cộng sản Việt Nam)\b',
        r'\1', s, flags=re.IGNORECASE
    )
    s = re.sub(r'\bTỉnh ủy tỉnh\b', 'Tỉnh ủy', s, flags=re.IGNORECASE)
    s = re.sub(r'\bThành ủy thành phố\b', 'Thành ủy', s, flags=re.IGNORECASE)
    s = re.sub(r'\bKhóa\b', 'khóa', s)
    s = re.sub(r'\s*,\s*(?=[IVX]+\b)', ', ', s)
    return re.sub(r'\s+', ' ', s).strip(' .;,:-–—')


def strict_skeleton(text):
    """Build a canonical grouping key so synonymous spelling variants cluster in the same LLM batch."""
    k = deterministic_expand(preclean_title(text)).lower()
    k = re.sub(r'\bban chấp hành trung ương đảng\b', 'trung ương đảng', k)
    k = re.sub(
        r'\b(?:nước\s+)?(?:cộng hòa xã hội chủ nghĩa việt nam|chxhcnvn|chxhcn việt nam|đảng cộng sản việt nam|việt nam)\b',
        ' ', k
    )
    k = re.sub(r'[-–—,:;.]', ' ', k)
    return re.sub(r'\s+', ' ', k).strip()


def _extract_province_canonical(text):
    if not text:
        return None
    for prov in PROVINCES:
        if re.search(r'\b' + re.escape(prov) + r'\b', text, re.IGNORECASE):
            return PROVINCE_CANONICAL.get(prov, prov)
    return None


def validate_canonical_mapping(source_text, candidate_text):
    """
    Safety guardrail ensuring LLM canonicalization never alters seniority/rank,
    administrative branch, province, term Roman numerals, or hallucinates content.
    Returns (is_valid, reason).
    """
    if not candidate_text or not isinstance(candidate_text, str):
        return False, "empty_output"
    cand = re.sub(r'\s+', ' ', candidate_text).strip(' .;,:-–—"\'')
    if len(cand) < 3 or len(cand) > 130:
        return False, "invalid_length"
    if any(ch in cand for ch in ('{', '}', '[', ']', '\n', '`')):
        return False, "markup_leak"

    src_low = source_text.lower()
    cand_low = cand.lower()

    # 1. Preserve leading deputy marker ("Phó ...") strictly
    src_starts_deputy = src_low.startswith("phó ")
    cand_starts_deputy = cand_low.startswith("phó ")
    if src_starts_deputy != cand_starts_deputy:
        return False, "deputy_prefix_mismatch"

    # 2. Preserve critical seniority and office role markers strictly
    for mod in (
        "thứ trưởng", "dự khuyết", "thường trực", "trợ lý", "thứ nhất",
        "quyền", "bí thư", "chủ tịch", "bộ trưởng", "thủ tướng"
    ):
        if (mod in src_low) != (mod in cand_low):
            return False, f"modifier_mismatch:{mod}"

    if ("bộ trưởng" in src_low) and ("thứ trưởng" in cand_low) and ("thứ trưởng" not in src_low):
        return False, "rank_downgrade_minister"

    # 3. Preserve Roman numeral terms if present in source
    src_romans = ROMAN_TERM_PATTERN.findall(source_text)
    if src_romans:
        cand_romans = ROMAN_TERM_PATTERN.findall(cand)
        if src_romans != cand_romans:
            return False, "roman_term_mismatch"

    # 4. Preserve province identity
    src_prov = _extract_province_canonical(source_text)
    cand_prov = _extract_province_canonical(cand)
    if src_prov and cand_prov and src_prov != cand_prov:
        return False, f"province_mismatch:{src_prov}->{cand_prov}"
    if src_prov and not cand_prov:
        return False, f"province_dropped:{src_prov}"

    # 5. Zero-hallucination token provenance & minimum overlap check
    src_tokens = set(re.findall(r'[0-9a-zà-ỹđ]+', src_low))
    cand_tokens = re.findall(r'[0-9a-zà-ỹđ]+', cand_low)
    cand_set = set(cand_tokens)
    novel = [t for t in cand_tokens if t not in src_tokens and t not in SAFE_EXPANSION_WORDS and len(t) > 1]
    if novel:
        return False, f"novel_tokens:{','.join(novel[:4])}"
    if src_tokens and cand_set:
        overlap_ratio = len(src_tokens & cand_set) / len(cand_set)
        if overlap_ratio < 0.45:
            return False, f"low_overlap:{overlap_ratio:.2f}"

    return True, "ok"


class LocalLLMNormalizer:
    """
    Hybrid rule + local Ollama (qwen3:1.7b) canonicalizer for Vietnamese political titles.
    """

    def __init__(
        self,
        model=DEFAULT_MODEL,
        ollama_url=OLLAMA_CHAT_URL,
        cache_path=None,
        report_path=None,
        batch_size=20,
        timeout=120
    ):
        self.model = model
        self.ollama_url = ollama_url
        self.cache_path = cache_path
        self.report_path = report_path
        self.batch_size = batch_size
        self.timeout = timeout
        self.cache = self._load_cache()
        self.stats = {
            "model": self.model,
            "total_raw_unique": 0,
            "after_deterministic_unique": 0,
            "llm_candidates": 0,
            "cache_hits": 0,
            "llm_batches": 0,
            "llm_accepted": 0,
            "guardrail_rejected": 0,
            "llm_errors": 0,
            "final_canonical_unique": 0,
            "elapsed_llm_seconds": 0.0,
        }
        self.guardrail_logs = []

    def _load_cache(self):
        if self.cache_path and os.path.exists(self.cache_path):
            try:
                with open(self.cache_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    return data
            except Exception:
                pass
        return {}

    def _save_cache(self):
        if self.cache_path:
            os.makedirs(os.path.dirname(self.cache_path), exist_ok=True)
            with open(self.cache_path, 'w', encoding='utf-8') as f:
                json.dump(self.cache, f, ensure_ascii=False, indent=2)

    def _build_prompt(self, indexed_items):
        lines = "\n".join([f'{idx}: {txt}' for idx, txt in indexed_items])
        return (
            "Bạn là chuyên gia chuẩn hóa thực thể hành chính-chính trị Việt Nam.\n"
            "Hãy chuẩn hóa mỗi chức danh theo chỉ số ID thành tên tiếng Việt chuẩn duy nhất để gộp các cách viết đồng nghĩa, nhưng TUYỆT ĐỐI KHÔNG gộp khác cấp bậc hoặc khác địa phương/bộ.\n"
            "Quy tắc bắt buộc:\n"
            "1. Mở rộng viết tắt (UBND -> Ủy ban nhân dân, HĐND -> Hội đồng nhân dân, ĐBQH -> Đại biểu Quốc hội, TPHCM -> Thành phố Hồ Chí Minh, TW -> Trung ương, UBKT -> Ủy ban Kiểm tra, MTTQ -> Mặt trận Tổ quốc, BCT -> Bộ Chính trị).\n"
            "2. Bỏ cụm quốc hiệu/quốc gia thừa ở cuối chức danh nhà nước hoặc bộ ngành (như 'Việt Nam', 'nước CHXHCNVN', 'Cộng hòa xã hội chủ nghĩa Việt Nam') khi không làm đổi nghĩa. NHƯNG phải GIỮ NGUYÊN 'Việt Nam' nếu là phần tên chính thức của cơ quan/tổ chức (ví dụ: 'Ngân hàng Nhà nước Việt Nam', 'Mặt trận Tổ quốc Việt Nam', 'Quân đội nhân dân Việt Nam', 'Đài Truyền hình Việt Nam').\n"
            "3. Bỏ phần mô tả phụ/lĩnh vực phụ trách thừa ở cuối (ví dụ 'Phụ trách Nội vụ, Y tế...'), thống nhất viết hoa chuẩn hành chính ('Tòa án nhân dân tối cao', 'Viện kiểm sát nhân dân tối cao', 'khóa XIII').\n"
            "4. TUYỆT ĐỐI GIỮ NGUYÊN: Phó vs Trưởng, Thứ trưởng vs Bộ trưởng, Dự khuyết vs Chính thức, Thường trực, tên Tỉnh/Thành phố, và số khóa La Mã (X, XI, XII, XIII, XIV, XV, XVI).\n"
            "5. Nếu chuỗi là nhiều chức vụ gộp liền nhau, giữ chức vụ chính quan trọng nhất hoặc chuẩn hóa sạch các từ viết tắt, không bịa thêm thông tin.\n"
            'Chỉ trả về JSON hợp lệ dạng: {"mappings": {"0": "Tên chuẩn", "1": "Tên chuẩn"}}\n\n'
            f"Danh sách cần chuẩn hóa:\n{lines}"
        )

    def _call_ollama_batch(self, indexed_items):
        prompt = self._build_prompt(indexed_items)
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "think": False,
            "format": "json",
            "stream": False,
            "options": {
                "temperature": 0.0,
                "num_ctx": 2048
            }
        }
        resp = requests.post(self.ollama_url, json=payload, timeout=self.timeout)
        resp.raise_for_status()
        content = resp.json().get("message", {}).get("content", "{}")
        parsed = json.loads(content)
        if isinstance(parsed, dict) and isinstance(parsed.get("mappings"), dict):
            return parsed["mappings"]
        if isinstance(parsed, dict):
            return parsed
        return {}

    def canonicalize_positions(self, raw_titles, verbose=True):
        """
        Canonicalize a collection of raw Infobox office strings.
        Returns dict mapping {raw_title: canonical_title}.
        """
        unique_raw = sorted({t.strip() for t in raw_titles if t and t.strip()})
        self.stats["total_raw_unique"] = len(unique_raw)

        # Phase A: Deterministic pre-cleaning & expansion
        raw_to_det = {}
        det_set = set()
        for r in unique_raw:
            d = deterministic_expand(preclean_title(r))
            if len(d) >= 3:
                raw_to_det[r] = d
                det_set.add(d)
            else:
                raw_to_det[r] = ""

        self.stats["after_deterministic_unique"] = len(det_set)

        # Phase B: Group into strict similarity clusters so variants share LLM batch context
        buckets = defaultdict(list)
        for d in sorted(det_set):
            buckets[strict_skeleton(d)].append(d)

        ordered_candidates = []
        clean_passthrough = {}
        for sk in sorted(buckets.keys()):
            grp = buckets[sk]
            if len(grp) > 1:
                ordered_candidates.extend(grp)
            else:
                item = grp[0]
                if NOISY_CANDIDATE_PATTERN.search(item) or len(item) >= 60:
                    ordered_candidates.append(item)
                else:
                    clean_passthrough[item] = item

        self.stats["llm_candidates"] = len(ordered_candidates)

        # Check cache for LLM candidates (re-verify against current guardrails)
        uncached = []
        det_to_canon = dict(clean_passthrough)
        for cand in ordered_candidates:
            if cand in self.cache:
                cached_val = self.cache[cand]
                ok, reason = validate_canonical_mapping(cand, cached_val)
                if ok:
                    det_to_canon[cand] = cached_val
                    self.stats["cache_hits"] += 1
                else:
                    uncached.append(cand)
            else:
                uncached.append(cand)

        if verbose:
            print(
                f"[LLM Canonicalizer ({self.model})] Raw unique: {len(unique_raw)} -> "
                f"After deterministic: {len(det_set)} | "
                f"LLM candidates: {len(ordered_candidates)} (cached: {len(ordered_candidates) - len(uncached)}, to query: {len(uncached)})",
                flush=True
            )

        # Phase C: Query Ollama qwen3:1.7b in context-preserving batches
        if uncached:
            t_start = time.time()
            total_batches = (len(uncached) + self.batch_size - 1) // self.batch_size
            for b_idx in range(total_batches):
                batch_items = uncached[b_idx * self.batch_size : (b_idx + 1) * self.batch_size]
                indexed = [(str(i), txt) for i, txt in enumerate(batch_items)]
                self.stats["llm_batches"] += 1

                try:
                    mappings = self._call_ollama_batch(indexed)
                except Exception as exc:
                    self.stats["llm_errors"] += 1
                    if verbose:
                        print(f"   ! Batch {b_idx + 1}/{total_batches} Ollama error ({exc}); using deterministic fallback.", flush=True)
                    mappings = {}

                for idx_str, orig_det in indexed:
                    proposed = mappings.get(idx_str) or mappings.get(orig_det) or orig_det
                    if isinstance(proposed, str):
                        proposed = re.sub(r'\s+', ' ', proposed).strip(' .;,:-–—"\'')
                    ok, reason = validate_canonical_mapping(orig_det, proposed)
                    if ok:
                        final_val = proposed
                        self.stats["llm_accepted"] += 1
                    else:
                        final_val = orig_det
                        self.stats["guardrail_rejected"] += 1
                        if len(self.guardrail_logs) < 100:
                            self.guardrail_logs.append({
                                "source": orig_det,
                                "proposed": proposed,
                                "reason": reason
                            })

                    det_to_canon[orig_det] = final_val
                    self.cache[orig_det] = final_val

                if (b_idx + 1) % 5 == 0 or (b_idx + 1) == total_batches:
                    self._save_cache()
                    if verbose:
                        el = time.time() - t_start
                        print(f"   -> Batch {b_idx + 1}/{total_batches} xong ({el:.1f}s)", flush=True)

            self.stats["elapsed_llm_seconds"] = round(time.time() - t_start, 2)
            self._save_cache()

        # Phase D: Enforce cluster consensus (if cluster variants differed only in casing after LLM, unify)
        canon_by_low = defaultdict(list)
        for v in det_to_canon.values():
            if v:
                canon_by_low[v.lower()].append(v)
        case_winner = {low: max(set(vals), key=vals.count) for low, vals in canon_by_low.items()}

        raw_to_canon = {}
        final_set = set()
        merges = defaultdict(set)
        for r, d in raw_to_det.items():
            if not d:
                raw_to_canon[r] = ""
                continue
            c_val = det_to_canon.get(d, d)
            c_val = case_winner.get(c_val.lower(), c_val)
            raw_to_canon[r] = c_val
            final_set.add(c_val)
            if r != c_val:
                merges[c_val].add(r)

        self.stats["final_canonical_unique"] = len(final_set)

        if self.report_path:
            os.makedirs(os.path.dirname(self.report_path), exist_ok=True)
            sample_merges = [
                {"canonical": k, "merged_variants": sorted(v)}
                for k, v in sorted(merges.items(), key=lambda x: -len(x[1]))[:80]
            ]
            with open(self.report_path, 'w', encoding='utf-8') as f:
                json.dump({
                    "stats": self.stats,
                    "top_merged_groups": sample_merges,
                    "guardrail_rejections_sample": self.guardrail_logs[:40]
                }, f, ensure_ascii=False, indent=2)

        if verbose:
            print(
                f"[LLM Canonicalizer] Kết quả Position: {len(unique_raw)} biến thể gốc -> "
                f"{len(final_set)} thực thể chuẩn (giảm {len(unique_raw) - len(final_set)} trùng lặp; "
                f"guardrail chặn {self.stats['guardrail_rejected']})",
                flush=True
            )

        return raw_to_canon
