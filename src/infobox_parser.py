# -*- coding: utf-8 -*-
"""
Infobox Parser for Vietnamese Politicians.
Extracts structured biographical data, offices held, tenures,
predecessors, successors, and deputy relationships.
"""
import re
from src.config import PROVINCES, PROVINCE_CANONICAL, CENTRAL_AGENCIES

RANK_PREFIX_PATTERN = re.compile(
    r'^(?:(?:Phó\s+Giáo\s+sư|Giáo\s+sư|Tiến\s+sĩ|Thạc\s+sĩ|PGS\.?\s*TS\.?|GS\.?\s*TS\.?|PGS\.?|GS\.?|TS\.?|'
    r'Đại\s+tướng|Thượng\s+tướng|Trung\s+tướng|Thiếu\s+tướng|Đô\s+đốc|Phó\s+Đô\s+đốc|Chuẩn\s+Đô\s+đốc|'
    r'Đại\s+tá|Thượng\s+tá|Trung\s+tá|Thiếu\s+tá|Ông|Bà)\s+)+',
    re.IGNORECASE
)

def clean_person_name(name):
    """Normalize a politician's display name by stripping wiki links, parenthetical notes, and rank/degree prefixes."""
    if not name:
        return ""
    n = name.split('|')[-1].strip()
    n = n.replace('[[', '').replace(']]', '').strip()
    if '(' in n and ')' in n:
        n = n.split('(')[0].strip()
    n = RANK_PREFIX_PATTERN.sub('', n).strip()
    return re.sub(r'\s+', ' ', n).strip()

def canonical_local_org(province):
    """Canonical organization name for a provincial authority, shared across Infobox and NLP."""
    if not province:
        return None
    prov = PROVINCE_CANONICAL.get(province, province)
    return f"Tỉnh ủy / UBND {prov}"

def canonicalize_office_name(office_name):
    """Standardize office title phrasing, tone marks, and strip status notes."""
    if not office_name:
        return ""
    off = office_name.strip()
    # Normalize common Vietnamese tone-mark variants
    for old_v, new_v in (
        ('uỷ', 'ủy'), ('Uỷ', 'Ủy'), ('uý', 'úy'), ('Uý', 'Úy'),
        ('hoà', 'hòa'), ('Hoà', 'Hòa'), ('toà', 'tòa'), ('Toà', 'Tòa'),
        ('khoá', 'khóa'), ('Khoá', 'Khóa')
    ):
        off = off.replace(old_v, new_v)

    # Remove parenthetical status notes like "(Đã bị cách chức)", "(2021–2026)"
    off = re.sub(
        r'\s*\([^)]*(?:cách chức|từ trần|qua đời|tạm quyền|quyền|khuyết|miễn nhiệm|kỷ luật|thôi chức|nghỉ hưu|nhiệm kỳ|\d{4})[^)]*\)',
        '', off, flags=re.IGNORECASE
    )
    # Standardize phrasing of top state titles ("Thủ tướng Chính phủ [nước] Cộng hòa...")
    off = re.sub(
        r'\b(Chủ tịch nước|Thủ tướng Chính phủ|Phó Thủ tướng Chính phủ|Chủ tịch Quốc hội)\s+(?:nước\s+)?(Cộng hòa xã hội chủ nghĩa Việt Nam)\b',
        r'\1 nước \2', off, flags=re.IGNORECASE
    )
    off = re.sub(r'\s*[-–—]\s*', ' - ', off)
    off = re.sub(r'\s+', ' ', off).strip(' .;,:-–—')
    return off

def office_dedup_key(office_name):
    """Normalized comparison key for deduplicating near-identical office titles."""
    k = canonicalize_office_name(office_name).lower()
    k = re.sub(r'\bubnd\b', 'ủy ban nhân dân', k)
    k = re.sub(r'\bhđnd\b', 'hội đồng nhân dân', k)
    k = re.sub(r'\bđbqh\b', 'đại biểu quốc hội', k)
    k = re.sub(r'\btw\b', 'trung ương', k)
    k = re.sub(r'\b(?:cộng hòa xã hội chủ nghĩa việt nam|đảng cộng sản việt nam|nước)\b', ' ', k)
    k = re.sub(r'[-–—,:;.]', ' ', k)
    k = re.sub(r'\s+', ' ', k).strip()
    return k

def clean_wikitext(text):
    """Strip wiki markup, file embeds, templates, references, and HTML tags."""
    if not text:
        return ""
    # Strip references and HTML tags
    t = re.sub(r'<ref[^>]*>.*?</ref>', ' ', text, flags=re.DOTALL)
    t = re.sub(r'<ref[^>]*/>', ' ', t)
    t = re.sub(r'<[^>]+>', ' ', t)
    t = t.replace('&nbsp;', ' ').replace('&ndash;', '–').replace('&mdash;', '—')

    # Handle {{ngày sinh và tuổi|1958|12|25}} -> 1958-12-25
    m_birth = re.search(r'\{\{(?:ngày sinh và tuổi|birth date and age|date of birth)[\s\|]+(\d{4})[\s\|]+(\d{1,2})[\s\|]+(\d{1,2})', t, re.IGNORECASE)
    if m_birth:
        t = re.sub(r'\{\{[^}]+\}\}', f"{m_birth.group(1)}-{m_birth.group(2).zfill(2)}-{m_birth.group(3).zfill(2)}", t, count=1)

    # Strip remaining templates
    while re.search(r'\{\{[^{}]*\}\}', t):
        t = re.sub(r'\{\{[^{}]*\}\}', ' ', t)

    # Strip File/Image embeds BEFORE converting [[Link|Anchor]] -> Anchor (prevents '25px' artifacts)
    t = re.sub(r'\[\[(?:Tập tin|File|Hình|Image):(?:[^\[\]]|\[\[[^\]]*\]\])*\]\]', ' ', t, flags=re.IGNORECASE)

    # Convert [[Link|Anchor]] -> Anchor
    t = re.sub(r'\[\[(?:[^|\]]*\|)?([^\]]+)\]\]', r'\1', t)
    # Strip stray image size tokens and bold/italic markup
    t = re.sub(r'\b\d{1,4}px\b', ' ', t)
    t = re.sub(r"''+", '', t)
    # Clean whitespace
    t = re.sub(r'\s+', ' ', t).strip()
    return t

def extract_wiki_links(text):
    """Extract list of target wiki links from text [[Link|Anchor]] or [[Link]]."""
    if not text:
        return []
    matches = re.findall(r'\[\[([^\]\|]+)(?:\|[^\]]+)?\]\]', text)
    cleaned = []
    for m in matches:
        m = m.strip()
        if not m.startswith(('Tập tin:', 'File:', 'Hình:', 'Image:', 'Thể loại:', 'Category:')):
            cleaned.append(m)
    return cleaned

def extract_year(text):
    """Extract 4-digit year from string (19xx or 20xx)."""
    if not text:
        return None
    m = re.findall(r'\b(19\d{2}|20\d{2})\b', text)
    if m:
        return int(m[0])
    return None

def extract_all_years(text):
    """Extract all 4-digit years from string."""
    if not text:
        return []
    return [int(y) for y in re.findall(r'\b(19\d{2}|20\d{2})\b', text)]

def parse_infobox(wikitext, title):
    """Parse infobox template into structured dictionary."""
    data = {
        'title': title,
        'name': title,
        'birth_year': None,
        'birth_date': None,
        'birth_place': None,
        'hometown': None,
        'death_year': None,
        'education': None,
        'party': 'Đảng Cộng sản Việt Nam',
        'offices': []
    }
    
    # Locate infobox
    # Matches {{Thông tin viên chức, {{Thông tin chính khách, {{Viên chức, {{Infobox
    m_info = re.search(r'\{\{(?:Thông tin viên chức|Thông tin chính khách|Viên chức|Thông tin nhân vật|Infobox person|Infobox officeholder)[\s\S]*?\n\}\}', wikitext, re.IGNORECASE)
    
    # If not found exact closing, try greedy match until start of article body
    if not m_info:
        m_info = re.search(r'(\{\{(?:Thông tin viên chức|Thông tin chính khách|Viên chức|Thông tin nhân vật)[\s\S]*?)(?=\n\'\'\'|\n==|\Z)', wikitext, re.IGNORECASE)
    
    info_raw = m_info.group(0) if m_info else ""
    
    # Parse key-value pairs in infobox
    raw_fields = {}
    if info_raw:
        lines = info_raw.split('\n')
        curr_key = None
        curr_val = []
        for line in lines:
            line_str = line.strip()
            if line_str.startswith('|') and '=' in line_str:
                if curr_key:
                    raw_fields[curr_key] = "\n".join(curr_val).strip()
                k, v = line_str[1:].split('=', 1)
                curr_key = k.strip().lower()
                curr_val = [v.strip()]
            elif curr_key:
                curr_val.append(line_str)
        if curr_key:
            raw_fields[curr_key] = "\n".join(curr_val).strip()
            
    # Extract Name (prefer clean Wikipedia title if Infobox concatenates multiple aliases)
    title_clean = clean_person_name(title)
    data['name'] = title_clean or title
    name_field = raw_fields.get('name') or raw_fields.get('tên')
    if name_field:
        parsed_name = clean_person_name(clean_wikitext(name_field))
        if parsed_name and len(parsed_name.split()) <= max(len(title_clean.split()) + 1, 5):
            data['name'] = parsed_name
        
    # Extract Birth Date & Birth Year
    bdate_field = raw_fields.get('birth_date') or raw_fields.get('ngày sinh') or raw_fields.get('date_of_birth')
    if bdate_field:
        clean_bd = clean_wikitext(bdate_field)
        data['birth_date'] = clean_bd
        y = extract_year(clean_bd)
        if y:
            data['birth_year'] = y
            
    if not data['birth_year']:
        # Fallback to article first paragraph: '''Tên''' (sinh [[1960]]...)
        m_birth_body = re.search(r"\(sinh\s+(?:ngày\s+[\d\s\w\[\]]+năm\s+)?\[?\[?(19\d{2}|20\d{2})\]?\]?", wikitext)
        if m_birth_body:
            data['birth_year'] = int(m_birth_body.group(1))

    # Hometown / Native place
    ht_field = (raw_fields.get('hometown') or raw_fields.get('quê quán') or 
                raw_fields.get('nguyên quán') or raw_fields.get('nơi sinh') or 
                raw_fields.get('birth_place'))
    if ht_field:
        clean_ht = clean_wikitext(ht_field)
        data['hometown'] = clean_ht
        data['birth_place'] = clean_ht
        
    # Education
    edu_field = raw_fields.get('alma_mater') or raw_fields.get('học vấn') or raw_fields.get('học vị') or raw_fields.get('education')
    if edu_field:
        data['education'] = clean_wikitext(edu_field)
        
    # Parse Offices / Positions
    # Infoboxes have: office, office1, office2... or chức vụ, chức vụ 1, chức vụ 2...
    office_indices = [''] + [str(i) for i in range(1, 15)]
    for idx in office_indices:
        off_key = f'office{idx}' if idx else 'office'
        cv_key = f'chức vụ{idx}' if idx else 'chức vụ'
        cv_space = f'chức vụ {idx}' if idx else 'chức vụ'
        
        raw_office = raw_fields.get(off_key) or raw_fields.get(cv_key) or raw_fields.get(cv_space)
        if not raw_office:
            continue
            
        office_name = canonicalize_office_name(clean_wikitext(raw_office))
        if not office_name or len(office_name) < 3:
            continue
            
        # Term start / end
        t_start = (raw_fields.get(f'term_start{idx}') or raw_fields.get(f'bắt đầu{idx}') or 
                   raw_fields.get(f'bắt đầu {idx}') or raw_fields.get(f'date1{idx}'))
        t_end = (raw_fields.get(f'term_end{idx}') or raw_fields.get(f'kết thúc{idx}') or 
                 raw_fields.get(f'kết thúc {idx}') or raw_fields.get(f'date2{idx}'))
        
        s_year = extract_year(clean_wikitext(t_start)) if t_start else None
        e_year = extract_year(clean_wikitext(t_end)) if t_end else None
        
        # Predecessor & Successor
        pred = (raw_fields.get(f'predecessor{idx}') or raw_fields.get(f'tiền nhiệm{idx}') or 
                raw_fields.get(f'tiền nhiệm {idx}'))
        succ = (raw_fields.get(f'successor{idx}') or raw_fields.get(f'kế nhiệm{idx}') or 
                raw_fields.get(f'kế nhiệm {idx}'))
        
        pred_links = extract_wiki_links(pred) if pred else []
        succ_links = extract_wiki_links(succ) if succ else []
        
        clean_pred = clean_wikitext(pred) if pred else None
        clean_succ = clean_wikitext(succ) if succ else None
        
        # Deputies vs Superiors in infobox (1blankname / 1namedata)
        deputy_names = []
        superior_names = []
        sub_markers = ('phó', 'thứ trưởng', 'trợ lý', 'cấp phó')
        sup_markers = (
            'tổng bí thư', 'chủ tịch nước', 'thủ tướng', 'chủ tịch quốc hội',
            'bí thư', 'chủ tịch', 'bộ trưởng', 'trưởng ban', 'viện trưởng',
            'chánh án', 'tư lệnh', 'giám đốc', 'tổng kiểm toán', 'thống đốc'
        )
        office_low = office_name.lower()
        is_curr_subordinate = any(m in office_low for m in ('phó', 'thứ trưởng', 'thường trực', 'trợ lý'))

        for d_idx in range(1, 5):
            b_name = raw_fields.get(f'{d_idx}blankname{idx}')
            b_data = raw_fields.get(f'{d_idx}namedata{idx}')
            if b_data:
                links = extract_wiki_links(b_data)
                b_low = clean_wikitext(b_name).lower() if b_name else ""
                if any(m in b_low for m in sub_markers):
                    deputy_names.extend(links)
                elif any(m in b_low for m in sup_markers) and is_curr_subordinate:
                    superior_names.extend(links)

        explicit_dep_data = raw_fields.get(f'danh sách phó{idx}')
        if explicit_dep_data:
            deputy_names.extend(extract_wiki_links(explicit_dep_data))

        data['offices'].append({
            'office': office_name,
            'start_year': s_year,
            'end_year': e_year,
            'predecessor_name': clean_pred,
            'predecessor_links': pred_links,
            'successor_name': clean_succ,
            'successor_links': succ_links,
            'deputies': deputy_names,
            'superiors': superior_names
        })

    return data

def extract_province_from_text(text):
    """Identify which Vietnamese province is referenced in a text snippet."""
    if not text:
        return None
    for prov in PROVINCES:
        pattern = r'\b' + re.escape(prov) + r'\b'
        if re.search(pattern, text, re.IGNORECASE):
            return PROVINCE_CANONICAL.get(prov, prov)
    return None

def extract_central_org_from_text(text):
    """Identify central party or government agency referenced in a text snippet."""
    if not text:
        return None
    for org in CENTRAL_AGENCIES:
        if org.lower() in text.lower():
            return org
    return None
