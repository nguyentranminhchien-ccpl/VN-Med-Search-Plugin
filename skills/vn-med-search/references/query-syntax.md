# VN-Med Query Syntax & PubMed Mapping

Tài liệu này hướng dẫn cách ánh xạ các tham số tìm kiếm tài liệu Y học từ chuẩn PubMed sang cú pháp CLI của plugin `vn-med-search`.

---

## 1. Bảng Ánh xạ Tham số (PubMed ↔ VN-Med CLI)

Khi người dùng đưa ra yêu cầu tìm kiếm dạng PubMed (ví dụ: `ung thư[tiab] AND Nguyễn[au] AND 2022:2024[dp]`), bạn cần phân tích các trường này và gán vào các cờ CLI tương ứng:

| Tiêu chí | Cú pháp PubMed | Cờ CLI VN-Med | Ví dụ sử dụng CLI |
| :--- | :--- | :--- | :--- |
| **Từ khóa chính** | `keyword[tiab]` or `keyword` | Đối số vị trí đầu tiên | `"ung thư phổi"` |
| **Tên tác giả** | `author_name[au]` | `--author "author_name"` | `--author "Nguyễn Văn A"` |
| **Năm xuất bản** | `YYYY[dp]` or `YYYY:YYYY[dp]` | `--year "YYYY"` or `--year "YYYY-YYYY"` | `--year 2023`, `--year 2020-2025` |
| **Thiết kế nghiên cứu**| `study_design[pt]` | `--study-type "study_design"` | `--study-type rct`, `--study-type systematic-review` |
| **Nguồn dữ liệu** | `journal_name[ta]` | `--sources "source_list"` | `--sources tcncyh,vista`, `--sources ojs` |

---

## 2. Thiết kế nghiên cứu hỗ trợ (Study Type Keyword mapping)

Vì các cơ sở dữ liệu Việt Nam thường không lưu trữ trường phân loại thiết kế nghiên cứu (Publication Type), hệ thống thực hiện lọc bài viết sau khi cào (post-filtering) bằng cách đối chiếu tiêu đề và tóm tắt với các bộ từ khóa tương ứng:

- **rct** / **clinical-trial**:
  - *Bộ từ khóa*: `thử nghiệm lâm sàng ngẫu nhiên`, `clinical trial`, `ngẫu nhiên có đối chứng`, `rct`, `thử nghiệm lâm sàng`, `ngẫu nhiên`
- **systematic-review** / **meta-analysis**:
  - *Bộ từ khóa*: `tổng quan hệ thống`, `systematic review`, `meta-analysis`, `tổng quan`, `phân tích gộp`, `phân tích hệ thống`
- **case-report**:
  - *Bộ từ khóa*: `báo cáo ca bệnh`, `case report`, `báo cáo lâm sàng`, `ca bệnh`, `báo cáo trường hợp`
- **cohort**:
  - *Bộ từ khóa*: `đoàn hệ`, `cohort`, `nghiên cứu đoàn hệ`, `theo dõi dọc`
- **mo-ta** / **descriptive**:
  - *Bộ từ khóa*: `mô tả`, `cắt ngang`, `cross-sectional`, `descriptive`, `nghiên cứu mô tả`
