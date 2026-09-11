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

Plugin hiện hỗ trợ **12 nguồn dữ liệu học thuật y khoa** hàng đầu tại Việt Nam:

| Mã nguồn | Tên đầy đủ | Kiến trúc | Ghi chú & Đơn vị chủ quản |
|---|---|---|---|
| `tcncyh` | Tạp chí Nghiên cứu Y học | OJS2 | Đại học Y Hà Nội / Bộ Y tế |
| `vmj` | Tạp chí Y học Việt Nam | OJS2 | Tổng hội Y học Việt Nam |
| `bv108` | Tạp chí Y Dược Lâm sàng 108 | OJS2 | Bệnh viện Trung ương Quân đội 108 |
| `vnu` | Tạp chí Khoa học VNU (MPS, NST) | OJS3 | Đại học Quốc gia Hà Nội (Y Dược & KHTN) |
| `nlv-luanan` | Thư viện Quốc gia — Luận án | Scraping | Luận án Tiến sĩ, Thạc sĩ y dược |
| `vista` | VISTA STI — Cơ sở dữ liệu KH&CN | POST API | Cục Thông tin KH&CN Quốc gia |
| `jmp` | Tạp chí Y Dược Huế (lưu trữ) | Custom PHP | ĐH Y Dược Huế (lưu trữ các số 2011–2023) |
| `huejmp` | Tạp chí Y Dược Huế (mới) | OJS3 | ĐH Y Dược Huế (các số xuất bản từ 2023 đến nay) |
| `tcyhtphcm` | Tạp chí Y học TP. Hồ Chí Minh | Crossref API + Enrich | ĐH Y Dược TP.HCM (hơn 1.140 bài với DOI `10.32895`) |
| `medpharmres` | MedPharmRes | CMS Scraping | ĐH Y Dược TP.HCM (bài tiếng Anh, chuẩn quốc tế DOAJ) |
| `vjpm` | Tạp chí Y học Dự phòng | OJS3 | Hội Y học Dự phòng Việt Nam & Viện VSDTTW |
| `ctump` | Tạp chí Y Dược học Cần Thơ | OJS3 | Trường Đại học Y Dược Cần Thơ |



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

Agent: Nguồn ưu tiên? (tcncyh / vmj / bv108 / vnu / nlv-luanan / vista / jmp / huejmp / tcyhtphcm / medpharmres / vjpm / ctump, hoặc 'all')
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
| `--sources` | `TEXT` | `all` | Nguồn: `all`, hoặc phân tách dấu phẩy: `tcncyh`, `vmj`, `bv108`, `vnu`, `nlv-luanan`, `vista`, `jmp`, `huejmp`, `tcyhtphcm`, `medpharmres`, `vjpm`, `ctump` |
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

### 1. Tìm kiếm cơ bản trên tất cả các nguồn
```bash
uv run ... vn_med_search.py "đột quỵ" --sources all
```

### 2. Tìm kiếm chuyên sâu vắc xin & dịch tễ (Tạp chí Y học Dự phòng)
```bash
uv run ... vn_med_search.py "vắc xin" --sources vjpm --year 2022-2026 --json
```

### 3. Tìm kiếm y dược khu vực Đồng bằng sông Cửu Long (ĐH Y Dược Cần Thơ)
```bash
uv run ... vn_med_search.py "đái tháo đường" --sources ctump --max-results 10
```

### 4. Tìm kiếm trên các tạp chí miền Nam và miền Trung
```bash
# Tìm kiếm trên TCYH TP.HCM, Cần Thơ, MedPharmRes và Tạp chí Y Dược Huế
uv run ... vn_med_search.py "suy tim" --sources tcyhtphcm,ctump,medpharmres,huejmp,jmp
```

### 5. Tìm kiếm bài báo quốc tế tiếng Anh trên MedPharmRes
```bash
uv run ... vn_med_search.py "lung cancer" --sources medpharmres --year 2024-2026 --json
```

### 6. Lọc theo năm và nguồn
```bash
uv run ... vn_med_search.py "lấy huyết khối" --sources tcncyh,bv108 --year 2022-2026
```

### 5. Lọc độ liên quan — ẩn kết quả rác
```bash
# Chỉ hiện bài liên quan đến đột quỵ/thrombectomy (ẩn bài tim mạch không liên quan)
uv run ... vn_med_search.py "kháng tiểu cầu" \
  --topic-keywords "huyết khối,đột quỵ,stroke,não" --sources all --json
```

### 6. Hiển thị cả kết quả ít liên quan (2 bảng riêng)
```bash
uv run ... vn_med_search.py "kháng tiểu cầu" \
  --topic-keywords "huyết khối,đột quỵ" --show-low-relevance
```

### 7. Lọc theo thiết kế nghiên cứu
```bash
# Chỉ lấy thử nghiệm lâm sàng ngẫu nhiên
uv run ... vn_med_search.py "tim mạch" --study-type rct --year 2020-2026
```

---

## Kiến trúc kỹ thuật

```
┌─────────────────────────────────────────────────────────┐
│              Antigravity Agent (Cửa sổ chính)            │
│  • Nhận diện chủ đề người dùng                          │
│  • Thực hiện Query Builder Protocol 5 bước              │
│  • Khởi tạo subagent vn-med-researcher                  │
└────────────────────────────┬────────────────────────────┘
                             │ invoke_subagent
                             ▼
┌─────────────────────────────────────────────────────────┐
│             vn-med-researcher (Subagent)                │
│  • Phân rã từ khóa (Keyword Decomposition)              │
│  • Gọi CLI vn_med_search.py với cờ --json               │
│  • Deduplication theo tiêu đề chuẩn hóa                 │
│  • Trích xuất Title, Author, DOI, URL, PDF URL          │
│  • Báo cáo kết quả và thông báo độ liên quan            │
└────────────────────────────┬────────────────────────────┘
                             │ run_command
                             ▼
┌─────────────────────────────────────────────────────────┐
│               vn_med_search.py (CLI core)               │
│                                                         │
│ ┌───────────────┐ ┌───────────────┐ ┌─────────────────┐ │
│ │  OJSAdapter   │ │  VNUAdapter   │ │  VISTAAdapter   │ │
│ │  tcncyh, vmj  │ │  (OJS3)       │ │  (POST API)     │ │
│ │  bv108, huejmp│ │  MPS, NST     │ │  sti.vista      │ │
│ │  vjpm, ctump  │ │               │ │                 │ │
│ └───────┬───────┘ └───────┬───────┘ └────────┬────────┘ │
│         │                 │                  │          │
│ ┌───────┴───────┐ ┌───────┴───────┐ ┌────────┴────────┐ │
│ │JMPHueAdapter  │ │MedPharmResAdap│ │TCYHTHCMAdapter  │ │
│ │(PHP Scraping) │ │(CMS Scraping) │ │(Crossref REST + │ │
│ │jmp.huemed     │ │medpharmres.com│ │Detail Enrich)   │ │
│ └───────┬───────┘ └───────┬───────┘ └────────┬────────┘ │
│         │                 │                  │          │
│         └─────────────────┼──────────────────┘          │
│                           ▼                             │
│               NLVLuanAnAdapter (Scraping)               │
│               luanan.nlv.gov.vn                         │
│                                                         │
│  Pipeline: Fetch song song ──> Chuẩn hóa ──> Lọc Năm    │
│  ──> Lọc Tác giả ──> Lọc Thiết kế ──> Lọc Từ khóa Topic │
│  ──> JSON output / Bảng Rich Format                     │
└─────────────────────────────────────────────────────────┘
```

---

## Lưu ý kỹ thuật

### Tạp chí Y học Dự phòng (`vjpm`) & Tạp chí Y Dược học Cần Thơ (`ctump`)
- **`vjpm`** (`vjpm.vn`): Tạp chí của Hội Y học Dự phòng Việt Nam & Viện Vệ sinh Dịch tễ TW. Chạy nền tảng OJS 3.x với siêu dữ liệu chuẩn hóa (tóm tắt song ngữ, chỉ mục DOI `10.51403`, link tải PDF trực tiếp).
- **`ctump`** (`tapchi.ctump.edu.vn`): Tạp chí chính thức của Trường Đại học Y Dược Cần Thơ. Chạy OJS 3.x, bao phủ toàn diện nghiên cứu y dược lâm sàng và dịch tễ khu vực Đồng bằng sông Cửu Long.

### Tạp chí Y học TP.HCM (`tcyhtphcm`)
- Website chính (`tapchiyhoctphcm.vn`) sử dụng Google CSE nên chặn bot scraping trực tiếp (403 Forbidden), còn trang OJS chỉ phục vụ nộp bài nội bộ.
- Tạp chí đăng ký mã DOI chuẩn quốc tế dưới tiền tố **`10.32895`** trên hệ thống **Crossref** (>1.140 bài báo đã số hóa).
- `TCYHTHCMAdapter` truy vấn trực tiếp Crossref REST API để tìm kiếm nhanh chóng và chính xác, sau đó tự động crawl trang bài viết trên `tapchiyhoctphcm.vn` để trích xuất **Tóm tắt (Abstract)** và **Link tải PDF trực tiếp**.

### Tạp chí Y Dược Huế (`jmp` và `huejmp`)
- **`jmp`** (`jmp.huemed-univ.edu.vn`): Hệ thống PHP lưu trữ các bài báo giai đoạn **2011–2023**. Sử dụng POST request với trường `keywords` tới `search.php` và bóc tách metadata từ `article.php`.
- **`huejmp`** (`huejmp.vn/index.php/journal`): Hệ thống OJS 3.x chính thức xuất bản các số từ **2023 đến nay**, hỗ trợ abstract song ngữ và DOI.

### MedPharmRes (`medpharmres`)
- Ấn bản tiếng Anh của Đại học Y Dược TP.HCM, đã được chỉ mục trong **DOAJ** (Directory of Open Access Journals).
- Sử dụng search endpoint `/archive/list_search` và cung cấp link tải PDF trực tiếp từ `/download/download_pdf`.

### VNU Adapter (OJS3)
- VNU không dùng OJS2 mà dùng **OJS3** với URL search dạng `/<journal>/search/search`.
- Kết quả render trong `div.article-summary`, không phải thẻ `<a>` trực tiếp.
- Hiện tại tìm kiếm trên 2 tạp chí con: **MPS** (Y Dược) và **NST** (Khoa học Tự nhiên).

### VISTA STI
- Cổng VISTA yêu cầu gửi tham số định tuyến `mod` và `fun` dưới dạng **POST body** (`application/x-www-form-urlencoded`). Gửi GET hoặc POST query string sẽ bị báo lỗi `not found!`.

### Bộ lọc `--study-type`
- Vì các nguồn Việt Nam không gắn nhãn thiết kế nghiên cứu chuẩn, bộ lọc hoạt động bằng cách **tìm từ khóa** trong tiêu đề và abstract (ví dụ: "ngẫu nhiên" → RCT).

### Bộ lọc `--topic-keywords` & `--show-low-relevance`
- Bài không chứa bất kỳ từ khóa topic nào sẽ được chuyển vào nhóm `low_relevance`.
- Dùng `--show-low-relevance` để xem nhóm này trong một bảng riêng (màu mờ hơn).
- Trong JSON output, chúng xuất hiện trong field `low_relevance_articles`.

### SSL & Encoding
- Tất cả HTTP request đều dùng `verify=False` do nhiều server VN sử dụng chứng chỉ SSL nội bộ.
- Script cấu hình `sys.stdout.reconfigure(encoding='utf-8')` để xử lý tiếng Việt chính xác trên Windows console.

---

*Plugin được phát triển và duy trì bởi Antigravity Agent — Phiên bản 1.2.0*
