# 🎵 SpotiDown - Trình Tải Nhạc Spotify Chất Lượng Cao

**SpotiDown** là một ứng dụng web mã nguồn mở cho phép tải xuống các bài hát, album và danh sách phát (playlist) từ Spotify dưới định dạng MP3 (320kbps). Ứng dụng tự động tìm kiếm nguồn nhạc chất lượng cao từ YouTube (Official Audio), chuyển đổi và gắn đầy đủ thông tin (Metadata) như ảnh bìa, tên nghệ sĩ, album.

Vì Spotify đã cập nhật điều khoản cho nhà phát triển, nên từ nay bạn muốn lấy api Spotify sẽ cần có tài khoản premium.

Demo (frontend only) :[Here](https://spotidown-web-kyso.onrender.com/)
---

## ✨ Tính năng nổi bật

* 🚀 **Tốc độ cao:** Tải và chuyển đổi cực nhanh nhờ xử lý đa luồng.
* 🎧 **Chất lượng:** Hỗ trợ MP3 320kbps từ nguồn YouTube Official.
* 🍪 **Hỗ trợ Cookies:** Tích hợp cơ chế xác thực bằng Cookies để tránh lỗi chặn IP (403 Forbidden) từ YouTube.
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

## 🍪 Hướng dẫn cấu hình Cookies (QUAN TRỌNG)

Do YouTube thường chặn các request từ server hoặc IP lạ, bạn cần cung cấp Cookies để tải nhạc ổn định.

1. **Cài đặt Extension:** Tải **"Cookies Editor"** trên Chrome/Edge/Firefox.
2. **Đăng nhập YouTube:** Truy cập YouTube bằng một tài khoản Google phụ.
3. **Xuất file:** Mở extension và bấm **Export** dưới dạng Netscape để copy cookies.
4. **Cài đặt vào dự án:**
* **Cách 1 (Chạy Local):** Copy file `cookies.txt` (hãy tạo một cái nếu không có sẵn) vào thư mục `backend/` (ngang hàng với `app.py`).
* **Cách 2 (Deploy Render):** Copy nội dung file `cookies.txt` và dán vào biến môi trường (Environment Variable) tên là `COOKIES`.



---

## 🚀 Hướng dẫn chạy dự án (Local Deployment)

Để chạy dự án này trên máy cá nhân của bạn, hãy làm theo các bước sau:

### 1. Cài đặt Backend

```
cd backend
python -m venv .venv
# Kích hoạt venv (Windows: .venv\Scripts\activate | Mac: source .venv/bin/activate)
pip install -r requirements.txt

```

*Lưu ý: Nếu chưa có file requirements, bạn có thể cài thủ công: `pip install flask flask-cors yt-dlp spotipy requests mutagen gunicorn*`

**Cấu hình môi trường:**
Tạo file `.env` hoặc sửa trực tiếp trong `app.py`:

* `SPOTIPY_CLIENT_ID`: Key của bạn.
* `SPOTIPY_CLIENT_SECRET`: Secret của bạn.

### 2. Cài đặt Frontend (⚠️ QUAN TRỌNG: Sửa API URL)

Do mã nguồn gốc được cấu hình để chạy trên server test online của tôi, bạn cần chuyển nó về localhost để chạy trên máy mình. Nếu không, backend sẽ không chạy.

1. Cài đặt thư viện:
```
cd frontend
npm install

```


2. **Đổi đường dẫn API:**
* Tìm file `src/App.jsx` trong folder `frontend`
* Tìm tất cả các dòng chứa đường dẫn: `https://ten-du-an.onrender.com`
* **Đổi thành:** `http://localhost:5000`


*Ví dụ trong App.jsx:*
```
// TRƯỚC KHI SỬA
// const API_URL = "https://spotidown-project.onrender.com";

// SAU KHI SỬA (Chạy Local)
const API_URL = "http://localhost:5000";

```


3. Chạy Frontend (Cần cài đặt Vite):
```
npm run dev

```



### 3. Khởi chạy (Bạn sẽ cần phải mở 2 terminal cùng lúc để chạy song song backend và frontend)

* **Backend:** Chạy lệnh `python app.py` (Server sẽ chạy tại `http://localhost:5000`)
* **Frontend:** Truy cập `http://localhost:5173` để sử dụng.

---

## ⚠️ Lưu ý pháp lý (Disclaimer)

Dự án này được tạo ra với mục đích **học tập và nghiên cứu**. Tác giả không chịu trách nhiệm về việc sử dụng công cụ này để vi phạm bản quyền. Vui lòng tôn trọng nghệ sĩ và sử dụng các nền tảng chính thống để ủng hộ họ.
