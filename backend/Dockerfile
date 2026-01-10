# Sử dụng Python 3.9
    FROM python:3.9-slim

    # Cài đặt FFmpeg (Bắt buộc để xử lý nhạc)
    RUN apt-get update && apt-get install -y ffmpeg && apt-get clean

    # Thiết lập thư mục làm việc
    WORKDIR /app

    # Copy file requirements và cài thư viện
    COPY requirements.txt .
    RUN pip install --no-cache-dir -r requirements.txt

    # Copy toàn bộ code vào
    COPY . .

    # Tạo thư mục downloads để tránh lỗi permission
    RUN mkdir -p downloads && chmod 777 downloads

    # Mở cổng 10000 (Cổng mặc định của Render)
    EXPOSE 10000

    # Lệnh chạy server với Gunicorn (Production server)
    CMD ["gunicorn", "--bind", "0.0.0.0:10000", "--timeout", "120", "app:app"]