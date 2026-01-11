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

# --- CẤU HÌNH SPOTIFY ---
# Thay bằng Key của bạn nếu cần, hoặc để mặc định để test fallback (có thể bị giới hạn)
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
                if os.path.isfile(p) and now - os.path.getctime(p) > 3600: os.remove(p) # 1h
                elif os.path.isdir(p) and f.startswith("temp_"): shutil.rmtree(p, ignore_errors=True)
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
        return {'type':'album', 'name':a['name'], 'cover':a['images'][0]['url'], 'tracks':[{'name':t['name'], 'artist':", ".join([ar['name'] for ar in t['artists']])} for t in a['tracks']['items']]}
    raise Exception("Link không hỗ trợ")

def dl_sc(query, final_name, title, artist):
    """Tải từ SoundCloud dùng thư mục tạm UUID để đảm bảo 100% bắt được file"""
    safe_name = sanitize(final_name)
    final_path = os.path.join(DOWNLOAD_FOLDER, f"{safe_name}.mp3")
    
    # 1. Cache Hit
    if os.path.exists(final_path): return final_path

    # 2. Tạo folder tạm riêng biệt
    temp_dir = os.path.join(DOWNLOAD_FOLDER, f"temp_{uuid.uuid4()}")
    os.makedirs(temp_dir, exist_ok=True)

    try:
        opts = {
            'format': 'bestaudio/best',
            'outtmpl': os.path.join(temp_dir, '%(title)s.%(ext)s'), # Tên gốc không quan trọng
            'default_search': 'scsearch1', # SOUNDCLOUD ONLY
            'postprocessors': [{'key': 'FFmpegExtractAudio','preferredcodec': 'mp3','preferredquality': '192'}],
            'quiet': True, 'no_warnings': True, 'noplaylist': True,
        }
        
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([query])

        # 3. Tìm file MP3 bất kỳ trong folder tạm
        files = [f for f in os.listdir(temp_dir) if f.endswith('.mp3')]
        if not files: return None
        
        # 4. Di chuyển và gắn thẻ
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

# --- API ---
@app.route('/')
def idx(): return jsonify({"status":"SoundCloud Engine Ready"})

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
        # Query không dùng chữ 'audio' với SC để chính xác hơn
        path = dl_sc(f"{t['name']} {t['artist']}", f"{t['name']} - {t['artist']}", t['name'], t['artist'])
        
        if not path: return jsonify({'error':'Không tìm thấy trên SoundCloud'}), 404
        return send_file(path, as_attachment=True, download_name=os.path.basename(path))
    except Exception as e: return jsonify({'error':str(e)}), 500

@app.route('/api/download_zip', methods=['POST'])
def dl_zip():
    try:
        url = request.json.get('url')
        meta = get_meta(url)
        aname = sanitize(meta['name'])
        
        # Folder tạm để gom file zip
        zip_temp = os.path.join(DOWNLOAD_FOLDER, f"zip_{uuid.uuid4()}")
        os.makedirs(zip_temp, exist_ok=True)

        cnt = 0
        for t in meta['tracks']:
            p = dl_sc(f"{t['name']} {t['artist']}", f"{t['name']} - {t['artist']}", t['name'], t['artist'])
            if p:
                shutil.copy(p, os.path.join(zip_temp, os.path.basename(p)))
                cnt += 1
        
        if cnt == 0: 
            shutil.rmtree(zip_temp)
            return jsonify({'error':'Empty Playlist'}), 404

        zpath = os.path.join(DOWNLOAD_FOLDER, f"{aname}.zip")
        shutil.make_archive(zpath.replace('.zip',''), 'zip', zip_temp)
        shutil.rmtree(zip_temp)

        @after_this_request
        def cl(r): 
            try: os.remove(zpath)
            except: pass
            return r
            
        return send_file(zpath, as_attachment=True, download_name=f"{aname}.zip")
    except Exception as e: return jsonify({'error':str(e)}), 500

if __name__ == '__main__': app.run(host='0.0.0.0', port=5000, debug=True)
