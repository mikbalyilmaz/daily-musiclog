import os
from urllib.parse import urlparse, parse_qs
from googleapiclient.discovery import build

# API Key:
API_KEY = "AIzaSyDsD2Gaf-uVZv_aGPzGlnQlwvYywr1TwyM"

def extract_video_id(url: str):
    u = urlparse(url)
    if "youtu.be" in u.netloc:
        return u.path.strip("/")
    if "youtube.com" in u.netloc:
        qs = parse_qs(u.query)
        return qs.get("v", [None])[0]
    return None

def get_video_title(video_id):
    # Madde 1: API ile otomatik başlık çekme
    youtube = build("youtube", "v3", developerKey=API_KEY)
    request = youtube.videos().list(part="snippet", id=video_id)
    response = request.execute()
    if response["items"]:
        return response["items"][0]["snippet"]["title"]
    return "Unknown Title"

def make_thumbnail(video_id: str):
    # Madde 5: En yüksek çözünürlüklü görsel
    return f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg"