import os
import re
import shutil
import logging
import yt_dlp
from flask import Flask, request, jsonify, send_file, after_this_request
from flask_cors import CORS
from mutagen.easyid3 import EasyID3
from mutagen.id3 import ID3

# Import Spotify
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials

app = Flask(__name__)
CORS(app)
logging.basicConfig(level=logging.INFO)

DOWNLOAD_FOLDER = 'downloads'
if not os.path.exists(DOWNLOAD_FOLDER):
    os.makedirs(DOWNLOAD_FOLDER)

# Cấu hình Spotify
SPOTIPY_CLIENT_ID = os.environ.get('SPOTIPY_CLIENT_ID', 'YOUR_SPOTIFY_CLIENT_ID')
SPOTIPY_CLIENT_SECRET = os.environ.get('SPOTIPY_CLIENT_SECRET', 'YOUR_SPOTIFY_CLIENT_SECRET')

if SPOTIPY_CLIENT_ID == 'YOUR_SPOTIFY_CLIENT_ID':
    logging.warning("⚠️ Chưa cấu hình Spotify API Key!")
    sp = None
else:
    auth_manager = SpotifyClientCredentials(client_id=SPOTIPY_CLIENT_ID, client_secret=SPOTIPY_CLIENT_SECRET)
    sp = spotipy.Spotify(auth_manager=auth_manager)
    logging.info("✅ Đã kết nối Spotify.")

def sanitize_filename(name):
    return re.sub(r'[\\/*?:"<>|]', "", name).strip()

def get_spotify_metadata(url):
    if not sp: raise Exception("Thiếu Spotify API Key.")
    try:
        if 'track' in url:
            item = sp.track(url)
            return {
                'type': 'track',
                'name': item['name'],
                'artist': ", ".join([a['name'] for a in item['artists']]),
                'cover': item['album']['images'][0]['url'] if item['album']['images'] else '',
                'tracks_list': [{'name': item['name'], 'artist': ", ".join([a['name'] for a in item['artists']])}]
            }
        elif 'playlist' in url:
            pl = sp.playlist(url)
            tracks = []
            for item in pl['tracks']['items']:
                if item.get('track'):
                    t = item['track']
                    tracks.append({'name': t['name'], 'artist': ", ".join([a['name'] for a in t['artists']])})
            return {'type': 'playlist', 'name': pl['name'], 'tracks_list': tracks}
        elif 'album' in url:
            al = sp.album(url)
            tracks = [{'name': t['name'], 'artist': ", ".join([a['name'] for a in t['artists']])} for t in al['tracks']['items']]
            return {'type': 'album', 'name': al['name'], 'tracks_list': tracks}
    except Exception as e:
        raise Exception(f"Lỗi Spotify: {str(e)}")

def dl_soundcloud(query, output_folder, final_filename, meta_title, meta_artist):
    # Dùng ID làm tên file tạm để tránh lỗi ký tự đặc biệt
    temp_template = os.path.join(output_folder, '%(id)s.%(ext)s')
    
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': temp_template,
        'default_search': 'scsearch1',
        'postprocessors': [{'key': 'FFmpegExtractAudio','preferredcodec': 'mp3','preferredquality': '192'}],
        'quiet': True,
        'noplaylist': True,
        'concurrent_fragment_downloads': 5, # <--- TĂNG TỐC ĐỘ TẢI (Tải 5 luồng cùng lúc)
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(query, download=True)
            if 'entries' in info: info = info['entries'][0]
            
            # File tạm yt-dlp tạo ra (ID.mp3)
            temp_file = os.path.join(output_folder, f"{info['id']}.mp3")
            
            if not os.path.exists(temp_file): return None

            # Đổi tên file sang tên chuẩn
            clean_name = sanitize_filename(final_filename)
            final_path = os.path.join(output_folder, f"{clean_name}.mp3")
            
            cnt = 1
            while os.path.exists(final_path):
                final_path = os.path.join(output_folder, f"{clean_name} ({cnt}).mp3")
                cnt += 1
                
            shutil.move(temp_file, final_path)

            # Gắn thẻ metadata
            try:
                audio = EasyID3(final_path)
                audio['title'] = meta_title
                audio['artist'] = meta_artist
                audio.save()
            except: 
                try: ID3(final_path).save() 
                except: pass
                
            return final_path
    except Exception as e:
        logging.error(f"DL Error ({query}): {e}")
        return None

# --- ROUTES ---

@app.route('/')
def index():
    return jsonify({"status": "Ready", "spotify": "OK" if sp else "Missing Key"})

@app.route('/api/info', methods=['POST'])
def api_info():
    url = request.json.get('url')
    if not url: return jsonify({'error': 'No URL'}), 400
    try:
        data = get_spotify_metadata(url)
        return jsonify({
            'type': data['type'],
            'name': data['name'],
            'tracks': [{'id': i, 'name': t['name'], 'artist': t['artist'], 'cover': data.get('cover')} 
                       for i, t in enumerate(data['tracks_list'])]
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/download_track', methods=['POST'])
def api_download_track():
    url = request.json.get('url')
    try:
        meta = get_spotify_metadata(url)
        track = meta['tracks_list'][0]
        query = f"{track['name']} {track['artist']}"
        logging.info(f"Downloading: {query}")
        
        path = dl_soundcloud(query, DOWNLOAD_FOLDER, track['name'], track['name'], track['artist'])
        
        if not path: return jsonify({'error': 'Failed to download from SoundCloud'}), 500

        @after_this_request
        def cleanup(resp):
            try: os.remove(path)
            except: pass
            return resp

        return send_file(path, as_attachment=True, download_name=os.path.basename(path))
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/download_zip', methods=['POST'])
def api_download_zip():
    url = request.json.get('url')
    try:
        meta = get_spotify_metadata(url)
        album_name = sanitize_filename(meta['name'])
        album_dir = os.path.join(DOWNLOAD_FOLDER, album_name)
        if not os.path.exists(album_dir): os.makedirs(album_dir)
        
        count = 0
        for t in meta['tracks_list']:
            query = f"{t['name']} {t['artist']}"
            if dl_soundcloud(query, album_dir, t['name'], t['name'], t['artist']):
                count += 1
        
        if count == 0: return jsonify({'error': 'No tracks downloaded'}), 500

        zip_name = f"{album_name}.zip"
        zip_path = os.path.join(DOWNLOAD_FOLDER, zip_name)
        shutil.make_archive(zip_path.replace('.zip', ''), 'zip', album_dir)
        shutil.rmtree(album_dir, ignore_errors=True)

        @after_this_request
        def cleanup(resp):
            try: os.remove(zip_path)
            except: pass
            return resp

        return send_file(zip_path, as_attachment=True, download_name=zip_name)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
