import os
import googleapiclient.discovery
import googleapiclient.errors
import whisper
import ffmpeg
import yt_dlp
from moviepy.editor import VideoFileClip
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.http import MediaFileUpload
from datetime import datetime, timedelta

def get_trending_videos(api_key, region_code="US"):
    youtube = googleapiclient.discovery.build("youtube", "v3", developerKey=api_key)
    request = youtube.videos().list(
        part="snippet,contentDetails,statistics",
        chart="mostPopular",
        regionCode=region_code,
        maxResults=5
    )
    response = request.execute()
    return [(item["id"], item["snippet"]["title"]) for item in response["items"]]

def download_video(video_id):
    ydl_opts = {
        'format': 'best',
        'outtmpl': f'{video_id}.mp4'
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([f'https://www.youtube.com/watch?v={video_id}'])
    return f"{video_id}.mp4"

def extract_highlight(video_path):
    model = whisper.load_model("base")
    result = model.transcribe(video_path)
    highlights = [seg for seg in result['segments'] if seg['no_speech_prob'] < 0.5]
    start_time = highlights[0]['start'] if highlights else 0
    end_time = min(start_time + 60, VideoFileClip(video_path).duration)
    edited_video_path = f"highlight_{video_path}"
    ffmpeg.input(video_path, ss=start_time, to=end_time).output(edited_video_path).run()
    return edited_video_path

def create_thumbnail(video_path):
    thumbnail_path = video_path.replace(".mp4", ".jpg")
    clip = VideoFileClip(video_path)
    clip.save_frame(thumbnail_path, t=clip.duration / 2)
    return thumbnail_path

def upload_to_youtube(video_path, title, description, credentials_path, schedule_time=None):
    SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
    flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
    credentials = flow.run_local_server(port=0)
    youtube = googleapiclient.discovery.build("youtube", "v3", credentials=credentials)
    request_body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": ["shorts", "trending"],
            "categoryId": "22"
        },
        "status": {
            "privacyStatus": "private" if schedule_time else "public",
            "publishAt": schedule_time.isoformat() if schedule_time else None
        }
    }
    media = MediaFileUpload(video_path, mimetype='video/mp4', resumable=True)
    request = youtube.videos().insert(
        part="snippet,status",
        body=request_body,
        media_body=media
    )
    response = request.execute()
    video_id = response["id"]
    print("Uploaded video ID:", video_id)
    
    # Upload custom thumbnail
    thumbnail_path = create_thumbnail(video_path)
    request = youtube.thumbnails().set(
        videoId=video_id,
        media_body=MediaFileUpload(thumbnail_path, mimetype='image/jpeg')
    )
    request.execute()
    print("Thumbnail uploaded for video ID:", video_id)

if __name__ == "__main__":
    API_KEY = "YOUR_YOUTUBE_API_KEY"
    CREDENTIALS_PATH = "client_secrets.json"
    SCHEDULE_DELAY_HOURS = 2  # Delay in hours for scheduling uploads
    
    trending_videos = get_trending_videos(API_KEY)
    for index, (video_id, title) in enumerate(trending_videos):
        video_path = download_video(video_id)
        short_video = extract_highlight(video_path)
        schedule_time = datetime.utcnow() + timedelta(hours=SCHEDULE_DELAY_HOURS * (index + 1))
        upload_to_youtube(short_video, title, "Trending video highlight", CREDENTIALS_PATH, schedule_time)
