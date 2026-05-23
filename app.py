# =====================================
# GEL IPTV YOUTUBE HLS EXTRACTOR
# Backend: Flask + yt-dlp + optional cookies
# =====================================

from flask import Flask, request, jsonify
import yt_dlp
import os
import base64
import tempfile

app = Flask(__name__)


def build_cookie_file():
    try:
        cookies_b64 = os.environ.get("YT_COOKIES_B64", "").strip()

        if not cookies_b64:
            return None

        cookies_text = base64.b64decode(
            cookies_b64.encode("utf-8")
        ).decode("utf-8", errors="ignore")

        if not cookies_text.strip():
            return None

        tmp = tempfile.NamedTemporaryFile(
            mode="w",
            delete=False,
            suffix=".txt"
        )

        tmp.write(cookies_text)
        tmp.flush()
        tmp.close()

        return tmp.name

    except Exception:
        return None


def extract_youtube_hls(url: str):
    if not url:
        return None

    cookie_file = build_cookie_file()

    ydl_opts = {
        "quiet": True,
        "skip_download": True,
        "format": "best[protocol=m3u8]/best",
        "noplaylist": True,
        "extractor_args": {
            "youtube": {
                "player_client": ["android", "web"]
            }
        }
    }

    if cookie_file:
        ydl_opts["cookiefile"] = cookie_file

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

            formats = info.get("formats", [])

            hls_formats = [
                f for f in formats
                if "m3u8" in str(f.get("protocol", "")).lower()
                and f.get("url")
            ]

            if hls_formats:
                best = sorted(
                    hls_formats,
                    key=lambda f: f.get("height") or 0,
                    reverse=True
                )[0]

                return {
                    "type": "youtube_hls",
                    "title": info.get("title", ""),
                    "format_id": best.get("format_id", ""),
                    "height": best.get("height", 0),
                    "url": best.get("url", "")
                }

            direct_url = info.get("url", "")

            if direct_url:
                return {
                    "type": "youtube_direct",
                    "title": info.get("title", ""),
                    "format_id": info.get("format_id", ""),
                    "height": info.get("height", 0),
                    "url": direct_url
                }

    finally:
        try:
            if cookie_file and os.path.exists(cookie_file):
                os.remove(cookie_file)
        except Exception:
            pass

    return None


@app.route("/extract", methods=["GET"])
def extract():
    url = request.args.get("url", "").strip()

    if not url:
        return jsonify({
            "ok": False,
            "error": "Missing url"
        }), 400

    try:
        result = extract_youtube_hls(url)

        if not result or not result.get("url"):
            return jsonify({
                "ok": False,
                "error": "No stream found"
            }), 404

        return jsonify({
            "ok": True,
            "result": result
        })

    except Exception as e:
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500


@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "ok": True,
        "service": "GEL IPTV YouTube HLS Extractor",
        "cookies_enabled": bool(os.environ.get("YT_COOKIES_B64", "").strip())
    })


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=8080
    )
