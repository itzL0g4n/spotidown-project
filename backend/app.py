import os
import re
import yt_dlp
import logging
import zipfile
import shutil
import time
from flask import Flask, request, jsonify, send_file, after_this_request
from flask_cors import CORS
from mutagen.easyid3 import EasyID3
from mutagen.id3 import ID3, APIC

app = Flask(__name__)
# Cho phép CORS để React (chạy port khác) có thể gọi API
CORS(app)

logging.basicConfig(level=logging.INFO)

DOWNLOAD_FOLDER = 'downloads'
if not os.path.exists(DOWNLOAD_FOLDER):
    os.makedirs(DOWNLOAD_FOLDER)

def sanitize_filename(name):
    """Làm sạch tên file để tránh lỗi hệ điều hành"""
    return re.sub(r'[\\/*?:"<>|]', "", name)

def find_downloaded_file(directory, video_id):
    """
    Tìm file trong thư mục chứa video_id.
    Khắc phục lỗi yt-dlp đổi tên file khác với dự đoán.
    """
    if not os.path.exists(directory):
        return None
    
    time.sleep(0.5) # Đợi hệ thống file cập nhật
    
    for filename in os.listdir(directory):
        # Tìm file có chứa ID và là file âm thanh
        if video_id in filename and filename.lower().endswith(('.mp3', '.m4a', '.webm')):
            return os.path.join(directory, filename)
    return None

def download_audio(url, output_folder=DOWNLOAD_FOLDER, is_playlist=False):
    try:
        # Lấy thông tin trước
        with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as e:
        return None, str(e)

    album_name = "Unknown Album"
    final_output_dir = output_folder
    
    if is_playlist and 'title' in info:
        album_name = sanitize_filename(info['title'])
        final_output_dir = os.path.join(output_folder, album_name)
        if not os.path.exists(final_output_dir):
            os.makedirs(final_output_dir)

    ydl_opts = {
        'format': 'bestaudio/best',
        # Lưu tên tạm là ID để dễ tìm
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
    # Xử lý danh sách entries
    if 'entries' in info:
        entries = info['entries']
    else:
        entries = [info]

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        for entry in entries:
            if not entry: continue
            
            video_id = entry.get('id')
            title = entry.get('title', 'Unknown Title')
            
            try:
                ydl.download([entry['webpage_url']])
                
                # Logic tìm file chính xác
                temp_path = find_downloaded_file(final_output_dir, video_id)
                
                if not temp_path:
                    logging.error(f"Không tìm thấy file ID: {video_id}")
                    continue

                safe_title = sanitize_filename(title)
                final_path = os.path.join(final_output_dir, f"{safe_title}.mp3")

                counter = 1
                while os.path.exists(final_path):
                    final_path = os.path.join(final_output_dir, f"{safe_title} ({counter}).mp3")
                    counter += 1

                os.rename(temp_path, final_path)
                
                # Gắn Metadata
                try:
                    audio = EasyID3(final_path)
                    audio['title'] = title
                    audio['artist'] = entry.get('artist', entry.get('uploader', 'Unknown Artist'))
                    audio['album'] = album_name if is_playlist else entry.get('album', 'Single')
                    audio.save()
                except Exception:
                    # Fallback nếu file chưa có tag ID3
                    try:
                        audio = ID3(final_path)
                        audio.add(APIC(encoding=3, mime='image/jpeg', type=3, desc='Cover', data=b''))
                        audio.save()
                    except:
                        pass

                downloaded_files.append(final_path)

            except Exception as e:
                logging.error(f"Lỗi bài {title}: {e}")
                continue

    return downloaded_files, album_name

# --- SỬA LỖI TẠI ĐÂY ---
# Thay vì render_template, chỉ trả về thông báo JSON
@app.route('/')
def index():
    return jsonify({
        "status": "online", 
        "message": "SpotiDown Backend is running. Please use the React Frontend to interact."
    })

@app.route('/api/download_single', methods=['POST'])
def api_download_single():
    data = request.json
    url = data.get('url')
    if not url: return jsonify({'error': 'Thiếu URL'}), 400

    try:
        files, _ = download_audio(url, is_playlist=False)
        if not files: return jsonify({'error': 'Lỗi tải file'}), 500
        
        file_path = files[0]
        filename = os.path.basename(file_path)

        @after_this_request
        def remove_file(response):
            try:
                if os.path.exists(file_path): os.remove(file_path)
            except: pass
            return response

        return send_file(file_path, as_attachment=True, download_name=filename)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/download_zip', methods=['POST'])
def api_download_zip():
    data = request.json
    url = data.get('url')
    if not url: return jsonify({'error': 'Thiếu URL'}), 400

    try:
        files, album_name = download_audio(url, is_playlist=True)
        if not files: return jsonify({'error': 'Playlist rỗng hoặc lỗi'}), 500

        zip_filename = f"{sanitize_filename(album_name)}.zip"
        zip_path = os.path.join(DOWNLOAD_FOLDER, zip_filename)

        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file in files:
                zipf.write(file, arcname=os.path.basename(file))

        # Xóa thư mục tạm
        try:
            shutil.rmtree(os.path.dirname(files[0]))
        except: pass

        @after_this_request
        def remove_zip(response):
            try:
                if os.path.exists(zip_path): os.remove(zip_path)
            except: pass
            return response

        return send_file(zip_path, as_attachment=True, download_name=zip_filename)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # Chạy trên 0.0.0.0 để container/network có thể truy cập
    app.run(host='0.0.0.0', port=5000, debug=True)
