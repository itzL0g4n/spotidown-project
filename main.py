import os
import re
import uuid
import requests
import zipfile
import io
import shutil
import glob
import time
import threading
import uvicorn
from typing import List, Optional, Dict
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import yt_dlp
from mutagen.easyid3 import EasyID3

# Load environment variables
load_dotenv()

app = FastAPI(title="Spotidown Backend")

# --- DIRECTORY SETUP ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DOWNLOAD_DIR = os.path.join(BASE_DIR, "downloads")
TEMP_WORK_DIR = os.path.join(DOWNLOAD_DIR, "temp_workspace")

if not os.path.exists(DOWNLOAD_DIR): os.makedirs(DOWNLOAD_DIR)
if not os.path.exists(TEMP_WORK_DIR): os.makedirs(TEMP_WORK_DIR)

# --- CLEANUP TASK (From example.py) ---
def cleanup_task():
    while True:
        try:
            now = time.time()
            # 1. Clean downloads folder
            for f in os.listdir(DOWNLOAD_DIR):
                p = os.path.join(DOWNLOAD_DIR, f)
                if f == 'temp_workspace': continue
                
                # Delete files older than 30 mins
                if now - os.path.getctime(p) > 1800:
                    if os.path.isfile(p): os.remove(p)
                    elif os.path.isdir(p): shutil.rmtree(p, ignore_errors=True)
            
            # 2. Clean temp workspace
            for f in os.listdir(TEMP_WORK_DIR):
                p = os.path.join(TEMP_WORK_DIR, f)
                if now - os.path.getctime(p) > 1800:
                    shutil.rmtree(p, ignore_errors=True)
        except Exception as e:
            print(f"Cleanup error: {e}")
        time.sleep(600)

# Start cleanup thread
threading.Thread(target=cleanup_task, daemon=True).start()

# CORS Configuration
origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Spotify Client Setup
SPOTIPY_CLIENT_ID = os.getenv("SPOTIPY_CLIENT_ID")
SPOTIPY_CLIENT_SECRET = os.getenv("SPOTIPY_CLIENT_SECRET")

sp = None
if SPOTIPY_CLIENT_ID and SPOTIPY_CLIENT_SECRET:
    try:
        client_credentials_manager = SpotifyClientCredentials(
            client_id=SPOTIPY_CLIENT_ID,
            client_secret=SPOTIPY_CLIENT_SECRET
        )
        sp = spotipy.Spotify(client_credentials_manager=client_credentials_manager)
    except Exception as e:
        print(f"Warning: Failed to initialize Spotipy: {e}")
else:
    print("Warning: Spotify credentials not found in environment variables.")

# --- Storage ---
# download_storage maps SingleFileID -> { filename: str, path: str, type: 'single' }
download_storage: Dict[str, dict] = {}

# jobs maps JobID -> { status: 'processing'|'done'|'error', progress: 'X/Y', zip_path: str, error: str }
jobs: Dict[str, dict] = {}

# --- Models ---
class InfoRequest(BaseModel):
    url: str

class TrackInfo(BaseModel):
    title: str
    artist: str
    cover_image: str
    spotify_url: str

class InfoResponse(BaseModel):
    type: str 
    name: str 
    cover_image: str
    tracks: List[TrackInfo]

class ConvertRequest(BaseModel):
    url: Optional[str] = None
    title: Optional[str] = None
    artist: Optional[str] = None

class ConvertResponse(BaseModel):
    title: str
    artist: str
    download_url: str

class BatchRequest(BaseModel):
    tracks: List[TrackInfo]
    collection_name: str

class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    progress: str
    error: Optional[str] = None
    download_url: Optional[str] = None

# --- Helpers ---

def get_spotify_id_and_type(url: str):
    parsed = re.search(r"(?:open\.spotify\.com\/|spotify:)(track|album|playlist)(?:\/|:)([a-zA-Z0-9]+)", url)
    if not parsed:
        raise ValueError("Invalid Spotify URL")
    return parsed.group(1), parsed.group(2)

def sanitize_filename(name: str) -> str:
    # Robust sanitization from example.py
    return re.sub(r'[\\/*?:"<>|]', "", name).strip()

def dl_engine(query, output_folder, final_name, meta_title, meta_artist):
    """
    Robust download engine ported from example.py
    """
    safe_name = sanitize_filename(final_name)
    final_path = os.path.join(output_folder, f"{safe_name}.mp3")
    
    # Check if exists
    if os.path.exists(final_path): return final_path

    # Unique temp dir for isolation
    temp_id = str(uuid.uuid4())
    temp_dir = os.path.join(TEMP_WORK_DIR, f"temp_{temp_id}")
    os.makedirs(temp_dir, exist_ok=True)
    
    # Cookie file check
    cookie_file = os.path.join(BASE_DIR, 'cookies.txt')
    has_cookies = os.path.exists(cookie_file)

    strategies = [
        {'src': 'ytsearch1', 'name': 'YouTube'},
        {'src': 'scsearch1', 'name': 'SoundCloud'} 
    ]

    for strat in strategies:
        try:
            print(f"🔎 Searching '{query}' on {strat['name']}...")
            
            # Use fixed temp filename to avoid naming issues
            temp_filename_tmpl = os.path.join(temp_dir, 'downloaded_file.%(ext)s')

            opts = {
                'format': 'bestaudio/best',
                'outtmpl': temp_filename_tmpl,
                'default_search': strat['src'],
                'postprocessors': [{'key': 'FFmpegExtractAudio','preferredcodec': 'mp3','preferredquality': '192'}],
                'quiet': True, 
                'no_warnings': True, 
                'noplaylist': True,
                'socket_timeout': 30,
                'nocheckcertificate': True,
                # Try to use Android client for YT
                'extractor_args': {
                    'youtube': {
                        'player_client': ['android', 'ios']
                    }
                }
            }

            if strat['src'] == 'ytsearch1' and has_cookies:
                opts['cookiefile'] = cookie_file

            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([query])

            # Find the file (regardless of extension if conversion failed, but we expect mp3)
            files = [f for f in os.listdir(temp_dir) if f.endswith('.mp3')]
            
            if files:
                downloaded_temp_path = os.path.join(temp_dir, files[0])
                
                # Move to final location
                shutil.move(downloaded_temp_path, final_path)
                
                # Tagging
                try:
                    tag = EasyID3(final_path)
                    tag['title'] = meta_title
                    tag['artist'] = meta_artist
                    tag.save()
                except Exception as e:
                    # Initialize tags if file has none
                    try:
                        tag = EasyID3()
                        tag['title'] = meta_title
                        tag['artist'] = meta_artist
                        tag.save(final_path)
                    except:
                        pass
                
                # Cleanup temp
                shutil.rmtree(temp_dir, ignore_errors=True)
                print(f"✅ Success: {final_path}")
                return final_path
        
        except Exception as e:
            print(f"⚠️ {strat['name']} Error: {str(e)}")
            # Continue to next strategy
    
    # Cleanup on failure
    shutil.rmtree(temp_dir, ignore_errors=True)
    return None

# --- Background Task ---

def process_batch_job(job_id: str, tracks: List[TrackInfo], collection_name: str):
    try:
        jobs[job_id]['status'] = 'processing'
        jobs[job_id]['total'] = len(tracks)
        
        # Temp folder for this batch inside DOWNLOAD_DIR
        batch_dir = os.path.join(DOWNLOAD_DIR, f"batch_{job_id}")
        if not os.path.exists(batch_dir):
            os.makedirs(batch_dir)
            
        zip_filename = f"{sanitize_filename(collection_name)}.zip"
        zip_path = os.path.join(DOWNLOAD_DIR, zip_filename)
        
        saved_files = []
        
        for i, track in enumerate(tracks):
            jobs[job_id]['progress'] = f"{i}/{len(tracks)}"
            
            query = f"{track.artist} - {track.title} audio"
            final_name = f"{track.artist} - {track.title}"
            
            # Use our robust engine
            # We download to batch_dir
            path = dl_engine(query, batch_dir, final_name, track.title, track.artist)
            
            if path:
                saved_files.append(path)
            else:
                print(f"Failed to download: {track.title}")
        
        if not saved_files:
            raise Exception("No tracks were downloaded successfully.")

        # Zip content
        with zipfile.ZipFile(zip_path, 'w') as zf:
            for file_path in saved_files:
                zf.write(file_path, arcname=os.path.basename(file_path))
        
        # Cleanup batch dir
        shutil.rmtree(batch_dir, ignore_errors=True)
        
        jobs[job_id]['status'] = 'done'
        jobs[job_id]['progress'] = f"{len(saved_files)}/{len(tracks)}"
        jobs[job_id]['zip_path'] = zip_path
        
    except Exception as e:
        jobs[job_id]['status'] = 'error'
        jobs[job_id]['error'] = str(e)
        import traceback
        traceback.print_exc()

# --- Endpoints ---

@app.post("/api/info", response_model=InfoResponse)
async def get_info(request: InfoRequest):
    if not sp: raise HTTPException(status_code=500, detail="Spotify not configured.")
    try:
        sp_type, sp_id = get_spotify_id_and_type(request.url)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid Spotify URL.")

    name = ""
    cover_image = ""
    tracks = []
    
    try:
        if sp_type == 'track':
            track = sp.track(sp_id)
            name = track['name']
            if track['album']['images']: cover_image = track['album']['images'][0]['url']
            tracks.append(TrackInfo(title=track['name'], artist=track['artists'][0]['name'], cover_image=cover_image, spotify_url=track['external_urls']['spotify']))

        elif sp_type == 'album':
            album = sp.album(sp_id)
            name = album['name']
            if album['images']: cover_image = album['images'][0]['url']
            results = sp.album_tracks(sp_id)
            for item in results['items']:
                tracks.append(TrackInfo(title=item['name'], artist=item['artists'][0]['name'], cover_image=cover_image, spotify_url=item['external_urls']['spotify']))

        elif sp_type == 'playlist':
            playlist = sp.playlist(sp_id)
            name = playlist['name']
            if playlist['images']: cover_image = playlist['images'][0]['url']
            results = playlist['tracks']
            for item in results['items']:
                if item['track']:
                    t = item['track']
                    img = cover_image
                    if t['album']['images']: img = t['album']['images'][0]['url']
                    tracks.append(TrackInfo(title=t['name'], artist=t['artists'][0]['name'], cover_image=img, spotify_url=t['external_urls']['spotify']))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    return InfoResponse(type=sp_type, name=name, cover_image=cover_image, tracks=tracks)

@app.post("/api/convert", response_model=ConvertResponse)
async def convert_track(request: ConvertRequest):
    title = request.title
    artist = request.artist
    if not (title and artist): raise HTTPException(status_code=400, detail="Missing info.")

    search_query = f"{artist} - {title} audio"
    try:
        # Use robust dl_engine
        final_name = f"{artist} - {title}"
        file_path = dl_engine(search_query, DOWNLOAD_DIR, final_name, title, artist)
        
        if not file_path:
             raise HTTPException(status_code=500, detail="Download failed on both YouTube and SoundCloud")
        
        file_id = str(uuid.uuid4())
        # Store just path, clean_up handles deletion if we want, 
        # OR we let cleanup_task handle it periodically (safer for "recent download history" UI)
        download_storage[file_id] = { 
            "path": file_path, 
            "filename": os.path.basename(file_path)
        }
        
        return ConvertResponse(title=title, artist=artist, download_url=f"/api/download/{file_id}")
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/download/{file_id}")
async def download_file(file_id: str):
    if file_id not in download_storage: raise HTTPException(status_code=404, detail="Link expired.")
    data = download_storage[file_id]
    
    if not os.path.exists(data['path']):
         raise HTTPException(status_code=404, detail="File deleted.")

    return FileResponse(
        path=data['path'], 
        filename=sanitize_filename(data['filename']),
        media_type='audio/mpeg'
    )

@app.post("/api/batch", response_model=JobStatusResponse)
async def create_batch_job(request: BatchRequest, background_tasks: BackgroundTasks):
    job_id = str(uuid.uuid4())
    jobs[job_id] = { "status": "queued", "progress": "0/" + str(len(request.tracks)) }
    background_tasks.add_task(process_batch_job, job_id, request.tracks, request.collection_name)
    return JobStatusResponse(job_id=job_id, status="queued", progress="0/" + str(len(request.tracks)))

@app.get("/api/job/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str):
    if job_id not in jobs: raise HTTPException(status_code=404, detail="Job not found")
    job = jobs[job_id]
    download_url = None
    if job['status'] == 'done':
        download_url = f"/api/job/{job_id}/download"
    return JobStatusResponse(
        job_id=job_id, 
        status=job['status'], 
        progress=job.get('progress', ''),
        error=job.get('error'),
        download_url=download_url
    )

@app.get("/api/job/{job_id}/download")
async def download_job_zip(job_id: str):
    if job_id not in jobs or jobs[job_id].get('status') != 'done':
         raise HTTPException(status_code=400, detail="Job not ready")
    zip_path = jobs[job_id]['zip_path']
    if not os.path.exists(zip_path): raise HTTPException(status_code=404, detail="File lost")
    
    return FileResponse(zip_path, filename=os.path.basename(zip_path), media_type='application/zip')

@app.get("/")
def health_check():
    return {"status": "ok", "service": "Spotidown API"}

if __name__ == "__main__":
    # Listen on all interfaces for VPS access
    # reload=False for production (saves CPU)
    uvicorn.run("main:app", host="0.0.0.0", port=12065, reload=False)
