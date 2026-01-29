from urllib.parse import urlparse, parse_qs

def extract_video_id(url: str):
    u = urlparse(url)
    if "youtu.be" in u.netloc:
        return u.path.strip("/")
    if "youtube.com" in u.netloc:
        qs = parse_qs(u.query)
        return qs.get("v", [None])[0]
    return None

def make_thumbnail(video_id: str):
    return f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg"

