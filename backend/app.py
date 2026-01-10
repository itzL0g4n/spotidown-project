from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import yt_dlp
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import os
import requests
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, APIC, TIT2, TPE1, TALB
import re
import shutil
import zipfile
import time
import threading
import random

app = Flask(__name__)
CORS(app)

# --- CẤU HÌNH ---
SPOTIPY_CLIENT_ID = os.environ.get('SPOTIPY_CLIENT_ID', 'YOUR_SPOTIFY_CLIENT_ID').strip()
SPOTIPY_CLIENT_SECRET = os.environ.get('SPOTIPY_CLIENT_SECRET', 'YOUR_SPOTIFY_CLIENT_SECRET').strip()

DOWNLOAD_FOLDER = 'downloads'
if not os.path.exists(DOWNLOAD_FOLDER):
    os.makedirs(DOWNLOAD_FOLDER)

# --- TIẾN TRÌNH DỌN DẸP ---
DELETE_AFTER_SECONDS = 1800 
CHECK_INTERVAL = 600

def auto_cleanup_task():
    while True:
        try:
            now = time.time()
            count = 0
            for filename in os.listdir(DOWNLOAD_FOLDER):
                file_path = os.path.join(DOWNLOAD_FOLDER, filename)
                if filename.startswith('.'): continue
                if os.path.exists(file_path):
                    creation_time = os.path.getctime(file_path)
                    if (now - creation_time) > DELETE_AFTER_SECONDS:
                        if os.path.isfile(file_path): os.remove(file_path)
                        elif os.path.isdir(file_path): shutil.rmtree(file_path)
                        count += 1
            if count > 0: print(f"✨ Đã dọn {count} file cũ.", flush=True)
        except Exception as e:
            print(f"⚠️ Lỗi dọn dẹp: {e}", flush=True)
        time.sleep(CHECK_INTERVAL)

cleanup_thread = threading.Thread(target=auto_cleanup_task, daemon=True)
cleanup_thread.start()

# --- SPOTIFY ---
try:
    auth_manager = SpotifyClientCredentials(client_id=SPOTIPY_CLIENT_ID, client_secret=SPOTIPY_CLIENT_SECRET)
    sp = spotipy.Spotify(auth_manager=auth_manager)
except Exception as e:
    print(f"Lỗi khởi tạo Spotify: {e}", flush=True)

def sanitize_filename(name):
    return re.sub(r'[<>:"/\\|?*]', '', name)

def add_metadata(file_path, metadata):
    try:
        audio = MP3(file_path, ID3=ID3)
        if audio.tags is None: audio.add_tags()
        audio.tags.add(TIT2(encoding=3, text=metadata['name']))
        audio.tags.add(TPE1(encoding=3, text=metadata['artist']))
        audio.tags.add(TALB(encoding=3, text=metadata['album']))
        if metadata['cover']:
            img_data = requests.get(metadata['cover']).content
            audio.tags.add(APIC(encoding=3, mime='image/jpeg', type=3, desc=u'Cover', data=img_data))
        audio.save()
        print(f"🏷️ Đã gắn metadata cho: {metadata['name']}", flush=True)
    except Exception as e:
        print(f"⚠️ Lỗi gắn metadata: {e}", flush=True)

def get_spotify_info(url):
    try:
        if 'track' in url:
            track = sp.track(url)
            return {
                'type': 'track',
                'id': track['id'],
                'artist': ", ".join([artist['name'] for artist in track['artists']]),
                'name': track['name'],
                'album': track['album']['name'],
                'cover': track['album']['images'][0]['url'] if track['album']['images'] else None
            }
        elif 'playlist' in url:
            playlist = sp.playlist(url)
            tracks = []
            for item in playlist['tracks']['items']:
                track = item['track']
                if track:
                    tracks.append({
                        'type': 'track',
                        'id': track['id'],
                        'name': track['name'],
                        'artist': ", ".join([artist['name'] for artist in track['artists']]),
                        'album': track['album']['name'],
                        'cover': track['album']['images'][0]['url'] if track['album']['images'] else None,
                        'url': track['external_urls']['spotify']
                    })
            return {
                'type': 'playlist',
                'name': playlist['name'],
                'artist': playlist['owner']['display_name'],
                'cover': playlist['images'][0]['url'] if playlist['images'] else None,
                'tracks': tracks
            }
        elif 'album' in url:
            album = sp.album(url)
            tracks = []
            for track in album['tracks']['items']:
                tracks.append({
                    'type': 'track',
                    'id': track['id'],
                    'name': track['name'],
                    'artist': ", ".join([artist['name'] for artist in track['artists']]),
                    'album': album['name'],
                    'cover': album['images'][0]['url'] if album['images'] else None,
                    'url': track['external_urls']['spotify']
                })
            return {
                'type': 'album',
                'name': album['name'],
                'artist': ", ".join([artist['name'] for artist in album['artists']]),
                'cover': album['images'][0]['url'] if album['images'] else None,
                'tracks': tracks
            }
    except Exception as e:
        print(f"Lỗi Spotify: {e}", flush=True)
        return None

def download_audio_source(query, output_path):
    print(f"🔍 Đang tìm trên SoundCloud: {query}", flush=True)
    
    # Cấu hình yt-dlp cho SoundCloud (Đơn giản hơn nhiều so với YouTube)
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': output_path + '.%(ext)s',
        'postprocessors': [{'key': 'FFmpegExtractAudio','preferredcodec': 'mp3','preferredquality': '320'}],
        'noplaylist': True,
        'quiet': False, 
        'verbose': True, # Bật log để xem chi tiết
        
        # SoundCloud không cần cookies phức tạp hay giả lập client
        'socket_timeout': 30,    
        'retries': 10,           
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            # scsearch = SoundCloud Search
            # Thêm "original" để cố gắng tìm bản gốc
            ydl.download([f"scsearch:{query}"])
            print(f"✅ Tải thành công: {output_path}.mp3", flush=True)
            return f"{output_path}.mp3"
        except Exception as e:
            print(f"❌ Lỗi SoundCloud DL cho {query}: {e}", flush=True)
            return None

# --- API ---
@app.route('/api/info', methods=['POST'])
def api_info():
    data = request.json
    print(f"📡 Nhận yêu cầu Info cho URL: {data.get('url')}", flush=True)
    info = get_spotify_info(data.get('url'))
    if not info: return jsonify({'error': 'Lỗi lấy thông tin Spotify'}), 400
    return jsonify(info)

@app.route('/api/download_track', methods=['POST'])
def api_download_track():
    data = request.json
    print(f"⬇️ Nhận yêu cầu tải Track: {data.get('url')}", flush=True)
    info = get_spotify_info(data.get('url'))
    if not info or info['type'] != 'track':
        return jsonify({'error': 'Lỗi thông tin bài hát'}), 400
    
    # Thêm "original" hoặc "audio" để tăng độ chính xác trên SoundCloud
    search_query = f"{info['name']} - {info['artist']}"
    safe_name = sanitize_filename(f"{info['name']} - {info['artist']}")
    final_filename = f"{safe_name}.mp3"
    final_path = os.path.join(DOWNLOAD_FOLDER, final_filename)
    
    if os.path.exists(final_path):
         print(f"📂 File đã tồn tại: {final_filename}", flush=True)
         return jsonify({'status': 'success', 'download_url': f"/api/file/{final_filename}"})

    temp_path = os.path.join(DOWNLOAD_FOLDER, info['id'])
    file_path = download_audio_source(search_query, temp_path)
    
    if file_path:
        add_metadata(file_path, info)
        if os.path.exists(final_path): os.remove(final_path)
        os.rename(file_path, final_path)
        return jsonify({'status': 'success', 'download_url': f"/api/file/{final_filename}"})
    else:
        return jsonify({'error': 'Không tìm thấy bài hát trên nguồn nhạc.'}), 500

@app.route('/api/download_zip', methods=['POST'])
def api_download_zip():
    data = request.json
    print(f"📦 Nhận yêu cầu tải ZIP cho URL: {data.get('url')}", flush=True)
    info = get_spotify_info(data.get('url'))
    if not info: return jsonify({'error': 'Lỗi lấy thông tin'}), 400

    folder_name = sanitize_filename(info['name'])
    folder_path = os.path.join(DOWNLOAD_FOLDER, folder_name)
    if not os.path.exists(folder_path): os.makedirs(folder_path)

    # Lấy 10 bài đầu để demo (bỏ [:10] để tải hết)
    tracks_to_download = info['tracks'][:10] 
    download_count = 0

    for track in tracks_to_download:
        safe_name = sanitize_filename(f"{track['name']} - {track['artist']}")
        final_filename = f"{safe_name}.mp3"
        final_file_path = os.path.join(folder_path, final_filename)
        
        if not os.path.exists(final_file_path):
            search_query = f"{track['name']} - {track['artist']}"
            temp_dl_path = os.path.join(folder_path, track['id'])
            downloaded_path = download_audio_source(search_query, temp_dl_path)
            if downloaded_path:
                add_metadata(downloaded_path, track)
                os.rename(downloaded_path, final_file_path)
                download_count += 1
        else:
            download_count += 1 

    if download_count == 0:
        print("❌ Không tải được bài nào. Hủy tạo Zip.", flush=True)
        try: shutil.rmtree(folder_path)
        except: pass
        return jsonify({'error': 'Không thể tải bất kỳ bài hát nào từ danh sách này.'}), 500
    
    zip_filename = f"{folder_name}.zip"
    zip_path = os.path.join(DOWNLOAD_FOLDER, zip_filename)
    shutil.make_archive(zip_path.replace('.zip', ''), 'zip', folder_path)
    
    try: shutil.rmtree(folder_path)
    except: pass

    print(f"✅ Đã tạo Zip thành công: {zip_filename}", flush=True)
    return jsonify({'status': 'success', 'download_url': f"/api/file/{zip_filename}"})

@app.route('/api/file/<path:filename>', methods=['GET'])
def get_file(filename):
    print(f"📥 Người dùng đang tải file: {filename}", flush=True)
    return send_file(os.path.join(DOWNLOAD_FOLDER, filename), as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True, port=5000)
