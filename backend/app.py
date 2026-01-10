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
# Bạn cần set biến môi trường hoặc điền trực tiếp vào đây (nhưng khuyến khích dùng biến môi trường)
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
        # yt-dlp đôi khi thêm ID vào cuối file hoặc đầu file, ta kiểm tra xem ID có trong tên file không
        if video_id in filename and filename.lower().endswith(('.mp3', '.m4a', '.webm')):
            return os.path.join(directory, filename)
    return None

def get_spotify_info(url):
    """Lấy thông tin từ Spotify API (Chuẩn xác & Nhanh hơn)"""
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
                    'id': track['id'],
                    'name': track['name'],
                    'artist': ", ".join([artist['name'] for artist in track['artists']]),
                    'cover': track['album']['images'][0]['url'] if track['album']['images'] else '',
                    'url': track['external_urls']['spotify']
                }]
            }
        
        elif 'playlist' in url:
            playlist = sp.playlist(url)
            tracks = []
            for item in playlist['tracks']['items']:
                if item['track']:
                    t = item['track']
                    tracks.append({
                        'id': t['id'],
                        'name': t['name'],
                        'artist': ", ".join([artist['name'] for artist in t['artists']]),
                        'cover': t['album']['images'][0]['url'] if t['album']['images'] else '',
                        'url': t['external_urls']['spotify']
                    })
            return {
                'type': 'playlist',
                'name': playlist['name'],
                'artist': playlist['owner']['display_name'],
                'cover': playlist['images'][0]['url'] if playlist['images'] else '',
                'id': playlist['id'],
                'tracks': tracks
            }
            
        elif 'album' in url:
            album = sp.album(url)
            tracks = []
            for t in album['tracks']['items']:
                tracks.append({
                    'id': t['id'],
                    'name': t['name'],
                    'artist': ", ".join([artist['name'] for artist in t['artists']]),
                    'cover': album['images'][0]['url'] if album['images'] else '',
                    'url': t['external_urls']['spotify']
                })
            return {
                'type': 'album', # Coi như playlist
                'name': album['name'],
                'artist': ", ".join([artist['name'] for artist in album['artists']]),
                'cover': album['images'][0]['url'] if album['images'] else '',
                'id': album['id'],
                'tracks': tracks
            }
            
    except Exception as e:
        logging.error(f"Spotify API Error: {e}")
        return None

def get_video_info(url):
    """Hàm điều phối: Ưu tiên Spotify API, Fallback sang yt-dlp"""
    
    # 1. Thử dùng Spotify API trước nếu là link Spotify
    if 'spotify.com' in url and sp:
        spotify_data = get_spotify_info(url)
        if spotify_data:
            return spotify_data
            
    # 2. Fallback: Dùng yt-dlp (cho YouTube hoặc nếu Spotify API lỗi/thiếu key)
    try:
        ydl_opts = {
            'quiet': True,
            'extract_flat': True,
            'dump_single_json': True
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            # Chuẩn hóa dữ liệu yt-dlp về format chung
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
                        result['tracks'].append({
                            'id': entry.get('id'),
                            'name': entry.get('title'),
                            'artist': entry.get('uploader'),
                            'cover': entry.get('thumbnail'), 
                            'url': entry.get('url')
                        })
            else:
                result['tracks'] = [{
                    'id': info.get('id'),
                    'name': info.get('title'),
                    'artist': info.get('uploader'),
                    'cover': info.get('thumbnail'),
                    'url': info.get('webpage_url')
                }]
            return result
            
    except Exception as e:
        logging.error(f"Lỗi lấy info (yt-dlp): {e}")
        return None

def download_audio_logic(url, output_folder=DOWNLOAD_FOLDER, is_playlist=False):
    try:
        ydl_opts = {
            'format': 'bestaudio/best',
            # Logic đặt tên file: Nếu playlist thì gom vào folder, nếu lẻ thì để ngoài
            'outtmpl': os.path.join(output_folder, '%(title)s.%(ext)s') if is_playlist else os.path.join(output_folder, '%(id)s.%(ext)s'),
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'quiet': True,
            'no_warnings': True,
        }
        
        # Xử lý Album folder
        if is_playlist:
            # Nếu là link Spotify, yt-dlp có thể không lấy được title chuẩn ngay để làm tên folder
            # Nên ta đặt tên folder tạm là ID hoặc Title nếu có
            album_name = "Playlist_" + str(int(time.time()))
            
            # Thử lấy tên album nhanh
            try:
                with yt_dlp.YoutubeDL({'quiet': True, 'extract_flat': True}) as ydl:
                    pre_info = ydl.extract_info(url, download=False)
                    if 'title' in pre_info:
                        album_name = sanitize_filename(pre_info['title'])
            except: pass

            final_folder = os.path.join(output_folder, album_name)
            if not os.path.exists(final_folder): os.makedirs(final_folder)
            ydl_opts['outtmpl'] = os.path.join(final_folder, '%(title)s.%(ext)s')
        else:
            final_folder = output_folder
            album_name = "Single"

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # yt-dlp thông minh: Nếu đưa link Spotify, nó sẽ tự search YouTube để tải
            info = ydl.extract_info(url, download=True)
            
            if is_playlist:
                return final_folder, album_name
            else:
                video_id = info.get('id')
                # TÌM FILE ĐÃ TẢI (Fix lỗi FileNotFoundError)
                file_path = find_downloaded_file(final_folder, video_id)
                
                # Nếu không tìm thấy bằng ID, thử tìm file mới nhất trong thư mục (Fallback)
                if not file_path:
                    list_of_files = [os.path.join(final_folder, f) for f in os.listdir(final_folder) if f.endswith('.mp3')]
                    if list_of_files:
                        file_path = max(list_of_files, key=os.path.getctime)

                if file_path:
                    title = sanitize_filename(info.get('title', 'audio'))
                    new_path = os.path.join(final_folder, f"{title}.mp3")
                    
                    # Xử lý trùng tên
                    if os.path.exists(new_path) and new_path != file_path:
                         os.remove(new_path)
                         
                    os.rename(file_path, new_path)
                    
                    # Gắn Metadata
                    try:
                        audio = EasyID3(new_path)
                        audio['title'] = info.get('title')
                        audio['artist'] = info.get('artist') or info.get('uploader')
                        audio.save()
                    except: pass
                    
                    return new_path, title
                return None, None

    except Exception as e:
        logging.error(f"DL Error: {e}")
        raise e

# --- ROUTES ---

@app.route('/')
def index():
    return jsonify({
        "status": "SpotiDown Backend Running", 
        "spotify_api": "Connected" if sp else "Disconnected (Fallback mode)"
    })

@app.route('/api/info', methods=['POST'])
def get_info():
    data = request.json
    url = data.get('url')
    if not url: return jsonify({'error': 'Thiếu URL'}), 400

    # Hàm get_video_info giờ đã thông minh (ưu tiên Spotify API -> Fallback yt-dlp)
    info = get_video_info(url)
    
    if not info: 
        return jsonify({'error': 'Không lấy được thông tin. Vui lòng kiểm tra Link.'}), 500

    return jsonify(info)

@app.route('/api/download_track', methods=['POST'])
def download_track():
    data = request.json
    url = data.get('url')
    try:
        file_path, filename = download_audio_logic(url, is_playlist=False)
        if not file_path: return jsonify({'error': 'Lỗi file hệ thống (Không tìm thấy file sau khi tải)'}), 500

        @after_this_request
        def remove_file(response):
            try: 
                if os.path.exists(file_path): os.remove(file_path)
            except: pass
            return response

        return send_file(file_path, as_attachment=True, download_name=f"{filename}.mp3")
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/download_zip', methods=['POST'])
def download_zip():
    data = request.json
    url = data.get('url')
    try:
        folder_path, album_name = download_audio_logic(url, is_playlist=True)
        
        zip_filename = f"{album_name}.zip"
        zip_path = os.path.join(DOWNLOAD_FOLDER, zip_filename)
        
        shutil.make_archive(zip_path.replace('.zip', ''), 'zip', folder_path)
        shutil.rmtree(folder_path)

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
