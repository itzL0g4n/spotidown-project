# 🎵 SpotiDown - Trình Tải Nhạc Spotify Chất Lượng Cao

**SpotiDown** là một ứng dụng web mã nguồn mở cho phép tải xuống các bài hát, album và danh sách phát (playlist) từ Spotify dưới định dạng MP3 (320kbps). Ứng dụng tự động tìm kiếm nguồn nhạc chất lượng cao từ YouTube, chuyển đổi và gắn đầy đủ thông tin (Metadata) như ảnh bìa, tên nghệ sĩ, album.

---

## ✨ Tính năng nổi bật

* 🚀 **Tốc độ cao:** Tải và chuyển đổi cực nhanh nhờ xử lý đa luồng.
* 🎧 **Chất lượng:** Hỗ trợ MP3 320kbps.
* 🖼️ **Full Metadata:** Tự động gắn ảnh bìa (Cover Art), tên bài hát, ca sĩ, album vào file tải về.
* 📦 **Hỗ trợ Playlist & Album:** Tải trọn bộ danh sách phát và tự động nén thành file `.zip`.
* 🎨 **Giao diện hiện đại:** Thiết kế Glassmorphism, hiệu ứng sóng nhạc sống động.
* 🧹 **Tự động dọn dẹp:** Hệ thống tự động xóa file tạm sau 30 phút để tiết kiệm dung lượng.

---

## 🛠️ Công nghệ sử dụng

### Frontend (Giao diện)
* **ReactJS (Vite)**
* **Tailwind CSS**
* **Lucide React Icons**

### Backend (Máy chủ)
* **Python (Flask)**
* **yt-dlp**: Tải nguồn nhạc từ YouTube.
* **FFmpeg**: Chuyển đổi định dạng âm thanh.
* **Spotipy**: Kết nối Spotify API.
* **Mutagen**: Gắn metadata (ID3 tags).

---

## ⚙️ Yêu cầu cài đặt (Prerequisites)

1. **Node.js** (v16+)
2. **Python** (v3.8+)
3. **FFmpeg**: Phải được cài đặt và thêm vào PATH hệ thống.
4. **Spotify API Credentials**: Lấy tại [Spotify Developer Dashboard](https://developer.spotify.com/dashboard).

---

## 🚀 Hướng dẫn chạy dự án (Local Deployment)

### 1. Cài đặt Backend
```bash
cd backend
python -m venv .venv
# Kích hoạt venv (Windows: .venv\Scripts\activate | Mac: source .venv/bin/activate)
pip install flask flask-cors yt-dlp spotipy requests mutagen gunicorn

```

*Lưu ý: Điền Client ID và Secret của bạn vào file `app.py`.*

### 2. Cài đặt Frontend

```bash
cd frontend
npm install
npm run dev

```

### 3. Khởi chạy

* Backend chạy tại: `http://localhost:5000`
* Frontend chạy tại: `http://localhost:5173`

---

## ⚠️ Lưu ý pháp lý (Disclaimer)

Dự án này được tạo ra với mục đích **học tập và nghiên cứu**. Tác giả không chịu trách nhiệm về việc sử dụng công cụ này để vi phạm bản quyền. Vui lòng tôn trọng nghệ sĩ và sử dụng các nền tảng chính thống để ủng hộ họ.

