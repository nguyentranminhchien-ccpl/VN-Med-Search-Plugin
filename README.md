# 🔍 VN-Med-Search Plugin

> **Plugin tìm kiếm tài liệu y học Việt Nam** dành cho Antigravity Agent.  
> Tự động thu thập, lọc và tổng hợp bài báo từ các tạp chí y khoa và cơ sở dữ liệu học thuật Việt Nam.

---

## 📋 Mục lục

- [Giới thiệu](#giới-thiệu)
- [Nguồn dữ liệu](#nguồn-dữ-liệu)
- [Cấu trúc thư mục](#cấu-trúc-thư-mục)
- [Hướng dẫn sử dụng qua Agent](#hướng-dẫn-sử-dụng-qua-agent)
- [Hướng dẫn sử dụng CLI trực tiếp](#hướng-dẫn-sử-dụng-cli-trực-tiếp)
- [Tham số CLI](#tham-số-cli)
- [Ví dụ thực tế](#ví-dụ-thực-tế)
- [Kiến trúc kỹ thuật](#kiến-trúc-kỹ-thuật)
- [Lưu ý kỹ thuật](#lưu-ý-kỹ-thuật)

---

## Giới thiệu

Plugin này cho phép tìm kiếm tài liệu y học và khoa học được xuất bản tại Việt Nam thông qua:

- **Giao diện ngôn ngữ tự nhiên** (hỏi agent, agent tự tìm kiếm)
- **CLI trực tiếp** (`vn_med_search.py`) để tích hợp vào workflow tự động

Kết quả trả về bao gồm: tiêu đề, tác giả, tóm tắt (abstract), DOI, link bài viết, link PDF (nếu có).

---

## Nguồn dữ liệu

| Mã nguồn | Tên đầy đủ | Loại | Ghi chú |
|---|---|---|---|
| `tcncyh` | Tạp chí Nghiên cứu Y học | OJS2 | Bộ Y tế, bài báo lâm sàng |
| `vmj` | Tạp chí Y học Việt Nam | OJS2 | Tổng hội Y học Việt Nam |
| `bv108` | Tạp chí Y Dược Lâm sàng 108 | OJS2 | Bệnh viện Trung ương Quân đội 108 |
| `vnu` | Tạp chí Khoa học VNU (MPS, NST) | OJS3 | ĐH Quốc gia Hà Nội — Y Dược & Khoa học TN |
| `nlv-luanan` | Thư viện Quốc gia — Luận án | Scraping | Luận án Tiến sĩ, Thạc sĩ |
| `vista` | VISTA STI — Cơ sở dữ liệu KH&CN | POST API | Công bố KH&CN Quốc gia |

---

## Cấu trúc thư mục

```
vn-med-search/
├── AGENTS.md                        # Rules: ép agent dùng subagent, không chạy CLI trực tiếp
├── plugin.json                      # Metadata plugin (version, skills, agents)
├── README.md                        # File này
├── agents/
│   └── vn-med-researcher.json       # Định nghĩa subagent chuyên tìm kiếm
└── skills/
    └── vn-med-search/
        ├── SKILL.md                 # Hướng dẫn cho agent (Query Builder Protocol)
        └── scripts/
            └── vn_med_search.py     # Script CLI chính (Python)
```

---

## Hướng dẫn sử dụng qua Agent

Khi dùng qua Antigravity Agent, chỉ cần nói: *"Tìm tài liệu về [chủ đề]"*.

Agent sẽ hỏi tuần tự từng bước để thu thập bộ lọc:

```
Agent: Bạn muốn tìm kiếm về chủ đề gì?
Bạn:   Điều trị đột quỵ nhồi máu não

Agent: Bạn có muốn lọc theo tên tác giả không? (Bỏ qua: gõ 'không')
Bạn:   không

Agent: Khoảng năm xuất bản? (Ví dụ: 2020-2025, hoặc 'không')
Bạn:   2022-2026

Agent: Thiết kế nghiên cứu? (rct/systematic-review/case-report/cohort/mo-ta, hoặc 'không')
Bạn:   không

Agent: Nguồn ưu tiên? (tcncyh/vmj/bv108/nlv-luanan/vista, hoặc 'all')
Bạn:   all
```

Sau đó agent sẽ tự động khởi chạy subagent `vn-med-researcher` trong nền và trả về báo cáo tổng hợp.

> **Lưu ý:** Vì các nguồn dữ liệu trong nước không hỗ trợ tìm kiếm NLP, query dài (nguyên câu) thường trả về 0 kết quả. Subagent sẽ tự động phân rã thành các từ khóa ngắn (2-3 từ) và chạy song song.

---

## Hướng dẫn sử dụng CLI trực tiếp

Yêu cầu: [`uv`](https://github.com/astral-sh/uv) (Python package manager).

```bash
# Cú pháp chung
uv run --with httpx --with beautifulsoup4 --with typer --with rich \
  "C:\Users\Thinkpad T14 gen 2\.gemini\config\plugins\vn-med-search\skills\vn-med-search\scripts\vn_med_search.py" \
  "<từ khóa>" [OPTIONS]
```

---

## Tham số CLI

| Tham số | Kiểu | Mặc định | Mô tả |
|---|---|---|---|
| `query` | `TEXT` | *(bắt buộc)* | Từ khóa tìm kiếm (ngắn, 2-3 từ) |
| `--sources` | `TEXT` | `all` | Nguồn: `all`, `tcncyh`, `vmj`, `bv108`, `vnu`, `nlv-luanan`, `vista` |
| `--max-results` | `INT` | `20` | Số kết quả tối đa mỗi nguồn |
| `--author` | `TEXT` | `None` | Lọc theo tên tác giả (không phân biệt hoa/thường) |
| `--year` | `TEXT` | `None` | Lọc năm: `"2023"` hoặc `"2020-2025"` |
| `--study-type` | `TEXT` | `None` | Loại nghiên cứu: `rct`, `systematic-review`, `case-report`, `cohort`, `mo-ta` |
| `--topic-keywords` | `TEXT` | `None` | Từ khóa phụ lọc độ liên quan (phân cách bằng dấu phẩy) |
| `--show-low-relevance` | Flag | `False` | Hiển thị thêm bảng kết quả ít liên quan |
| `--json` | Flag | `False` | Xuất kết quả dạng JSON (dành cho xử lý tự động) |
| `--verbose` | Flag | `False` | Hiển thị debug log (HTTP calls, filter decisions) |

---

## Ví dụ thực tế

### 1. Tìm kiếm cơ bản
```bash
uv run ... vn_med_search.py "đột quỵ" --sources all
```

### 2. Lọc theo năm và nguồn
```bash
uv run ... vn_med_search.py "lấy huyết khối" --sources tcncyh,bv108 --year 2022-2026
```

### 3. Lọc độ liên quan — ẩn kết quả rác
```bash
# Chỉ hiện bài liên quan đến đột quỵ/thrombectomy (ẩn bài tim mạch không liên quan)
uv run ... vn_med_search.py "kháng tiểu cầu" \
  --topic-keywords "huyết khối,đột quỵ,stroke,não" --sources all --json
```

### 4. Hiển thị cả kết quả ít liên quan (2 bảng riêng)
```bash
uv run ... vn_med_search.py "kháng tiểu cầu" \
  --topic-keywords "huyết khối,đột quỵ" --show-low-relevance
```

### 5. Chạy nhiều từ khóa và gộp kết quả (dành cho scripting)
```powershell
$keywords = @("lấy huyết khối", "kháng tiểu cầu", "hẹp động mạch não")
$results = @()
foreach ($kw in $keywords) {
    $out = uv run ... vn_med_search.py $kw --sources all --json | ConvertFrom-Json
    $results += $out.articles
}
# Dedup thủ công hoặc dùng lại trong script Python
```

### 6. Lọc theo thiết kế nghiên cứu
```bash
# Chỉ lấy thử nghiệm lâm sàng ngẫu nhiên
uv run ... vn_med_search.py "tim mạch" --study-type rct --year 2020-2026
```

---

## Kiến trúc kỹ thuật

```
┌─────────────────────────────────────────────┐
│          Antigravity Agent (cửa sổ chính)    │
│  • Nhận yêu cầu từ user                     │
│  • Hỏi 5 bộ lọc tuần tự                    │
│  • Delegate cho vn-med-researcher subagent  │
└─────────────────┬───────────────────────────┘
                  │ invoke_subagent
                  ▼
┌─────────────────────────────────────────────┐
│       vn-med-researcher (subagent)           │
│  • Phân rã query dài → cụm từ ngắn         │
│  • Chạy vn_med_search.py CLI nhiều lần      │
│  • Gộp JSON, dedup, tổng hợp báo cáo        │
└─────────────────┬───────────────────────────┘
                  │ run_command
                  ▼
┌─────────────────────────────────────────────┐
│         vn_med_search.py (CLI script)        │
│                                             │
│  ┌──────────┐ ┌──────────┐ ┌─────────────┐ │
│  │OJSAdapter│ │VNUAdapter│ │VISTAAdapter │ │
│  │(OJS2)    │ │(OJS3)    │ │(POST API)   │ │
│  │tcncyh    │ │MPS / NST │ │             │ │
│  │vmj, bv108│ │          │ │             │ │
│  └────┬─────┘ └────┬─────┘ └──────┬──────┘ │
│       │            │              │         │
│  ┌────┴────────────┴──────────────┴──────┐  │
│  │   NLVLuanAnAdapter (Scraping)         │  │
│  │   luanan.nlv.gov.vn                   │  │
│  └───────────────────────────────────────┘  │
│                                             │
│  Dedup → Filter (author/year/study/topic)   │
│  → Sort by year → JSON / Rich Table output  │
└─────────────────────────────────────────────┘
```

---

## Lưu ý kỹ thuật

### SSL & Encoding
- Tất cả HTTP request đều dùng `verify=False` do nhiều server VN sử dụng chứng chỉ SSL tự ký.
- Script cấu hình `sys.stdout.reconfigure(encoding='utf-8')` để xử lý tiếng Việt đúng trên Windows.

### VNU Adapter (OJS3)
- VNU không dùng OJS2 mà dùng **OJS3** với URL search dạng `/<journal>/search/search`.
- Kết quả render trong `div.article-summary`, không phải thẻ `<a>` trực tiếp.
- Hiện tại tìm kiếm trên 2 tạp chí con: **MPS** (Y Dược) và **NST** (Khoa học Tự nhiên).

### VISTA
- Endpoint VISTA chỉ chấp nhận **POST body** (`application/x-www-form-urlencoded`).
- Gửi GET hoặc POST query string sẽ trả về lỗi `not found!`.

### Bộ lọc `--study-type`
- Vì các nguồn Việt Nam không gắn nhãn thiết kế nghiên cứu chuẩn, bộ lọc hoạt động bằng cách **tìm từ khóa** trong tiêu đề và abstract (ví dụ: "ngẫu nhiên" → RCT).

### Bộ lọc `--topic-keywords` & `--show-low-relevance`
- Bài không chứa bất kỳ từ khóa topic nào sẽ được chuyển vào nhóm `low_relevance`.
- Dùng `--show-low-relevance` để xem nhóm này trong một bảng riêng (màu mờ hơn).
- Trong JSON output, chúng xuất hiện trong field `low_relevance_articles`.

---

*Plugin được phát triển và duy trì bởi Antigravity Agent — phiên bản 1.1.0*
