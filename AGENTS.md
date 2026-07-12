# VN-Med-Search Plugin Rules
- Khi kỹ năng (skill) `vn-med-search` được kích hoạt, LUÔN LUÔN tạo hoặc gọi subagent `vn-med-researcher` để thực hiện việc tìm kiếm.
- Tuyệt đối không chạy script `vn_med_search.py` trực tiếp trong terminal của cửa sổ chat chính.
- Bắt buộc phải thực hiện đủ 5 bước hỏi tuần tự (từ khóa, tác giả, năm, thiết kế, nguồn) theo Query Builder Protocol được định nghĩa trong `SKILL.md` trước khi bàn giao tác vụ cho subagent.
