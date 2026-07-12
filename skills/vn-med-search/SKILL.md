---
name: vn-med-search
description: >-
  Fire this skill when the user asks to search, query, find, or retrieve medical literature,
  scientific publications, clinical trials, or academic theses published in Vietnam.
  Trigger when the user mentions Vietnamese medical journals, databases, or sources such as
  Tạp chí Nghiên cứu Y học (TCNCYH), Tạp chí Y học Việt Nam (VMJ), Tạp chí Y Dược Lâm sàng 108 (BV108),
  Tạp chí Khoa học VNU (VNU JS), Thư viện Quốc gia (NLV), or VISTA/STI.
---

# Vietnam Medical Literature Search Skill

Kỹ năng này điều phối việc tìm kiếm và trích xuất tài liệu y khoa Việt Nam bằng cách sử dụng Query Builder Protocol và ủy quyền cho subagent `vn-med-researcher`.

## Gotchas (Lưu ý quan trọng)

- **VISTA POST Routing**: Server VISTA chỉ chấp nhận định tuyến khi các tham số `mod` và `fun` được gửi dưới dạng **POST body parameters** (application/x-www-form-urlencoded) tới `https://sti.vista.gov.vn/index.php`. Gửi GET hoặc POST với query string sẽ trả về lỗi `not found!`.
- **NLV Document Suffixes**: URL luận án trên thư viện quốc gia chứa ID tài liệu ở parameter `d`. Cần tách bỏ các suffix trang (như `.1.1`) trước khi tải trang chi tiết.
- **Windows Encoding**: Môi trường Windows sử dụng mặc định ANSI, dễ gây lỗi in ký tự tiếng Việt ra stdout. Script CLI đã giải quyết bằng cách thiết lập stdout UTF-8.
- **Deduplication**: Kết quả từ nhiều nguồn được loại trùng dựa trên tiêu đề chuẩn hóa (chỉ giữ lại chữ cái và số dạng thường).
- **Study Type Parsing**: Do các nguồn trong nước không gắn nhãn loại nghiên cứu chuẩn, bộ lọc `--study-type` hoạt động bằng cách tìm kiếm từ khóa tương ứng trong tiêu đề và tóm tắt.

## Query Builder Protocol (Giao thức dựng truy vấn) — BẮT BUỘC

**ĐÂY LÀ QUY TRÌNH CỨNG. KHÔNG ĐƯỢC RÚT GỌN. KHÔNG ĐƯỢC GỘP CÂU HỎI.**

Trước khi thực hiện tìm kiếm, hỏi người dùng **tuần tự từng bước một** (chỉ gửi 1 câu hỏi, chờ trả lời, rồi mới hỏi câu tiếp theo):

1. **Bước 1** *(bắt buộc)*: Hỏi: *"Bạn muốn tìm kiếm về chủ đề gì?"*
2. **Bước 2** *(có thể bỏ qua)*: Hỏi: *"Bạn có muốn lọc theo tên tác giả cụ thể không? (Gõ tên hoặc 'không')"*
3. **Bước 3** *(có thể bỏ qua)*: Hỏi: *"Khoảng năm xuất bản? (Ví dụ: 2020-2025, hoặc 2023, hoặc 'không')"*
4. **Bước 4** *(có thể bỏ qua)*: Hỏi: *"Thiết kế nghiên cứu? (rct / systematic-review / case-report / cohort / mo-ta, hoặc 'không')"*
5. **Bước 5** *(có thể bỏ qua)*: Hỏi: *"Nguồn ưu tiên? (tcncyh / vmj / bv108 / vnu / nlv-luanan / vista, hoặc 'all')"*

**Quy tắc xử lý:**
- Nếu user nói "tìm ngay", "bỏ qua tất cả" → vẫn phải hỏi Bước 1 nếu chưa có chủ đề, sau đó tự điền mặc định cho Bước 2-5.
- Nếu user đã cung cấp chủ đề trong yêu cầu ban đầu → bỏ qua Bước 1, bắt đầu từ Bước 2.
- Mỗi câu trả lời "không" đồng nghĩa với không áp dụng bộ lọc đó.

Sau khi thu thập đủ 5 bước → biên dịch thành tham số CLI và gửi cho subagent `vn-med-researcher`.

## Xử lý kết quả nhận từ Subagent

Sau khi subagent trả báo cáo:
1. Trình bày kết quả liên quan cao trước.
2. Nếu JSON trả về có `total_low_relevance > 0`, hỏi user: *"Ngoài X kết quả trên, còn Y bài viết liên quan gián tiếp. Bạn có muốn xem không?"*
3. Nếu user đồng ý → yêu cầu subagent chạy lại với `--show-low-relevance`.

## CLI Usage (Cú pháp CLI dùng trong Subagent)

```bash
# Tìm kiếm cơ bản — LUÔN dùng --json để subagent parse kết quả
uv run --with httpx --with beautifulsoup4 --with typer --with rich \
  "C:\Users\Thinkpad T14 gen 2\.gemini\config\plugins\vn-med-search\skills\vn-med-search\scripts\vn_med_search.py" \
  "ung thư" --sources all --json

# Tìm kiếm với bộ lọc nâng cao
uv run ... vn_med_search.py "tim mạch" \
  --sources tcncyh,vista --year 2020-2025 --study-type rct --author "Nguyễn" --json

# Lọc độ liên quan theo chủ đề + hiển thị bài ít liên quan
uv run ... vn_med_search.py "kháng tiểu cầu" \
  --topic-keywords "huyết khối,đột quỵ,não" --show-low-relevance --json
```
