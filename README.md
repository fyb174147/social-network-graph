# Mạng lưới Chính trị gia Việt Nam — Snowball BFS + NLP + Local LLM

Hệ thống xây dựng **Đồ thị tri thức (Knowledge Graph)** và **Phân tích mạng xã hội (SNA)** về đội ngũ chính trị gia Việt Nam từ Wikipedia tiếng Việt, kết hợp thu thập đồ thị theo chiến lược **Hybrid Snowball BFS**, khai phá ngữ nghĩa từ **Infobox & Văn bản tiểu sử (NLP)**, và **Chuẩn hóa thực thể bằng LLM cục bộ (`qwen3.5-custom:latest` qua Ollama)** kèm hệ thống **5 lớp Guardrail** chống ảo giác.

---

## 1. Kiến trúc & Quy trình xử lý (Pipeline 5 Bước)

1. **Bước 1 — Thu thập dữ liệu (`src/crawler_snowball.py`):**
   - Khởi phát từ 14 trang hạt giống bộ máy chính trị và nguyên thủ Việt Nam (`Chính phủ Việt Nam`, `Bộ Chính trị`, `BCH Trung ương`, `Danh sách Đại biểu Quốc hội`, ...), mở rộng theo chiều rộng (BFS) qua các liên kết nhân sự (`Tiền nhiệm`, `Kế nhiệm`, `Cấp phó`) kết hợp bộ lọc chống trôi chủ đề để sàng lọc 7.000 trang và thu về **`2.050`** bài viết chính khách hợp lệ lưu tại `data/raw/raw_politicians_snowball.json`.
2. **Bước 2 — Tiền xử lý, Trích xuất Infobox/NLP & Chuẩn hóa LLM:**
   - **Tiền xử lý & Trích xuất (`src/infobox_parser.py`, `src/nlp_extractor.py`):** Làm sạch cú pháp Wikitext/HTML/ảnh nhúng, chuẩn hóa danh xưng và địa danh, bóc tách chức danh, niên hạn tại nhiệm, tiền nhiệm/kế nhiệm, cấp phó/cấp trưởng, quá trình trưởng thành từ cơ sở (`ROSE_FROM_GRASSROOTS`), luân chuyển có hướng (`TRANSFERRED_TO`) và thăng tiến lên Trung ương (`PROMOTED_TO_CENTRAL`).
   - **Chuẩn hóa thực thể bằng Local LLM (`src/llm_normalizer.py`):**
     1. *Tiền xử lý tất định (`preclean_title`, `deterministic_expand`):* Dọn ngoặc wiki sót, chuẩn hóa dấu thanh tiếng Việt cũ (`tòan` -> `toàn`, `uỷ` -> `ủy`, `nước nước` -> `nước`), xóa chú thích trạng thái/số lần trong ngoặc hoặc phần `Phụ trách...`, mở rộng viết tắt (`UBND`, `HĐND`, `ĐBQH`, `TPHCM`, `TP. HN`, `TW`).
     2. *Gom cụm ngữ cảnh (`strict_skeleton`):* Nhóm các biến thể cùng khung ngữ nghĩa vào chung batch để LLM đối chiếu đồng thời.
     3. *Suy luận Ollama (`think: false`, `format: "json"`, `temperature: 0.0`):* Hợp nhất các biến thể đồng nghĩa về một tên chuẩn duy nhất (`1.159` ứng viên gom cụm xử lý trong `68` batch).
     4. *Hậu kiểm an toàn 5 lớp (`validate_canonical_mapping`):* Kiểm tra độ dài & chống rò rỉ cú pháp, bảo toàn tuyệt đối cấp trưởng/cấp phó và 10 từ khóa vai trò (`Phó`, `Thứ trưởng`, `Dự khuyết`, `Thường trực`, `Quyền`, `Bí thư`, `Chủ tịch`, `Bộ trưởng`, `Thủ tướng`), bảo toàn số khóa La Mã, tên Tỉnh/Thành phố, và kiểm chứng nguồn gốc token (`SAFE_EXPANSION_WORDS`, ngưỡng chồng lấp >= `0.45`). Lưu cache bền vững tại `data/processed/llm_canonical_cache_qwen3.5-custom_latest.json`.
3. **Bước 3 — Dựng Đồ thị & Xuất Neo4j (`src/llm_graph_builder.py`, `src/neo4j_loader.py`):**
   - Khởi tạo đồ thị đa quan hệ `nx.MultiDiGraph` (5 nhãn nút, 12 loại quan hệ có trọng số), chiếu sang mạng thuần nhất chính khách `subG`, và xuất `vietnamese_politicians.cypher`, `vietnamese_politicians.graphml`, `nodes.csv`, `edges.csv` cùng `graph_data.json` trong `data/export/`.
4. **Bước 4 — Phân tích mạng xã hội SNA (`src/graph_analyzer.py`):**
   - Tính phân bố bậc, Degree Centrality, Betweenness Centrality, PageRank có trọng số, phát hiện cộng đồng Clauset–Newman–Moore và thống kê luân chuyển cán bộ vào `data/processed/network_stats.json`.
5. **Bước 5 — Trực quan hóa (`figures/`):**
   - Tự động sinh `6` biểu đồ PNG (300 DPI) phục vụ phân tích.

---

## 2. Kết quả thực nghiệm & Thống kê mạng lưới

Trên tập **`2.050`** bài viết chính khách thu thập được từ Wikipedia tiếng Việt:

| Chỉ số mạng lưới | Giá trị đo được | Ghi chú |
| :--- | :---: | :--- |
| Tổng số nút (`Total Nodes`) | **`5.922`** | `2.050` Politician, `3.270` Position, `531` Organization, `66` Location, `5` Term |
| Tổng số cạnh (`Total Edges`) | **`44.959`** | Phân bổ trên `12` loại quan hệ có trọng số |
| Nén nút chức danh (`Position`) | **`3.270`** | Tinh gọn từ `3.782` chuỗi gốc (`3.608` sau quy tắc tất định; giảm `338` nút / `-9,37%` qua LLM) |
| Chuỗi tiền nhiệm / kế nhiệm | **`2.910` / `2.910`** | Đã loại bỏ `121` cặp cạnh trùng nhờ chuẩn hóa chức danh & `add_edge_once` |
| Bậc trung bình / Bậc cực đại | `15,18` / `1.006` | Mật độ đồ thị `0,001282` |
| Thành phần liên thông lớn nhất (`LCC`) | **`1.609`** | Chiếm `78,49%` tổng số chính khách (bảo toàn 100% tính liên thông) |
| Kiểm soát an toàn Guardrail | **`0` lỗi đảo vai trò** | Chặn `98` đề xuất vượt ngưỡng/lệch thực thể trên lần chạy đầy đủ |

---

## 3. Cấu trúc mã nguồn

```text
social-network-graph/
├── src/
│   ├── config.py                # Cấu hình đường dẫn & từ điển tỉnh/cơ quan TW/loại quan hệ
│   ├── crawler_snowball.py      # Bộ thu thập Hybrid Snowball BFS từ Wikipedia tiếng Việt
│   ├── infobox_parser.py        # Làm sạch Wikitext & bóc tách cấu trúc Infobox đa nhiệm kỳ
│   ├── nlp_extractor.py         # Khai phá luân chuyển / cơ sở / đoàn ĐBQH từ tiểu sử
│   ├── llm_normalizer.py        # Chuẩn hóa thực thể bằng Ollama (qwen3.5-custom:latest) + 5 lớp Guardrail
│   ├── graph_builder.py         # Lớp nền tảng dựng đồ thị & chiếu đồ thị chính khách
│   ├── llm_graph_builder.py     # Bộ dựng đồ thị tích hợp chuẩn hóa LLM & chống trùng cạnh
│   ├── neo4j_loader.py          # Xuất Cypher (UNWIND), GraphML, CSV, Web JSON
│   └── graph_analyzer.py        # Tính chỉ số SNA và sinh biểu đồ
├── run_pipeline.py              # Script điều phối toàn bộ pipeline 5 bước
├── import_to_neo4j.py           # Nạp đồ thị từ CSV vào Neo4j qua Bolt driver
└── requirements.txt             # Thư viện Python cần thiết
```

*(Các thư mục `data/` và `figures/` sẽ được tự động khởi tạo khi chạy pipeline.)*

---

## 4. Hướng dẫn sử dụng

```powershell
# 1. Cài đặt thư viện
pip install -r requirements.txt

# 2. Chạy toàn bộ pipeline (cần Ollama đang bật với model qwen3.5-custom:latest)
python run_pipeline.py

# Hoặc đổi model Ollama / thu thập mới dữ liệu từ Wikipedia:
python run_pipeline.py --model qwen3.5-custom:latest --batch-size 15
python run_pipeline.py --refresh-crawl --target-count 2050

# 3. Nạp đồ thị vào Neo4j (Bolt mặc định bolt://localhost:7687)
python import_to_neo4j.py <mat_khau_neo4j>
```
