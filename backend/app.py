import os
import re
import shutil
import logging
import uuid
import time
import threading
import yt_dlp
from flask import Flask, request, jsonify, send_file
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

# --- GLOBAL TASKS DICTIONARY (Lưu trạng thái tải) ---
# Trong môi trường production thật nên dùng Redis, nhưng ở đây dùng biến toàn cục cho đơn giản
download_tasks = {} 

# --- CẤU HÌNH SPOTIFY ---
SPOTIPY_CLIENT_ID = os.environ.get('SPOTIPY_CLIENT_ID', '835be40df95f4ceb9cd48db5ab553e1e')
SPOTIPY_CLIENT_SECRET = os.environ.get('SPOTIPY_CLIENT_SECRET', '4ab634805b2a49dfa66550fccccaf7b4')

try:
    sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(client_id=SPOTIPY_CLIENT_ID, client_secret=SPOTIPY_CLIENT_SECRET))
    logging.info("✅ Spotify: Connected")
except:
    sp = None
    logging.warning("⚠️ Spotify: Disconnected")

# --- DỌN DẸP ---
def cleanup_task():
    while True:
        try:
            now = time.time()
            for f in os.listdir(DOWNLOAD_FOLDER):
                p = os.path.join(DOWNLOAD_FOLDER, f)
                # Xóa file zip/mp3 cũ quá 1 tiếng
                if now - os.path.getctime(p) > 3600: 
                    if os.path.isfile(p): os.remove(p)
                    elif os.path.isdir(p): shutil.rmtree(p, ignore_errors=True)
            
            # Xóa các task cũ trong bộ nhớ
            keys_to_del = [k for k, v in download_tasks.items() if now - v['timestamp'] > 3600]
            for k in keys_to_del: del download_tasks[k]
                
        except: pass
        time.sleep(600)
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
        return {'type':'album', 'name':a['name'], 'cover':a['images'][0]['url'], 'tracks':[{'name':t['name'], 'artist':", ".join([artist['name'] for artist in t['artists']])} for t in a['tracks']['items']]}
    raise Exception("Link không hỗ trợ")

def dl_sc(query, final_name, title, artist):
    safe_name = sanitize(final_name)
    final_path = os.path.join(DOWNLOAD_FOLDER, f"{safe_name}.mp3")
    
    if os.path.exists(final_path): return final_path

    temp_dir = os.path.join(DOWNLOAD_FOLDER, f"temp_{uuid.uuid4()}")
    os.makedirs(temp_dir, exist_ok=True)

    try:
        opts = {
            'format': 'bestaudio/best',
            'outtmpl': os.path.join(temp_dir, '%(title)s.%(ext)s'),
            'default_search': 'scsearch1',
            'postprocessors': [{'key': 'FFmpegExtractAudio','preferredcodec': 'mp3','preferredquality': '192'}],
            'quiet': True, 'no_warnings': True, 'noplaylist': True,
            'concurrent_fragment_downloads': 5,
        }
        
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([query])

        files = [f for f in os.listdir(temp_dir) if f.endswith('.mp3')]
        if not files: return None
        
        shutil.move(os.path.join(temp_dir, files[0]), final_path)
        
        try:
            tag = EasyID3(final_path)
            tag['title'] = title
            tag['artist'] = artist
            tag.save()
        except:
            try: ID3(final_path).save()
            except: pass
            
        return final_path
    except Exception as e:
        logging.error(f"DL Fail: {e}")
        return None
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

# --- BACKGROUND WORKER CHO ZIP ---
def process_zip_background(task_id, url):
    try:
        download_tasks[task_id]['status'] = 'processing'
        download_tasks[task_id]['progress'] = 'Đang lấy thông tin...'
        
        meta = get_meta(url)
        aname = sanitize(meta['name'])
        total_tracks = len(meta['tracks'])
        
        zip_temp = os.path.join(DOWNLOAD_FOLDER, f"zip_{task_id}")
        os.makedirs(zip_temp, exist_ok=True)

        cnt = 0
        for idx, t in enumerate(meta['tracks']):
            # Cập nhật tiến độ
            percent = int((idx / total_tracks) * 100)
            download_tasks[task_id]['progress'] = f"Đang tải {idx+1}/{total_tracks}: {t['name']}"
            download_tasks[task_id]['percent'] = percent
            
            p = dl_sc(f"{t['name']} {t['artist']}", f"{t['name']} - {t['artist']}", t['name'], t['artist'])
            if p:
                shutil.copy(p, os.path.join(zip_temp, os.path.basename(p)))
                cnt += 1
        
        if cnt == 0:
            download_tasks[task_id]['status'] = 'error'
            download_tasks[task_id]['error'] = 'Không tải được bài nào'
            shutil.rmtree(zip_temp, ignore_errors=True)
            return

        # Nén zip
        download_tasks[task_id]['progress'] = 'Đang nén file...'
        zpath = os.path.join(DOWNLOAD_FOLDER, f"{aname}.zip")
        shutil.make_archive(zpath.replace('.zip',''), 'zip', zip_temp)
        shutil.rmtree(zip_temp, ignore_errors=True)
        
        # Hoàn tất
        download_tasks[task_id]['status'] = 'completed'
        download_tasks[task_id]['filename'] = f"{aname}.zip"
        download_tasks[task_id]['progress'] = 'Hoàn tất!'
        download_tasks[task_id]['percent'] = 100
        
    except Exception as e:
        download_tasks[task_id]['status'] = 'error'
        download_tasks[task_id]['error'] = str(e)
        logging.error(f"Zip Task Error: {e}")

# --- API ROUTES ---

@app.route('/')
def idx(): return jsonify({"status":"SoundCloud Async Engine Ready"})

@app.route('/api/file/<path:filename>', methods=['GET'])
def get_file(filename):
    return send_file(os.path.join(DOWNLOAD_FOLDER, filename), as_attachment=True)

@app.route('/api/info', methods=['POST'])
def info():
    try:
        d = get_meta(request.json.get('url'))
        return jsonify(d)
    except Exception as e: return jsonify({'error':str(e)}), 500

@app.route('/api/download_track', methods=['POST'])
def dl_track():
    try:
        url = request.json.get('url')
        meta = get_meta(url)
        t = meta['tracks'][0]
        path = dl_sc(f"{t['name']} {t['artist']}", f"{t['name']} - {t['artist']}", t['name'], t['artist'])
        
        if not path: return jsonify({'error':'Không tìm thấy trên SoundCloud'}), 404
        
        filename = os.path.basename(path)
        return jsonify({ "status": "success", "download_url": f"/api/file/{filename}" })
    except Exception as e: return jsonify({'error':str(e)}), 500

# API MỚI: Bắt đầu tải Zip (Trả về Task ID)
@app.route('/api/start_zip', methods=['POST'])
def start_zip():
    task_id = str(uuid.uuid4())
    url = request.json.get('url')
    
    download_tasks[task_id] = {
        'status': 'queued',
        'progress': 'Đang hàng đợi...',
        'percent': 0,
        'timestamp': time.time()
    }
    
    # Chạy thread ngầm
    thread = threading.Thread(target=process_zip_background, args=(task_id, url))
    thread.start()
    
    return jsonify({'task_id': task_id})

# API MỚI: Kiểm tra trạng thái Task
@app.route('/api/status_zip/<task_id>', methods=['GET'])
def status_zip(task_id):
    task = download_tasks.get(task_id)
    if not task: return jsonify({'error': 'Task not found'}), 404
    
    response = {
        'status': task['status'],
        'progress': task.get('progress', ''),
        'percent': task.get('percent', 0)
    }
    
    if task['status'] == 'completed':
        response['download_url'] = f"/api/file/{task['filename']}"
    elif task['status'] == 'error':
        response['error'] = task.get('error', 'Unknown Error')
        
    return jsonify(response)

if __name__ == '__main__': app.run(host='0.0.0.0', port=5000, debug=True)
