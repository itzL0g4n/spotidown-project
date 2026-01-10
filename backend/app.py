import os
import re
import yt_dlp
import logging
import zipfile
import shutil
import time
import uuid  # Import thêm uuid để tạo folder tạm duy nhất
from flask import Flask, request, jsonify, send_file, after_this_request
from flask_cors import CORS
from mutagen.easyid3 import EasyID3
from mutagen.id3 import ID3, APIC

# --- SPOTIFY IMPORTS ---
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials

app = Flask(__name__)
CORS(app) 

logging.basicConfig(level=logging.INFO)

DOWNLOAD_FOLDER = 'downloads'
if not os.path.exists(DOWNLOAD_FOLDER):
    os.makedirs(DOWNLOAD_FOLDER)

# --- CẤU HÌNH SPOTIFY API ---
SPOTIPY_CLIENT_ID = os.environ.get('SPOTIPY_CLIENT_ID', 'YOUR_SPOTIFY_CLIENT_ID')
SPOTIPY_CLIENT_SECRET = os.environ.get('SPOTIPY_CLIENT_SECRET', 'YOUR_SPOTIFY_CLIENT_SECRET')

sp = None
try:
    if SPOTIPY_CLIENT_ID != 'YOUR_SPOTIFY_CLIENT_ID':
        auth_manager = SpotifyClientCredentials(client_id=SPOTIPY_CLIENT_ID, client_secret=SPOTIPY_CLIENT_SECRET)
        sp = spotipy.Spotify(auth_manager=auth_manager)
        logging.info("✅ Spotify API Connected")
    else:
        logging.warning("⚠️ Chưa cấu hình Spotify API Key. Sẽ chạy ở chế độ fallback (yt-dlp only).")
except Exception as e:
    logging.error(f"❌ Lỗi kết nối Spotify API: {e}")

def sanitize_filename(name):
    return re.sub(r'[\\/*?:"<>|]', "", name)

# Hàm tìm file cũ đã bị loại bỏ vì chiến thuật mới dùng folder tạm

def get_spotify_info(url):
    """Lấy thông tin từ Spotify API"""
    if not sp: return None
    
    try:
        if 'track' in url:
            track = sp.track(url)
            return {
                'type': 'track',
                'name': track['name'],
                'artist': ", ".join([artist['name'] for artist in track['artists']]),
                'cover': track['album']['images'][0]['url'] if track['album']['images'] else '',
                'id': track['id'],
                'tracks': [{
                    'name': track['name'],
                    'artist': ", ".join([artist['name'] for artist in track['artists']]),
                }]
            }
        
        elif 'playlist' in url:
            playlist = sp.playlist(url)
            tracks = []
            for item in playlist['tracks']['items']:
                if item['track']:
                    t = item['track']
                    tracks.append({
                        'name': t['name'],
                        'artist': ", ".join([artist['name'] for artist in t['artists']]),
                    })
            return {
                'type': 'playlist',
                'name': playlist['name'],
                'tracks': tracks
            }
            
        elif 'album' in url:
            album = sp.album(url)
            tracks = []
            for t in album['tracks']['items']:
                tracks.append({
                    'name': t['name'],
                    'artist': ", ".join([artist['name'] for artist in t['artists']]),
                })
            return {
                'type': 'album',
                'name': album['name'],
                'tracks': tracks
            }
            
    except Exception as e:
        logging.error(f"Spotify API Error: {e}")
        return None

def get_video_info(url):
    """Hàm lấy info hiển thị lên UI"""
    # 1. Ưu tiên Spotify API
    if 'spotify.com' in url and sp:
        spotify_data = get_spotify_info(url)
        if spotify_data:
            # Format lại để khớp với frontend
            spotify_data['tracks'] = [{'id': i, 'name': t['name'], 'artist': t['artist'], 'cover': spotify_data.get('cover', '')} for i, t in enumerate(spotify_data['tracks'])]
            return spotify_data
            
    # 2. Fallback yt-dlp
    try:
        ydl_opts = {'quiet': True, 'extract_flat': True, 'dump_single_json': True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            result = {
                'type': 'playlist' if 'entries' in info else 'track',
                'name': info.get('title', 'Unknown'),
                'artist': info.get('uploader', 'Unknown Artist'),
                'cover': info.get('thumbnail', ''),
                'id': info.get('id'),
                'tracks': []
            }
            if result['type'] == 'playlist':
                for entry in info['entries']:
                    if entry:
                        result['tracks'].append({'id': entry.get('id'), 'name': entry.get('title'), 'artist': entry.get('uploader'), 'cover': entry.get('thumbnail')})
            else:
                result['tracks'] = [{'id': info.get('id'), 'name': info.get('title'), 'artist': info.get('uploader'), 'cover': info.get('thumbnail')}]
            return result
    except Exception as e:
        logging.error(f"Lỗi lấy info: {e}")
        return None

def download_single_item(search_query, output_folder, metadata=None):
    """Hàm phụ trợ: Tải 1 bài dùng folder tạm cô lập"""
    
    # Tạo folder tạm duy nhất cho lần tải này
    temp_dir_name = str(uuid.uuid4())
    temp_path = os.path.join(output_folder, temp_dir_name)
    if not os.path.exists(temp_path):
        os.makedirs(temp_path)

    logging.info(f"🔍 Đang tìm kiếm và tải: {search_query}")
    logging.info(f"📂 Thư mục tạm: {temp_path}")

    ydl_opts = {
        'format': 'bestaudio/best',
        # Lưu thẳng vào folder tạm, không quan trọng tên file gốc là gì
        'outtmpl': os.path.join(temp_path, '%(title)s.%(ext)s'),
        'postprocessors': [{'key': 'FFmpegExtractAudio','preferredcodec': 'mp3','preferredquality': '192'}],
        'quiet': True,
        'no_warnings': True,
        'default_search': 'scsearch1', # SOUNDCLOUD SEARCH
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Search và tải
            ydl.download([search_query])
            
            # Kiểm tra xem folder tạm có file nào không
            files = os.listdir(temp_path)
            downloaded_file = None
            for f in files:
                if f.endswith('.mp3'):
                    downloaded_file = os.path.join(temp_path, f)
                    break
            
            if downloaded_file:
                # Nếu có metadata từ Spotify truyền vào thì dùng
                title = metadata['name'] if metadata else "Unknown Title"
                artist = metadata['artist'] if metadata else "Unknown Artist"
                
                safe_title = sanitize_filename(title)
                final_path = os.path.join(output_folder, f"{safe_title}.mp3")
                
                # Xử lý trùng tên ở thư mục đích
                counter = 1
                while os.path.exists(final_path):
                     final_path = os.path.join(output_folder, f"{safe_title} ({counter}).mp3")
                     counter += 1

                # Di chuyển file từ temp ra đích
                shutil.move(downloaded_file, final_path)
                logging.info(f"✅ Đã chuyển file tới: {final_path}")
                
                # Xóa folder tạm
                try: shutil.rmtree(temp_path)
                except: pass

                # Gắn Metadata
                try:
                    audio = EasyID3(final_path)
                    audio['title'] = title
                    audio['artist'] = artist
                    audio.save()
                except: 
                    try: 
                        audio = ID3(final_path) 
                        audio.save() 
                    except: pass
                
                return final_path, safe_title
            
            else:
                logging.error("❌ yt-dlp chạy xong nhưng không thấy file mp3 nào trong folder tạm.")
                try: shutil.rmtree(temp_path)
                except: pass
                return None, None

    except Exception as e:
        logging.error(f"❌ Lỗi nghiêm trọng khi tải {search_query}: {e}")
        try: shutil.rmtree(temp_path)
        except: pass
        return None, None

def download_audio_logic(url, output_folder=DOWNLOAD_FOLDER, is_playlist=False):
    """Logic tải thông minh: Tự chuyển Spotify Link -> SoundCloud Search"""
    
    # 1. XỬ LÝ LINK SPOTIFY
    if 'spotify.com' in url:
        info = get_spotify_info(url)
        if not info: raise Exception("Không lấy được thông tin Spotify để tải.")
        
        # Nếu là playlist/album
        if info['type'] in ['playlist', 'album'] and is_playlist:
            album_name = sanitize_filename(info['name'])
            final_folder = os.path.join(output_folder, album_name)
            if not os.path.exists(final_folder): os.makedirs(final_folder)
            
            for track in info['tracks']:
                query = f"{track['name']} {track['artist']}" 
                download_single_item(query, final_folder, metadata=track)
                
            return final_folder, album_name
            
        # Nếu là bài lẻ (Track)
        else:
            final_folder = output_folder
            track = info['tracks'][0]
            query = f"{track['name']} {track['artist']}"
            return download_single_item(query, final_folder, metadata=track)

    # 2. XỬ LÝ LINK TRỰC TIẾP
    else:
        if not is_playlist:
            return download_single_item(url, output_folder)
        else:
            # Logic playlist cho link trực tiếp (ít dùng với Soundcloud search, chủ yếu cho Youtube link)
            try:
                with yt_dlp.YoutubeDL({'quiet': True, 'extract_flat': True}) as ydl:
                    pre_info = ydl.extract_info(url, download=False)
                    album_name = sanitize_filename(pre_info.get('title', 'Playlist'))
                
                final_folder = os.path.join(output_folder, album_name)
                if not os.path.exists(final_folder): os.makedirs(final_folder)

                ydl_opts = {
                    'format': 'bestaudio/best',
                    'outtmpl': os.path.join(final_folder, '%(title)s.%(ext)s'), # Dùng title thay vì ID
                    'postprocessors': [{'key': 'FFmpegExtractAudio','preferredcodec': 'mp3','preferredquality': '192'}],
                    'quiet': True, 'no_warnings': True
                }
                
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([url])
                    
                return final_folder, album_name
            except Exception as e:
                raise e

# --- ROUTES ---

@app.route('/')
def index():
    return jsonify({
        "status": "SpotiDown Backend Running", 
        "spotify_api": "Connected" if sp else "Disconnected"
    })

@app.route('/api/info', methods=['POST'])
def get_info():
    data = request.json
    url = data.get('url')
    if not url: return jsonify({'error': 'Thiếu URL'}), 400
    info = get_video_info(url)
    if not info: return jsonify({'error': 'Không lấy được thông tin.'}), 500
    return jsonify(info)

@app.route('/api/download_track', methods=['POST'])
def download_track():
    data = request.json
    url = data.get('url')
    try:
        file_path, filename = download_audio_logic(url, is_playlist=False)
        
        if not file_path: return jsonify({'error': 'Không tìm thấy file sau khi tải'}), 500

        @after_this_request
        def remove_file(response):
            try: 
                if os.path.exists(file_path): os.remove(file_path)
            except: pass
            return response

        return send_file(file_path, as_attachment=True, download_name=f"{filename}.mp3")
    except Exception as e:
        logging.error(f"API Error: {e}")
        return jsonify({'error': "Lỗi server: " + str(e)}), 500

@app.route('/api/download_zip', methods=['POST'])
def download_zip():
    data = request.json
    url = data.get('url')
    try:
        folder_path, album_name = download_audio_logic(url, is_playlist=True)
        
        zip_filename = f"{album_name}.zip"
        zip_path = os.path.join(DOWNLOAD_FOLDER, zip_filename)
        
        shutil.make_archive(zip_path.replace('.zip', ''), 'zip', folder_path)
        try: shutil.rmtree(folder_path) 
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
    app.run(host='0.0.0.0', port=5000, debug=True)
