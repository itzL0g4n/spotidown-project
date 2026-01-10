import os
import re
import yt_dlp
import logging
import zipfile
import shutil
import time  # Thêm time để tránh race condition
from flask import Flask, render_template, request, jsonify, send_file, after_this_request
from mutagen.easyid3 import EasyID3
from mutagen.id3 import ID3, APIC, error as id3_error

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# Cấu hình thư mục download
DOWNLOAD_FOLDER = 'downloads'
if not os.path.exists(DOWNLOAD_FOLDER):
    os.makedirs(DOWNLOAD_FOLDER)

def sanitize_filename(name):
    """Làm sạch tên file để tránh lỗi hệ điều hành"""
    return re.sub(r'[\\/*?:"<>|]', "", name)

def find_downloaded_file(directory, video_id):
    """
    Tìm file trong thư mục chứa video_id.
    Giúp tránh lỗi FileNotFoundError khi yt-dlp đổi đuôi file hoặc đặt tên khác dự đoán.
    """
    if not os.path.exists(directory):
        return None
    
    # Đợi một chút để hệ thống file cập nhật (đôi khi cần thiết trên docker/network drive)
    time.sleep(0.5)
    
    for filename in os.listdir(directory):
        # Tìm file có chứa ID và là file âm thanh
        if video_id in filename and filename.lower().endswith(('.mp3', '.m4a', '.webm')):
            return os.path.join(directory, filename)
    return None

def download_audio(url, output_folder=DOWNLOAD_FOLDER, is_playlist=False):
    """Hàm tải nhạc xử lý cả bài đơn và playlist"""
    
    # 1. Lấy thông tin metadata trước (nhanh hơn tải)
    try:
        with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as e:
        logging.error(f"Lỗi lấy thông tin: {e}")
        return None, str(e)

    # Xử lý logic thư mục cho Playlist
    album_name = "Unknown Album"
    final_output_dir = output_folder
    
    if is_playlist and 'title' in info:
        album_name = sanitize_filename(info['title'])
        final_output_dir = os.path.join(output_folder, album_name)
        if not os.path.exists(final_output_dir):
            os.makedirs(final_output_dir)

    # Cấu hình yt-dlp
    ydl_opts = {
        'format': 'bestaudio/best',
        # Lưu tên file tạm là ID để dễ tìm kiếm bằng code sau này
        'outtmpl': os.path.join(final_output_dir, '%(id)s.%(ext)s'),
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'quiet': True,
        'no_warnings': True,
    }

    downloaded_files = []

    # Danh sách các mục cần tải (nếu là playlist thì info['entries'], nếu bài đơn thì là chính nó)
    entries = info['entries'] if 'entries' in info else [info]

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        for entry in entries:
            if not entry: continue
            
            video_id = entry.get('id')
            title = entry.get('title', 'Unknown Title')
            
            try:
                # Tải file
                ydl.download([entry['webpage_url']])
                
                # --- KHẮC PHỤC LỖI FILE NOT FOUND ---
                # Thay vì đoán đường dẫn, ta tìm file thực tế dựa trên ID
                temp_path = find_downloaded_file(final_output_dir, video_id)
                
                if not temp_path:
                    logging.error(f"Không tìm thấy file sau khi tải: ID {video_id}")
                    continue

                # Đường dẫn đích (Tên bài hát.mp3)
                safe_title = sanitize_filename(title)
                final_path = os.path.join(final_output_dir, f"{safe_title}.mp3")

                # Xử lý trường hợp file trùng tên
                counter = 1
                while os.path.exists(final_path):
                    final_path = os.path.join(final_output_dir, f"{safe_title} ({counter}).mp3")
                    counter += 1

                # Đổi tên file từ ID -> Title
                os.rename(temp_path, final_path)
                
                # Gắn Metadata (Cover art, Artist, Album)
                try:
                    audio = EasyID3(final_path)
                    audio['title'] = title
                    audio['artist'] = entry.get('artist', entry.get('uploader', 'Unknown Artist'))
                    audio['album'] = album_name if is_playlist else entry.get('album', 'Single')
                    audio.save()
                    logging.info(f"✅ Đã gắn thẻ: {final_path}")
                except Exception as meta_error:
                    # Nếu file chưa có ID3 tag, EasyID3 có thể lỗi, fallback sang ID3
                    try:
                        audio = ID3(final_path)
                        audio.add(APIC(encoding=3, mime='image/jpeg', type=3, desc='Cover', data=b'')) # Placeholder
                        audio.save()
                        logging.warning(f"⚠️ Dùng fallback ID3 cho: {final_path}")
                    except:
                        logging.error(f"⚠️ Lỗi gắn metadata: {meta_error}")

                downloaded_files.append(final_path)

            except Exception as e:
                logging.error(f"Lỗi khi xử lý bài {title}: {e}")
                continue

    return downloaded_files, album_name

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/download_single', methods=['POST'])
def api_download_single():
    data = request.json
    url = data.get('url')
    
    if not url:
        return jsonify({'error': 'Thiếu URL'}), 400

    try:
        files, _ = download_audio(url, is_playlist=False)
        if not files:
            return jsonify({'error': 'Không tải được file nào'}), 500
        
        file_path = files[0]
        filename = os.path.basename(file_path)

        # Xóa file sau khi gửi xong
        @after_this_request
        def remove_file(response):
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
            except Exception as e:
                app.logger.error(f"Lỗi xóa file tạm: {e}")
            return response

        return send_file(file_path, as_attachment=True, download_name=filename)

    except Exception as e:
        logging.error(f"API Error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/download_zip', methods=['POST'])
def api_download_zip():
    data = request.json
    url = data.get('url')

    if not url:
        return jsonify({'error': 'Thiếu URL'}), 400

    try:
        # Tải playlist
        files, album_name = download_audio(url, is_playlist=True)
        
        if not files:
            return jsonify({'error': 'Không tải được bài nào trong playlist'}), 500

        # Tạo file ZIP
        zip_filename = f"{sanitize_filename(album_name)}.zip"
        zip_path = os.path.join(DOWNLOAD_FOLDER, zip_filename)

        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file in files:
                # Thêm file vào zip với tên ngắn gọn (không bao gồm full path)
                zipf.write(file, arcname=os.path.basename(file))

        # Cleanup: Xóa thư mục album gốc sau khi zip
        album_dir = os.path.dirname(files[0])
        try:
            shutil.rmtree(album_dir) 
        except Exception as e:
            logging.warning(f"Không thể xóa thư mục tạm: {e}")

        # Gửi file ZIP
        @after_this_request
        def remove_zip(response):
            try:
                if os.path.exists(zip_path):
                    os.remove(zip_path)
            except Exception as e:
                app.logger.error(f"Lỗi xóa zip: {e}")
            return response

        return send_file(zip_path, as_attachment=True, download_name=zip_filename)

    except Exception as e:
        logging.error(f"ZIP API Error: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
