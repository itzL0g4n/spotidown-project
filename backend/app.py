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

def find_downloaded_file(directory, video_id):
    if not os.path.exists(directory): return None
    time.sleep(1) 
    for filename in os.listdir(directory):
        if video_id in filename and filename.lower().endswith(('.mp3', '.m4a', '.webm')):
            return os.path.join(directory, filename)
    return None

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
    """Hàm phụ trợ: Tải 1 bài từ câu lệnh search"""
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': os.path.join(output_folder, '%(id)s.%(ext)s'),
        'postprocessors': [{'key': 'FFmpegExtractAudio','preferredcodec': 'mp3','preferredquality': '192'}],
        'quiet': True,
        'no_warnings': True,
        'default_search': 'scsearch1', # CHUYỂN SANG SOUNDCLOUD SEARCH
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Search và tải
            info = ydl.extract_info(search_query, download=True)
            
            # search trả về list entries, lấy phần tử đầu tiên
            if 'entries' in info:
                info = info['entries'][0]
            
            video_id = info['id']
            file_path = find_downloaded_file(output_folder, video_id)

            if file_path:
                # Nếu có metadata từ Spotify truyền vào thì dùng, không thì dùng của nguồn tải
                title = metadata['name'] if metadata else info.get('title', 'audio')
                artist = metadata['artist'] if metadata else info.get('uploader', 'Unknown')
                
                safe_title = sanitize_filename(title)
                new_path = os.path.join(output_folder, f"{safe_title}.mp3")
                
                # Xử lý trùng tên
                counter = 1
                while os.path.exists(new_path) and new_path != file_path:
                     new_path = os.path.join(output_folder, f"{safe_title} ({counter}).mp3")
                     counter += 1

                if file_path != new_path:
                    os.rename(file_path, new_path)
                
                # Gắn Metadata
                try:
                    audio = EasyID3(new_path)
                    audio['title'] = title
                    audio['artist'] = artist
                    audio.save()
                except: 
                    # Fallback ID3
                    try: 
                        audio = ID3(new_path) 
                        audio.save() 
                    except: pass
                
                return new_path, safe_title
            return None, None
    except Exception as e:
        logging.error(f"Lỗi tải item {search_query}: {e}")
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
            
            # Duyệt qua từng bài và tải
            for track in info['tracks']:
                # Bỏ từ khóa 'audio' vì SoundCloud mặc định là audio
                query = f"{track['name']} {track['artist']}" 
                download_single_item(query, final_folder, metadata=track)
                
            return final_folder, album_name
            
        # Nếu là bài lẻ (Track)
        else:
            final_folder = output_folder
            # Lấy track đầu tiên
            track = info['tracks'][0]
            query = f"{track['name']} {track['artist']}"
            return download_single_item(query, final_folder, metadata=track)

    # 2. XỬ LÝ LINK TRỰC TIẾP (SoundCloud/YouTube/Khác)
    else:
        # Nếu user đưa link trực tiếp thì vẫn tải bình thường
        if not is_playlist:
            return download_single_item(url, output_folder)
        else:
            try:
                with yt_dlp.YoutubeDL({'quiet': True, 'extract_flat': True}) as ydl:
                    pre_info = ydl.extract_info(url, download=False)
                    album_name = sanitize_filename(pre_info.get('title', 'Playlist'))
                
                final_folder = os.path.join(output_folder, album_name)
                if not os.path.exists(final_folder): os.makedirs(final_folder)

                ydl_opts = {
                    'format': 'bestaudio/best',
                    'outtmpl': os.path.join(final_folder, '%(id)s.%(ext)s'),
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
