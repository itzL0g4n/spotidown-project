import os
import re
import shutil
import logging
import uuid
import time
import threading
import yt_dlp
from flask import Flask, request, jsonify, send_file, after_this_request
from flask_cors import CORS
from mutagen.easyid3 import EasyID3
from mutagen.id3 import ID3

# Spotify
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials

app = Flask(__name__)
CORS(app)
logging.basicConfig(level=logging.INFO)

DOWNLOAD_FOLDER = 'downloads'
if not os.path.exists(DOWNLOAD_FOLDER): os.makedirs(DOWNLOAD_FOLDER)

# --- QUẢN LÝ TÁC VỤ (TASKS) ---
# Lưu trạng thái các file đang tải: { task_id: { status, progress, percent, filename... } }
download_tasks = {}

# --- CẤU HÌNH SPOTIFY ---
# Dùng key mặc định hoặc từ biến môi trường
SPOTIPY_CLIENT_ID = os.environ.get('SPOTIPY_CLIENT_ID', '835be40df95f4ceb9cd48db5ab553e1e')
SPOTIPY_CLIENT_SECRET = os.environ.get('SPOTIPY_CLIENT_SECRET', '4ab634805b2a49dfa66550fccccaf7b4')

try:
    sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(client_id=SPOTIPY_CLIENT_ID, client_secret=SPOTIPY_CLIENT_SECRET))
    logging.info("✅ Spotify: Connected")
except:
    sp = None
    logging.warning("⚠️ Spotify: Disconnected")

# --- DỌN DẸP FILE CŨ ---
def cleanup_task():
    while True:
        try:
            now = time.time()
            # Xóa file trong thư mục downloads
            for f in os.listdir(DOWNLOAD_FOLDER):
                p = os.path.join(DOWNLOAD_FOLDER, f)
                # Xóa file cũ hơn 1 tiếng
                if now - os.path.getctime(p) > 3600:
                    if os.path.isfile(p): os.remove(p)
                    elif os.path.isdir(p): shutil.rmtree(p, ignore_errors=True)
            
            # Xóa task rác trong bộ nhớ
            keys_to_remove = [k for k, v in download_tasks.items() if now - v.get('timestamp', 0) > 3600]
            for k in keys_to_remove:
                del download_tasks[k]
        except: pass
        time.sleep(600) # Quét mỗi 10 phút

threading.Thread(target=cleanup_task, daemon=True).start()

def sanitize(n): return re.sub(r'[\\/*?:"<>|]', "", n).strip()

def get_meta(url):
    if not sp: raise Exception("No Spotify Key")
    if 'track' in url:
        t = sp.track(url)
        art = ", ".join([a['name'] for a in t['artists']])
        return {'type':'track', 'name':t['name'], 'artist':art, 'cover':t['album']['images'][0]['url'], 'tracks':[{'name':t['name'], 'artist':art}]}
    elif 'playlist' in url:
        p = sp.playlist(url)
        return {'type':'playlist', 'name':p['name'], 'cover':p['images'][0]['url'], 'tracks':[{'name':i['track']['name'], 'artist':", ".join([a['name'] for a in i['track']['artists']])} for i in p['tracks']['items'] if i.get('track')]}
    elif 'album' in url:
        a = sp.album(url)
        return {'type':'album', 'name':a['name'], 'cover':a['images'][0]['url'], 'tracks':[{'name':t['name'], 'artist':", ".join([ar['name'] for ar in t['artists']])} for t in a['tracks']['items']]}
    raise Exception("Link không hỗ trợ")

def dl_sc_engine(query, output_folder, final_name, meta_title, meta_artist):
    """Hàm tải SoundCloud Engine"""
    safe_name = sanitize(final_name)
    final_path = os.path.join(output_folder, f"{safe_name}.mp3")
    
    if os.path.exists(final_path): return final_path

    # Tạo thư mục tạm riêng biệt cho bài này để tránh xung đột
    temp_id = str(uuid.uuid4())
    temp_dir = os.path.join(output_folder, f"temp_track_{temp_id}")
    os.makedirs(temp_dir, exist_ok=True)

    try:
        opts = {
            'format': 'bestaudio/best',
            'outtmpl': os.path.join(temp_dir, '%(title)s.%(ext)s'),
            'default_search': 'scsearch1', # SOUNDCLOUD SEARCH
            'postprocessors': [{'key': 'FFmpegExtractAudio','preferredcodec': 'mp3','preferredquality': '192'}],
            'quiet': True, 'no_warnings': True, 'noplaylist': True,
        }
        
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([query])

        files = [f for f in os.listdir(temp_dir) if f.endswith('.mp3')]
        if not files: return None
        
        # Di chuyển ra thư mục đích
        shutil.move(os.path.join(temp_dir, files[0]), final_path)
        
        # Gắn thẻ
        try:
            tag = EasyID3(final_path)
            tag['title'] = meta_title
            tag['artist'] = meta_artist
            tag.save()
        except:
            try: ID3(final_path).save()
            except: pass
            
        return final_path
    except Exception as e:
        print(f"Lỗi tải track {query}: {e}")
        return None
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

# --- WORKER: XỬ LÝ ZIP CHẠY NGẦM ---
def background_zip_worker(task_id, url):
    try:
        download_tasks[task_id]['status'] = 'processing'
        
        # 1. Lấy thông tin
        meta = get_meta(url)
        safe_album_name = sanitize(meta['name'])
        
        # 2. Tạo thư mục gom file cho Album này
        album_temp_dir = os.path.join(DOWNLOAD_FOLDER, f"album_{task_id}")
        os.makedirs(album_temp_dir, exist_ok=True)
        
        total = len(meta['tracks'])
        success_count = 0

        # 3. Duyệt và tải từng bài
        for idx, t in enumerate(meta['tracks']):
            # Cập nhật tiến độ cho Frontend
            percent = int(((idx) / total) * 100)
            download_tasks[task_id]['progress'] = f"Đang tải bài {idx + 1}/{total}: {t['name']}"
            download_tasks[task_id]['percent'] = percent
            
            # Logic tìm kiếm SoundCloud
            query = f"{t['name']} {t['artist']}"
            # Tải vào folder album
            path = dl_sc_engine(query, album_temp_dir, f"{t['name']} - {t['artist']}", t['name'], t['artist'])
            
            if path: success_count += 1

        if success_count == 0:
            download_tasks[task_id]['status'] = 'error'
            download_tasks[task_id]['error'] = 'Không tải được bài nào từ SoundCloud'
            shutil.rmtree(album_temp_dir, ignore_errors=True)
            return

        # 4. Nén Zip
        download_tasks[task_id]['progress'] = 'Đang nén file ZIP...'
        download_tasks[task_id]['percent'] = 99
        
        zip_filename = f"{safe_album_name}.zip"
        zip_path = os.path.join(DOWNLOAD_FOLDER, zip_filename)
        
        # Tạo zip từ thư mục album
        shutil.make_archive(zip_path.replace('.zip', ''), 'zip', album_temp_dir)
        
        # Xóa thư mục album thô
        shutil.rmtree(album_temp_dir, ignore_errors=True)
        
        # 5. Hoàn tất
        download_tasks[task_id]['status'] = 'completed'
        download_tasks[task_id]['percent'] = 100
        download_tasks[task_id]['download_url'] = f"/api/file/{zip_filename}"
        
    except Exception as e:
        download_tasks[task_id]['status'] = 'error'
        download_tasks[task_id]['error'] = str(e)
        # Dọn dẹp nếu lỗi
        try: shutil.rmtree(os.path.join(DOWNLOAD_FOLDER, f"album_{task_id}"), ignore_errors=True)
        except: pass

# --- ROUTES ---

@app.route('/')
def idx(): return jsonify({"status":"Async SoundCloud Engine Ready"})

# 1. API Lấy thông tin (Metadata)
@app.route('/api/info', methods=['POST'])
def info():
    try:
        d = get_meta(request.json.get('url'))
        return jsonify({
            'type': d['type'],
            'name': d['name'],
            'artist': d.get('artist', ''),
            'cover': d.get('cover', ''),
            'tracks': [{'id': i, 'name': t['name'], 'artist': t['artist'], 'cover': d.get('cover')} 
                       for i, t in enumerate(d['tracks'])]
        })
    except Exception as e: return jsonify({'error':str(e)}), 500

# 2. API Tải bài lẻ (Vẫn dùng sync vì nhanh)
@app.route('/api/download_track', methods=['POST'])
def dl_track():
    try:
        url = request.json.get('url')
        meta = get_meta(url)
        t = meta['tracks'][0]
        # Query: Tên + Nghệ sĩ
        path = dl_sc_engine(f"{t['name']} {t['artist']}", DOWNLOAD_FOLDER, f"{t['name']} - {t['artist']}", t['name'], t['artist'])
        
        if not path: return jsonify({'error':'Không tìm thấy trên SoundCloud'}), 404
        
        return jsonify({
            "status": "success",
            "download_url": f"/api/file/{os.path.basename(path)}"
        })
    except Exception as e: return jsonify({'error':str(e)}), 500

# 3. API BẮT ĐẦU TẢI ZIP (Async - Trả về Task ID ngay lập tức)
@app.route('/api/start_zip', methods=['POST'])
def start_zip():
    url = request.json.get('url')
    task_id = str(uuid.uuid4())
    
    # Khởi tạo task
    download_tasks[task_id] = {
        'status': 'queued',
        'progress': 'Đang chờ xử lý...',
        'percent': 0,
        'timestamp': time.time()
    }
    
    # Chạy thread ngầm để không block request
    thread = threading.Thread(target=background_zip_worker, args=(task_id, url))
    thread.start()
    
    return jsonify({'task_id': task_id})

# 4. API KIỂM TRA TRẠNG THÁI ZIP (Polling)
@app.route('/api/status_zip/<task_id>', methods=['GET'])
def status_zip(task_id):
    task = download_tasks.get(task_id)
    if not task: return jsonify({'status': 'error', 'error': 'Task not found'}), 404
    return jsonify(task)

# 5. API Tải file về
@app.route('/api/file/<path:filename>', methods=['GET'])
def get_file(filename):
    return send_file(os.path.join(DOWNLOAD_FOLDER, filename), as_attachment=True)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
