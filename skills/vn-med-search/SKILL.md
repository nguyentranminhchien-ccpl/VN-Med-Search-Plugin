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

## Query Builder Protocol (Giao thức dựng truy vấn)

Trước khi thực hiện tìm kiếm, bạn **BẮT BUỘC** phải hỏi người dùng tuần tự từng bước để thu thập các bộ lọc (chỉ hỏi câu tiếp theo sau khi người dùng trả lời câu trước):

1. **Bước 1**: "Bạn muốn tìm kiếm về chủ đề gì?"
2. **Bước 2**: "Bạn có muốn lọc theo tên tác giả cụ thể không? (Bỏ qua: gõ 'không')"
3. **Bước 3**: "Khoảng năm xuất bản? (Ví dụ: 2020-2025, hoặc 2023, hoặc 'không')"
4. **Bước 4**: "Thiết kế nghiên cứu? (rct/systematic-review/case-report/cohort/mo-ta, hoặc 'không')"
5. **Bước 5**: "Nguồn ưu tiên? (tcncyh/vmj/bv108/nlv-luanan/vista, hoặc 'all')"

*Lưu ý:* Tuyệt đối không gộp 5 câu hỏi thành một tin nhắn duy nhất. Hãy hỏi lần lượt. Sau khi thu thập đủ, hãy biên dịch thành các tham số dòng lệnh và gửi cho subagent `vn-med-researcher` xử lý trong môi trường độc lập.

## CLI Usage (Cú pháp CLI dùng trong Subagent)

```bash
# Tìm kiếm cơ bản trên tất cả các nguồn
uv run scripts/vn_med_search.py "ung thư" --sources all

# Tìm kiếm nâng cao kết hợp bộ lọc
uv run scripts/vn_med_search.py "tim mạch" --sources tcncyh,vista --year 2020-2025 --study-type rct --author "Nguyễn"

# Trả về định dạng JSON
uv run scripts/vn_med_search.py "ung thư" --json
```
