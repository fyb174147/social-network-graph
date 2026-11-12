# Mạng lưới Chính trị gia Việt Nam — Approach 3 (Hybrid Snowball + NLP + Local LLM Canonicalization)

Repository độc lập triển khai **Hướng tiếp cận 3 (Approach 3)**: kết hợp thu thập đồ thị Wikipedia theo chiến lược **Hybrid Snowball BFS**, khai phá ngữ nghĩa từ **Infobox & Văn bản tiểu sử (NLP)**, và **Chuẩn hóa thực thể bằng LLM cục bộ (`qwen3.5-custom:latest` 4.2B qua Ollama)** kèm bộ lọc **Guardrail** chống ảo giác trước khi dựng Đồ thị tri thức (Knowledge Graph) và phân tích mạng xã hội (SNA).

---

## 1. Kiến trúc & Quy trình xử lý (Pipeline 5 Bước)

1. **Bước 1 — Thu thập dữ liệu (`src/crawler_snowball.py`):**
   - Bắt đầu từ các trang hạt giống bộ máy chính trị Việt Nam (`Chính phủ Việt Nam`, `Bộ Chính trị`, `BCH Trung ương`, `Đại biểu Quốc hội`) và mở rộng BFS theo các liên kết nhân sự (`Tiền nhiệm`, `Kế nhiệm`, `Cấp phó`) với bộ lọc chống trôi chủ đề -> **`2.050`** bài viết chính khách hợp lệ.
2. **Bước 2 — Trích xuất & Chuẩn hóa thực thể (`src/infobox_parser.py`, `src/nlp_extractor.py`, `src/llm_normalizer.py`, `src/llm_graph_builder.py`):**
   - **Trích xuất Infobox & NLP:** Bóc tách chức vụ, nhiệm kỳ, tiền nhiệm/kế nhiệm, cấp phó/cấp trưởng, quá trình trưởng thành từ cơ sở (`ROSE_FROM_GRASSROOTS`), luân chuyển (`TRANSFERRED_TO`) và điều động lên Trung ương (`PROMOTED_TO_CENTRAL`).
   - **Phase 1.5 — Chuẩn hóa thực thể bằng Local LLM (`qwen3.5-custom:latest`):**
     1. *Tiền xử lý tất định (`preclean_title`, `deterministic_expand`):* dọn tàn dư wiki (`}}`), chuẩn hóa dấu/chính tả (`tòan` -> `toàn`, `nước nước` -> `nước`), loại bỏ chú thích trạng thái/số lần trong ngoặc hoặc phần `Phụ trách...`, mở rộng viết tắt (`UBND`, `HĐND`, `ĐBQH`, `TPHCM`, `TP. HN`, `TW`).
     2. *Gom cụm theo ngữ cảnh (`strict_skeleton`):* nhóm các biến thể cùng khung ngữ nghĩa vào chung batch để LLM đối chiếu đồng thời.
     3. *Suy luận Ollama (`think: false`, `format: "json"`, `temperature: 0.0`):* gộp các biến thể đồng nghĩa về một tên chuẩn duy nhất (`1.159` cụm đề cử trong `68` batch).
     4. *Hậu kiểm an toàn (`validate_canonical_mapping`):* bảo toàn tuyệt đối cấp trưởng/cấp phó/vai trò (`Phó`, `Thứ trưởng`, `Dự khuyết`, `Thường trực`, `Quyền`, `Bí thư`, `Chủ tịch`, `Bộ trưởng`, `Thủ tướng`), số khóa La Mã, tên tỉnh/thành phố và chặn thêm từ lạ ngoài danh sách mở rộng chuẩn. Lưu cache tại `data/processed/llm_canonical_cache_qwen3.5-custom_latest.json`.
3. **Bước 3 — Xuất dữ liệu đồ thị (`src/neo4j_loader.py`):**
   - Sinh `vietnamese_politicians.cypher`, `vietnamese_politicians.graphml`, `nodes.csv`, `edges.csv` và `graph_data.json` trong `data/export/`.
4. **Bước 4 — Phân tích mạng xã hội SNA (`src/graph_analyzer.py`):**
   - Tính phân bố bậc, Degree Centrality, Betweenness Centrality, PageRank, phát hiện cộng đồng và lưu báo cáo tại `data/processed/network_stats.json`.
5. **Bước 5 — Trực quan hóa (`figures/`):**
   - Sinh `6` biểu đồ phục vụ báo cáo trong `figures/`.

---

## 2. Kết quả thực nghiệm & Đối chiếu với Baseline (Approach 2)

Trên cùng tập **`2.050`** bài viết chính khách Wikipedia:

| Chỉ số | Approach 2 *(Baseline)* | Approach 3 *(`qwen3.5-custom:latest`)* | Thay đổi |
| :--- | :---: | :---: | :---: |
| Tổng số nút (`Total Nodes`) | `6.260` | **`5.922`** | **`-338`** |
| Số nút chức danh (`Position`) | `3.608` | **`3.270`** *(từ `3.782` chuỗi gốc)* | **`-338` (`-9,37%`)** |
| Tổng số cạnh (`Total Edges`) | `45.572` | **`44.959`** | **`-613`** |
| `PREDECESSOR_OF` / `SUCCESSOR_OF` | `3.031` / `3.031` | **`2.910` / `2.910`** | **`-121` / `-121` cạnh trùng** |
| `BELONGS_TO_ORG` | `4.457` | **`4.405`** | **`-52` cạnh trùng** |
| `CO_LEADER` | `24.314` | **`23.996`** | **`-318`** |
| Thành phần liên thông lớn nhất (`LCC`) | `1.609` | **`1.609`** | `0` *(bảo toàn 100%)* |

- **Kiểm soát an toàn:** Guardrail chặn `98` đề xuất rủi ro; kiểm tra toàn bộ `1.159` mục trong cache xác nhận **`0` lỗi đổi cấp bậc/vai trò**.

---

## 3. Cấu trúc thư mục

```text
social-network-graph-approach3/
├── src/
│   ├── config.py                # Cấu hình đường dẫn & từ điển tỉnh/cơ quan TW/loại quan hệ
│   ├── crawler_snowball.py      # Bộ thu thập Hybrid Snowball BFS từ Wikipedia tiếng Việt
│   ├── infobox_parser.py        # Bóc tách dữ liệu cấu trúc Infobox
│   ├── nlp_extractor.py         # Khai phá luân chuyển / cơ sở / đoàn ĐBQH từ tiểu sử
│   ├── llm_normalizer.py        # Chuẩn hóa thực thể bằng Ollama (qwen3.5-custom:latest) + Guardrail
│   ├── graph_builder.py         # Lớp nền tảng dựng đồ thị & chiếu đồ thị chính khách
│   ├── llm_graph_builder.py     # Bộ dựng đồ thị tích hợp Phase 1.5 LLM Canonicalization
│   ├── neo4j_loader.py          # Xuất Cypher, GraphML, CSV, Web JSON
│   └── graph_analyzer.py        # Tính chỉ số SNA và vẽ biểu đồ
├── data/
│   ├── raw/                     # Dữ liệu Wikipedia thô (raw_politicians_snowball.json, snowball_trace.json)
│   ├── processed/               # network_stats.json, comparison_vs_approach2.json, cache & audit LLM
│   └── export/                  # nodes.csv, edges.csv, .cypher, .graphml, graph_data.json
├── figures/                     # 6 biểu đồ PNG dùng cho báo cáo
├── run_pipeline.py              # Script chạy toàn bộ pipeline
├── import_to_neo4j.py           # Nạp đồ thị từ CSV vào Neo4j
└── requirements.txt             # Thư viện Python cần thiết
```

---

## 4. Hướng dẫn sử dụng

```powershell
# 1. Cài đặt thư viện (nếu môi trường mới)
pip install -r requirements.txt

# 2. Chạy toàn bộ pipeline (tự tận dụng cache LLM & dữ liệu thô sẵn có)
python run_pipeline.py

# Hoặc đổi model Ollama / thu thập mới từ Wikipedia:
python run_pipeline.py --model qwen3.5-custom:latest --batch-size 15
python run_pipeline.py --refresh-crawl --target-count 2050

# 3. Nạp đồ thị vào Neo4j (Bolt mặc định bolt://localhost:7687)
python import_to_neo4j.py <mat_khau_neo4j>
```
