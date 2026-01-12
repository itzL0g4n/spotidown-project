import os
import re
import shutil
import logging
import uuid
import time
import random
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
TEMP_WORK_DIR = os.path.join(DOWNLOAD_FOLDER, 'temp_workspace')

if not os.path.exists(DOWNLOAD_FOLDER): os.makedirs(DOWNLOAD_FOLDER)
if not os.path.exists(TEMP_WORK_DIR): os.makedirs(TEMP_WORK_DIR)

# --- QUẢN LÝ TÁC VỤ ---
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

# --- DỌN DẸP FILE CŨ ---
def cleanup_task():
    while True:
        try:
            now = time.time()
            for f in os.listdir(DOWNLOAD_FOLDER):
                p = os.path.join(DOWNLOAD_FOLDER, f)
                if f == 'temp_workspace': continue
                if now - os.path.getctime(p) > 3600:
                    if os.path.isfile(p): os.remove(p)
                    elif os.path.isdir(p): shutil.rmtree(p, ignore_errors=True)
            
            for f in os.listdir(TEMP_WORK_DIR):
                p = os.path.join(TEMP_WORK_DIR, f)
                if now - os.path.getctime(p) > 1800:
                    shutil.rmtree(p, ignore_errors=True)

            keys_to_remove = [k for k, v in download_tasks.items() if now - v.get('timestamp', 0) > 3600]
            for k in keys_to_remove:
                del download_tasks[k]
        except: pass
        time.sleep(600)

threading.Thread(target=cleanup_task, daemon=True).start()

def sanitize(n): return re.sub(r'[\\/*?:"<>|]', "", n).strip()

def get_all_tracks(sp_result, type='album'):
    tracks = []
    batch = sp_result['tracks'] if 'tracks' in sp_result else sp_result
    tracks.extend(batch['items'])
    while batch['next']:
        try:
            batch = sp.next(batch)
            tracks.extend(batch['items'])
        except: break
    return tracks

def get_meta(url):
    if not sp: raise Exception("No Spotify Key")
    if 'track' in url:
        t = sp.track(url)
        art = ", ".join([a['name'] for a in t['artists']])
        return {'type':'track', 'name':t['name'], 'artist':art, 'cover':t['album']['images'][0]['url'], 'tracks':[{'name':t['name'], 'artist':art}]}
    elif 'playlist' in url:
        p = sp.playlist(url)
        all_items = get_all_tracks(p, 'playlist')
        track_list = []
        for i in all_items:
            if i.get('track'):
                t_name = i['track']['name']
                t_art = ", ".join([a['name'] for a in i['track']['artists']])
                track_list.append({'name': t_name, 'artist': t_art})
        return {'type':'playlist', 'name':p['name'], 'cover':p['images'][0]['url'], 'tracks':track_list}
    elif 'album' in url:
        a = sp.album(url)
        all_items = get_all_tracks(a, 'album')
        track_list = []
        for t in all_items:
            t_name = t['name']
            t_art = ", ".join([ar['name'] for ar in t['artists']])
            track_list.append({'name': t_name, 'artist': t_art})
        return {'type':'album', 'name':a['name'], 'cover':a['images'][0]['url'], 'tracks':track_list}
    raise Exception("Link không hỗ trợ")

# --- ENGINE TẢI NHẠC (YOUTUBE WITH COOKIES) ---
def dl_engine(query, output_folder, final_name, meta_title, meta_artist):
    safe_name = sanitize(final_name)
    final_path = os.path.join(output_folder, f"{safe_name}.mp3")
    
    if os.path.exists(final_path): return final_path

    temp_id = str(uuid.uuid4())
    temp_dir = os.path.join(TEMP_WORK_DIR, f"temp_{temp_id}")
    os.makedirs(temp_dir, exist_ok=True)

    # Kiểm tra xem có file cookies.txt không
    cookie_file = 'cookies.txt'
    has_cookies = os.path.exists(cookie_file)
    
    if has_cookies:
        logging.info("🍪 Phát hiện cookies.txt! Sử dụng để xác thực YouTube.")
    else:
        logging.warning("⚠️ Không tìm thấy cookies.txt. Khả năng cao sẽ bị YouTube chặn (403).")

    # Chiến lược: Ưu tiên YouTube (vì nhạc chuẩn) -> Fallback SoundCloud
    strategies = [
        {'src': 'ytsearch1', 'name': 'YouTube'},
        {'src': 'scsearch1', 'name': 'SoundCloud'} 
    ]

    for strat in strategies:
        # Nếu là YouTube mà không có cookies thì vẫn thử (nhên xui), nhưng log cảnh báo
        
        for attempt in range(2):
            try:
                logging.info(f"🔎 Đang tìm '{query}' trên {strat['name']} (Lần {attempt+1})...")
                
                opts = {
                    'format': 'bestaudio/best',
                    'outtmpl': os.path.join(temp_dir, '%(title)s.%(ext)s'),
                    'default_search': strat['src'],
                    'postprocessors': [{'key': 'FFmpegExtractAudio','preferredcodec': 'mp3','preferredquality': '192'}],
                    'quiet': True, 'no_warnings': True, 'noplaylist': True,
                    'socket_timeout': 30,
                    'nocheckcertificate': True,
                }

                # QUAN TRỌNG: Nạp cookies nếu tìm trên YouTube
                if strat['src'] == 'ytsearch1' and has_cookies:
                    opts['cookiefile'] = cookie_file

                with yt_dlp.YoutubeDL(opts) as ydl:
                    ydl.download([query])

                files = [f for f in os.listdir(temp_dir) if f.endswith('.mp3')]
                if files:
                    shutil.move(os.path.join(temp_dir, files[0]), final_path)
                    try:
                        tag = EasyID3(final_path)
                        tag['title'] = meta_title
                        tag['artist'] = meta_artist
                        tag.save()
                    except: pass
                    shutil.rmtree(temp_dir, ignore_errors=True)
                    logging.info(f"✅ Thành công ({strat['name']}): {final_name}")
                    return final_path
            
            except Exception as e:
                logging.warning(f"⚠️ {strat['name']} Lỗi: {str(e)}")
                # Nếu lỗi Sign in required hoặc 403 mà đang dùng cookies -> Cookies hết hạn
                if "Sign in" in str(e) or "403" in str(e):
                    logging.error("❌ Cookies có thể đã hết hạn hoặc bị chặn.")
                time.sleep(3)
            
            shutil.rmtree(temp_dir, ignore_errors=True)
            os.makedirs(temp_dir, exist_ok=True)

    shutil.rmtree(temp_dir, ignore_errors=True)
    return None

# --- WORKER ---
def background_zip_worker(task_id, url):
    try:
        download_tasks[task_id]['status'] = 'processing'
        meta = get_meta(url)
        safe_album_name = sanitize(meta['name'])
        
        album_final_dir = os.path.join(DOWNLOAD_FOLDER, f"album_{task_id}")
        os.makedirs(album_final_dir, exist_ok=True)
        
        total = len(meta['tracks'])
        success_count = 0

        for idx, t in enumerate(meta['tracks']):
            download_tasks[task_id]['progress'] = f"Đang tải {idx + 1}/{total}: {t['name']}"
            download_tasks[task_id]['percent'] = int(((idx) / total) * 100)
            
            # Query đơn giản để YouTube tự tìm bản chuẩn nhất (Official Audio)
            query = f"{t['name']} {t['artist']} audio" 
            path = dl_engine(query, album_final_dir, f"{t['name']} - {t['artist']}", t['name'], t['artist'])
            
            if path: success_count += 1
            else: logging.error(f"❌ SKIPPED: {t['name']}")

            time.sleep(random.uniform(2, 4))

        if success_count == 0:
            download_tasks[task_id]['status'] = 'error'
            download_tasks[task_id]['error'] = 'Lỗi: Không tải được bài nào (Kiểm tra Cookies/IP).'
            shutil.rmtree(album_final_dir, ignore_errors=True)
            return

        download_tasks[task_id]['progress'] = 'Đang nén file ZIP...'
        zip_filename = f"{safe_album_name}.zip"
        zip_path = os.path.join(DOWNLOAD_FOLDER, zip_filename)
        
        shutil.make_archive(zip_path.replace('.zip', ''), 'zip', album_final_dir)
        shutil.rmtree(album_final_dir, ignore_errors=True)
        
        download_tasks[task_id]['status'] = 'completed'
        download_tasks[task_id]['percent'] = 100
        download_tasks[task_id]['download_url'] = f"/api/file/{zip_filename}"
        
    except Exception as e:
        download_tasks[task_id]['status'] = 'error'
        download_tasks[task_id]['error'] = str(e)
        try: shutil.rmtree(os.path.join(DOWNLOAD_FOLDER, f"album_{task_id}"), ignore_errors=True)
        except: pass

@app.route('/')
def idx(): return jsonify({"status":"YouTube (Cookies) Engine Ready"})

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

@app.route('/api/download_track', methods=['POST'])
def dl_track():
    try:
        url = request.json.get('url')
        meta = get_meta(url)
        t = meta['tracks'][0]
        path = dl_engine(f"{t['name']} {t['artist']} audio", DOWNLOAD_FOLDER, f"{t['name']} - {t['artist']}", t['name'], t['artist'])
        
        if not path: return jsonify({'error':'Không tìm thấy bài hát'}), 404
        
        return jsonify({
            "status": "success",
            "download_url": f"/api/file/{os.path.basename(path)}"
        })
    except Exception as e: return jsonify({'error':str(e)}), 500

@app.route('/api/start_zip', methods=['POST'])
def start_zip():
    url = request.json.get('url')
    task_id = str(uuid.uuid4())
    download_tasks[task_id] = {
        'status': 'queued',
        'progress': 'Đang chờ...',
        'percent': 0,
        'timestamp': time.time()
    }
    threading.Thread(target=background_zip_worker, args=(task_id, url)).start()
    return jsonify({'task_id': task_id})

@app.route('/api/status_zip/<task_id>', methods=['GET'])
def status_zip(task_id):
    task = download_tasks.get(task_id)
    if not task: return jsonify({'status': 'error', 'error': 'Task not found'}), 404
    return jsonify(task)

@app.route('/api/file/<path:filename>', methods=['GET'])
def get_file(filename):
    return send_file(os.path.join(DOWNLOAD_FOLDER, filename), as_attachment=True)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
