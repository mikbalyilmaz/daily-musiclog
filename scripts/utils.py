import os
from urllib.parse import urlparse, parse_qs
from googleapiclient.discovery import build

API_KEY = "AIzaSyDsD2Gaf-uVZv_aGPzGlnQlwvYywr1TwyM"

def extract_video_id(url: str):
    # Terminalden yapıştırılan ters slash (\) işaretlerini temizler
    url = url.replace("\\", "")
    u = urlparse(url)
    if "youtu.be" in u.netloc:
        return u.path.strip("/")
    if "youtube.com" in u.netloc:
        qs = parse_qs(u.query)
        v_list = qs.get("v", [None])
        return v_list[0] if v_list else None
    return None

def get_video_title(video_id):
    if not video_id:
        return "Unknown Title"
    youtube = build("youtube", "v3", developerKey=API_KEY)
    request = youtube.videos().list(part="snippet", id=video_id)
    response = request.execute()
    if response.get("items"):
        return response["items"][0]["snippet"]["title"]
    return "Unknown Title"

def make_thumbnail(video_id: str):
    return f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg"
