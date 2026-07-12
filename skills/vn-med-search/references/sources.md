# Vietnamese Medical Literature Sources

Tài liệu này chi tiết cấu trúc kỹ thuật và thông số của các nguồn tài liệu y khoa Việt Nam được tích hợp trong hệ thống.

---

## 1. Hệ thống tạp chí OJS (Open Journal Systems)

### Các Tạp chí hỗ trợ:
- **Tạp chí Nghiên cứu Y học (TCNCYH)**: `https://tapchinghiencuuyhoc.vn/index.php/tcncyh`
- **Tạp chí Y học Việt Nam (VMJ)**: `https://tapchiyhocvietnam.vn/index.php/vmj`
- **Tạp chí Y Dược Lâm sàng 108 (BV108)**: `https://tcydls108.benhvien108.vn/index.php/YDLS`
- **Tạp chí Khoa học VNU (VNU JS)**: `https://js.vnu.edu.vn`

### Cơ chế hoạt động:
- **Search URL**: `{base_url}/search/search?query={keyword}`
- **Metadata parsing**: Trang chi tiết bài báo có các thẻ meta Dublin Core chuẩn hóa được OJS tự động kết xuất:
  - `citation_title` / `DC.Title`: Tiêu đề bài viết
  - `citation_author` / `DC.Creator.PersonalName`: Tác giả (hỗ trợ nhiều thẻ nếu nhiều tác giả)
  - `DC.Description`: Tóm tắt abstract (thường có cả tiếng Anh và tiếng Việt)
  - `citation_journal_title` / `DC.Source`: Tên tạp chí/nguồn trích dẫn
  - `citation_date` / `DC.Date.issued`: Ngày/Năm xuất bản
  - `citation_doi` / `DC.Identifier.DOI`: Mã định danh số DOI
  - `citation_pdf_url`: Liên kết trực tiếp tới file PDF

---

## 2. Luận án Tiến sĩ - Thư viện Quốc gia Việt Nam (NLV)

- **Search URL**: `https://luanan.nlv.gov.vn/luanan?a=q&hs=1&r=1&results=1&txf=txIN&leq=Primary&txq={keyword}&e=-------vi-20--1--img-txIN-------`
- **Cơ chế trích xuất**:
  - Phân tích mã nguồn HTML để lấy liên kết chi tiết có dạng: `?a=d&d={doc_id}`
  - Truy cập trang chi tiết luận án, duyệt qua các thẻ `<div>` để tìm các khối nhãn như `Tên luận án`, `Tác giả`, `Năm xuất bản`, `Tóm tắt`.
  - **Lưu ý**: NLV xem luận án dưới dạng các file ảnh quét tuần tự, không hỗ trợ liên kết tải trực tiếp PDF toàn văn.

---

## 3. Cơ sở dữ liệu VISTA STI (Bộ KH&CN)

- **Endpoint**: `https://sti.vista.gov.vn/index.php`
- **Cơ chế POST**:
  - Gửi POST request với kiểu `application/x-www-form-urlencoded`.
  - Body payload:
    ```json
    {
      "mod": "publication",
      "fun": "getlist",
      "keyword": "{keyword}",
      "page": 1,
      "limit": 10,
      "field": "all",
      "is_fulltext": 0
    }
    ```
  - Phân tích bảng kết quả HTML trả về để trích xuất các ID tài liệu qua thuộc tính `onclick="ViewDoc('{id}')"` trên các thẻ liên kết.
  - Truy cập trang chi tiết: `https://sti.vista.gov.vn/modules/publication/expansion/ViewDoc.php?id={id}` để lấy Metadata.
