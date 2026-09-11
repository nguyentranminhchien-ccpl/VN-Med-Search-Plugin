# VN-Med-Search Plugin Rules

## RULE 1 — Bắt buộc dùng subagent
- Khi kỹ năng `vn-med-search` được kích hoạt, LUÔN LUÔN gọi subagent `vn-med-researcher` để thực hiện tìm kiếm.
- Tuyệt đối không chạy script `vn_med_search.py` trực tiếp trong terminal của cửa sổ chat chính.

## RULE 2 — Bắt buộc hỏi tuần tự 5 bước (KHÔNG ĐƯỢC BỎ QUA)
- Trước khi gọi subagent, bạn PHẢI hỏi user tuần tự từng bước một theo Query Builder Protocol trong `SKILL.md`.
- **Nghiêm cấm** gộp nhiều câu hỏi vào cùng một tin nhắn.
- Nếu user gửi một yêu cầu tìm kiếm mà chưa trả lời đủ 5 bước, hãy bắt đầu ngay từ **Bước 1** và chờ user trả lời trước khi hỏi Bước 2.
- Ngay cả khi user nói "tìm kiếm ngay" hoặc "bỏ qua", bạn vẫn phải hỏi tuần tự; user có thể gõ "không" để bỏ qua từng bước một.

## RULE 3 — Xử lý kết quả sau khi nhận từ subagent
- Sau khi nhận báo cáo từ subagent, nếu có `total_low_relevance > 0`, hãy hỏi user:
  *"Ngoài X kết quả liên quan trực tiếp, còn có Y bài viết liên quan gián tiếp. Bạn có muốn xem không?"*
- Nếu user đồng ý, yêu cầu subagent chạy lại với flag `--show-low-relevance`.
