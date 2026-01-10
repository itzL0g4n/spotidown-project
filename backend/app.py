import os
import re
import shutil
import time
import uuid
import logging
import yt_dlp
from flask import Flask, request, jsonify, send_file, after_this_request
from flask_cors import CORS
from mutagen.easyid3 import EasyID3
from mutagen.id3 import ID3, APIC

# Import Spotify
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials

# --- CẤU HÌNH CƠ BẢN ---
app = Flask(__name__)
CORS(app) # Cho phép React gọi API
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

DOWNLOAD_FOLDER = 'downloads'
if not os.path.exists(DOWNLOAD_FOLDER):
    os.makedirs(DOWNLOAD_FOLDER)

# --- CẤU HÌNH SPOTIFY (BẮT BUỘC) ---
# Bạn phải cung cấp Client ID/Secret. Nếu không có, App sẽ không hoạt động (theo yêu cầu của bạn).
SPOTIPY_CLIENT_ID = os.environ.get('SPOTIPY_CLIENT_ID', 'YOUR_SPOTIFY_CLIENT_ID')
SPOTIPY_CLIENT_SECRET = os.environ.get('SPOTIPY_CLIENT_SECRET', 'YOUR_SPOTIFY_CLIENT_SECRET')

sp = None

def init_spotify():
    """Khởi tạo kết nối Spotify. Nếu thất bại, biến sp sẽ là None."""
    global sp
    try:
        if SPOTIPY_CLIENT_ID == 'YOUR_SPOTIFY_CLIENT_ID':
            logging.warning("⚠️ CẢNH BÁO: Chưa cấu hình Spotify API Key!")
            return False
        
        auth_manager = SpotifyClientCredentials(client_id=SPOTIPY_CLIENT_ID, client_secret=SPOTIPY_CLIENT_SECRET)
        sp = spotipy.Spotify(auth_manager=auth_manager)
        logging.info("✅ Đã kết nối Spotify API thành công.")
        return True
    except Exception as e:
        logging.error(f"❌ Lỗi kết nối Spotify: {e}")
        return False

# Gọi hàm khởi tạo
init_spotify()

# --- CÁC HÀM TIỆN ÍCH ---

def sanitize_filename(name):
    """Làm sạch tên file để lưu trên ổ cứng an toàn"""
    return re.sub(r'[\\/*?:"<>|]', "", name).strip()

def get_spotify_metadata(url):
    """
    Chỉ lấy metadata từ Spotify API.
    Trả về cấu trúc chuẩn hoặc Raise Exception nếu lỗi.
    """
    if not sp:
        raise Exception("Server chưa cấu hình Spotify API Key. Vui lòng kiểm tra backend.")

    try:
        if 'track' in url:
            item = sp.track(url)
            # Chuẩn hóa dữ liệu Track
            return {
                'type': 'track',
                'name': item['name'],
                'artist': ", ".join([artist['name'] for artist in item['artists']]),
                'cover': item['album']['images'][0]['url'] if item['album']['images'] else '',
                'id': item['id'],
                'tracks_list': [{ # Danh sách tracks (với bài lẻ thì chỉ có 1)
                    'name': item['name'],
                    'artist': ", ".join([artist['name'] for artist in item['artists']]),
                }]
            }

        elif 'playlist' in url:
            playlist = sp.playlist(url)
            tracks = []
            for item in playlist['tracks']['items']:
                if item.get('track'):
                    t = item['track']
                    tracks.append({
                        'name': t['name'],
                        'artist': ", ".join([artist['name'] for artist in t['artists']]),
                    })
            return {
                'type': 'playlist',
                'name': playlist['name'],
                'artist': playlist['owner']['display_name'],
                'cover': playlist['images'][0]['url'] if playlist['images'] else '',
                'id': playlist['id'],
                'tracks_list': tracks
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
                'artist': ", ".join([artist['name'] for artist in album['artists']]),
                'cover': album['images'][0]['url'] if album['images'] else '',
                'id': album['id'],
                'tracks_list': tracks
            }
        else:
            raise Exception("Link không hợp lệ (Không phải Track, Playlist hoặc Album Spotify).")

    except Exception as e:
        logging.error(f"Lỗi Spotify Metadata: {e}")
        raise Exception(f"Lỗi khi lấy thông tin từ Spotify: {str(e)}")

def download_engine(search_query, output_folder, metadata):
    """
    Hàm tải file cốt lõi.
    - Sử dụng folder tạm (UUID) để cô lập file.
    - Sử dụng SoundCloud (scsearch) để tránh DRM/Bot Youtube.
    """
    # 1. Tạo folder tạm duy nhất
    session_id = str(uuid.uuid4())
    temp_path = os.path.join(output_folder, f"temp_{session_id}")
    os.makedirs(temp_path, exist_ok=True)

    logging.info(f"⬇️ Đang tải: '{search_query}' vào {temp_path}")

    # 2. Cấu hình yt-dlp (SoundCloud Mode)
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': os.path.join(temp_path, '%(title)s.%(ext)s'), # Tên file gốc không quan trọng, ta sẽ đổi sau
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'quiet': True,
        'no_warnings': True,
        'default_search': 'scsearch1', # Ưu tiên tìm trên SoundCloud
        'noplaylist': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([search_query])

        # 3. Tìm file kết quả trong folder tạm
        files = [f for f in os.listdir(temp_path) if f.endswith('.mp3')]
        
        if not files:
            logging.error(f"❌ Không tìm thấy file MP3 nào sau khi tải: {search_query}")
            shutil.rmtree(temp_path, ignore_errors=True)
            return None, None

        downloaded_filename = files[0] # Lấy file đầu tiên tìm được
        source_file = os.path.join(temp_path, downloaded_filename)

        # 4. Chuẩn bị đường dẫn đích
        # Dùng metadata chuẩn từ Spotify để đặt tên file
        clean_title = sanitize_filename(metadata['name'])
        # clean_artist = sanitize_filename(metadata['artist'])
        # Tên file cuối cùng: "Tên Bài Hát.mp3" (đơn giản hóa)
        final_filename = f"{clean_title}.mp3"
        final_path = os.path.join(output_folder, final_filename)

        # Xử lý trùng tên (thêm số đếm)
        counter = 1
        base_name = clean_title
        while os.path.exists(final_path):
            final_path = os.path.join(output_folder, f"{base_name} ({counter}).mp3")
            counter += 1
            
        # 5. Di chuyển và Gắn thẻ
        shutil.move(source_file, final_path)
        
        # Gắn thẻ ID3 (Title, Artist)
        try:
            audio = EasyID3(final_path)
            audio['title'] = metadata['name']
            audio['artist'] = metadata['artist']
            audio.save()
        except Exception:
            try:
                audio = ID3(final_path)
                audio.save()
            except: pass

        logging.info(f"✅ Hoàn tất: {final_path}")
        
        # Dọn dẹp
        shutil.rmtree(temp_path, ignore_errors=True)
        
        return final_path, os.path.basename(final_path)

    except Exception as e:
        logging.error(f"❌ Lỗi Engine Tải: {e}")
        shutil.rmtree(temp_path, ignore_errors=True)
        return None, None

# --- ROUTES API ---

@app.route('/')
def index():
    status = "Connected" if sp else "Disconnected (Missing API Key)"
    return jsonify({
        "service": "SpotiDown Backend",
        "spotify_status": status,
        "mode": "SoundCloud Search (Strict)"
    })

@app.route('/api/info', methods=['POST'])
def api_info():
    """Endpoint lấy thông tin bài hát/playlist để hiển thị UI"""
    data = request.json
    url = data.get('url')
    
    if not url: 
        return jsonify({'error': 'Vui lòng cung cấp URL'}), 400
    
    try:
        # Gọi hàm lấy metadata (Strict Spotify)
        info = get_spotify_metadata(url)
        
        # Chuẩn hóa format trả về cho Frontend (khớp với App.jsx)
        response_data = {
            'type': info['type'],
            'name': info['name'],
            'artist': info.get('artist', 'Unknown'),
            'cover': info['cover'],
            'id': info['id'],
            'tracks': []
        }
        
        # Map danh sách tracks
        for idx, t in enumerate(info['tracks_list']):
            response_data['tracks'].append({
                'id': f"{info['id']}_{idx}", # Fake ID cho UI render list
                'name': t['name'],
                'artist': t['artist'],
                'cover': info['cover'], # Dùng cover album cho từng track
                'url': url # Link gốc (để frontend gửi lại khi bấm tải)
            })
            
        return jsonify(response_data)

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/download_track', methods=['POST'])
def api_download_track():
    """Endpoint tải 1 bài hát lẻ"""
    data = request.json
    url = data.get('url') # Đây là link Spotify gốc
    
    try:
        # Bước 1: Lấy lại Metadata chuẩn từ Spotify
        # (Vì frontend có thể chỉ gửi URL, ta cần biết chính xác tên bài để search)
        info = get_spotify_metadata(url)
        
        # Xác định track cần tải
        target_track = None
        if info['type'] == 'track':
            target_track = info['tracks_list'][0]
        else:
            # Nếu gửi link playlist vào api download_track, mặc định lấy bài đầu tiên hoặc báo lỗi
            # Ở đây ta xử lý đơn giản: Lấy bài đầu tiên
            target_track = info['tracks_list'][0]

        # Bước 2: Tạo Query Search cho SoundCloud
        # Format: "Tên bài Tên ca sĩ"
        search_query = f"{target_track['name']} {target_track['artist']}"
        
        # Bước 3: Tải
        file_path, filename = download_engine(search_query, DOWNLOAD_FOLDER, target_track)
        
        if not file_path:
            return jsonify({'error': 'Không tìm thấy bài hát trên SoundCloud'}), 404

        # Bước 4: Gửi file và xóa sau khi gửi
        @after_this_request
        def cleanup(response):
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
            except Exception as e:
                logging.error(f"Lỗi xóa file tạm: {e}")
            return response

        return send_file(file_path, as_attachment=True, download_name=filename)

    except Exception as e:
        logging.error(f"API Download Error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/download_zip', methods=['POST'])
def api_download_zip():
    """Endpoint tải Playlist/Album dưới dạng ZIP"""
    data = request.json
    url = data.get('url')
    
    try:
        # Bước 1: Lấy info playlist
        info = get_spotify_metadata(url)
        if info['type'] == 'track':
            return jsonify({'error': 'Đây là link bài hát lẻ, hãy dùng tính năng tải lẻ.'}), 400

        # Bước 2: Tạo folder album
        album_name = sanitize_filename(info['name'])
        album_folder = os.path.join(DOWNLOAD_FOLDER, album_name)
        if not os.path.exists(album_folder):
            os.makedirs(album_folder)

        # Bước 3: Duyệt và tải từng bài
        success_count = 0
        for track in info['tracks_list']:
            search_query = f"{track['name']} {track['artist']}"
            f_path, _ = download_engine(search_query, album_folder, track)
            if f_path:
                success_count += 1
        
        if success_count == 0:
            return jsonify({'error': 'Không tải được bài nào trong playlist này.'}), 500

        # Bước 4: Nén ZIP
        zip_filename = f"{album_name}.zip"
        zip_path = os.path.join(DOWNLOAD_FOLDER, zip_filename)
        shutil.make_archive(zip_path.replace('.zip', ''), 'zip', album_folder)
        
        # Dọn dẹp folder album
        shutil.rmtree(album_folder, ignore_errors=True)

        # Bước 5: Gửi file
        @after_this_request
        def cleanup_zip(response):
            try:
                if os.path.exists(zip_path):
                    os.remove(zip_path)
            except: pass
            return response
            
        return send_file(zip_path, as_attachment=True, download_name=zip_filename)

    except Exception as e:
        logging.error(f"API Zip Error: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # Chạy server
    app.run(host='0.0.0.0', port=5000, debug=True)
