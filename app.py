# ===================================== 
# GEL IPTV YOUTUBE HLS EXTRACTOR
# Flask + yt-dlp + Render cookies support
# =====================================

from flask import Flask, request, jsonify, Response
import yt_dlp
import os
import base64
import tempfile
import time
import re

app = Flask(__name__)


# =====================================
# COOKIE FILE FROM RENDER ENV
# =====================================

def build_cookie_file():
    try:
        cookies_b64 = os.environ.get(
            "YT_COOKIES_B64",
            ""
        ).strip()

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


# =====================================
# EXPIRE PARSER
# =====================================

def parse_expire_from_url(url):
    try:
        match = re.search(r"/expire/(\d+)", url)

        if match:
            return int(match.group(1))

        match = re.search(r"[?&]expire=(\d+)", url)

        if match:
            return int(match.group(1))

    except Exception:
        pass

    return 0


# =====================================
# YOUTUBE EXTRACTOR
# =====================================

def extract_youtube_hls(url: str):
    if not url:
        return None

    cookie_file = build_cookie_file()

    ydl_opts = {
        "quiet": True,
        "skip_download": True,
        "noplaylist": True,
        "format": "best[protocol=m3u8]/best",
        "extractor_args": {
            "youtube": {
                "player_client": [
                    "android",
                    "web"
                ]
            }
        }
    }

    if cookie_file:
        ydl_opts["cookiefile"] = cookie_file

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:

            info = ydl.extract_info(
                url,
                download=False
            )

            formats = info.get(
                "formats",
                []
            )

            hls_formats = []

            for f in formats:

                protocol = str(
                    f.get("protocol", "")
                ).lower()

                stream_url = f.get(
                    "url",
                    ""
                )

                if (
                    stream_url and
                    "m3u8" in protocol
                ):
                    hls_formats.append(f)

            if hls_formats:

                best = sorted(
                    hls_formats,
                    key=lambda f: f.get("height") or 0,
                    reverse=True
                )[0]

                stream_url = best.get(
                    "url",
                    ""
                )

                expire_ts = parse_expire_from_url(
                    stream_url
                )

                return {
                    "type": "youtube_hls",
                    "source_url": url,
                    "title": info.get("title", ""),
                    "video_id": info.get("id", ""),
                    "format_id": best.get("format_id", ""),
                    "height": best.get("height", 0),
                    "protocol": best.get("protocol", ""),
                    "m3u8_url": stream_url,
                    "url": stream_url,
                    "expire": expire_ts,
                    "expires_in_seconds": max(
                        0,
                        expire_ts - int(time.time())
                    ) if expire_ts else 0,
                    "temporary": True
                }

            direct_url = info.get(
                "url",
                ""
            )

            if direct_url:

                expire_ts = parse_expire_from_url(
                    direct_url
                )

                return {
                    "type": "youtube_direct",
                    "source_url": url,
                    "title": info.get("title", ""),
                    "video_id": info.get("id", ""),
                    "format_id": info.get("format_id", ""),
                    "height": info.get("height", 0),
                    "protocol": info.get("protocol", ""),
                    "m3u8_url": direct_url,
                    "url": direct_url,
                    "expire": expire_ts,
                    "expires_in_seconds": max(
                        0,
                        expire_ts - int(time.time())
                    ) if expire_ts else 0,
                    "temporary": True
                }

    finally:
        try:
            if cookie_file and os.path.exists(cookie_file):
                os.remove(cookie_file)
        except Exception:
            pass

    return None


# =====================================
# JSON EXTRACT ENDPOINT
# =====================================

@app.route("/extract", methods=["GET"])
def extract():
    url = request.args.get(
        "url",
        ""
    ).strip()

    if not url:
        return jsonify({
            "ok": False,
            "error": "Missing url"
        }), 400

    try:
        result = extract_youtube_hls(
            url
        )

        if not result or not result.get("url"):
            return jsonify({
                "ok": False,
                "error": "No stream found"
            }), 404

        return jsonify({
            "ok": True,
            "cookies_enabled": bool(
                os.environ.get(
                    "YT_COOKIES_B64",
                    ""
                ).strip()
            ),
            "result": result
        })

    except Exception as e:
        return jsonify({
            "ok": False,
            "cookies_enabled": bool(
                os.environ.get(
                    "YT_COOKIES_B64",
                    ""
                ).strip()
            ),
            "error": str(e)
        }), 500


# =====================================
# M3U EXPORT ENDPOINT
# =====================================

@app.route("/m3u", methods=["GET"])
def m3u():
    url = request.args.get(
        "url",
        ""
    ).strip()

    name = request.args.get(
        "name",
        "YouTube Live"
    ).strip()

    if not url:
        return Response(
            "#EXTM3U\n# ERROR: Missing url\n",
            mimetype="application/vnd.apple.mpegurl"
        )

    try:
        result = extract_youtube_hls(
            url
        )

        if not result or not result.get("url"):
            return Response(
                "#EXTM3U\n# ERROR: No stream found\n",
                mimetype="application/vnd.apple.mpegurl"
            )

        playlist = f"""#EXTM3U
#EXTINF:-1 tvg-id="YouTube" tvg-logo="noimage.png" group-title="YouTube Live", {name}
{result.get("url", "")}
"""

        return Response(
            playlist,
            mimetype="application/vnd.apple.mpegurl"
        )

    except Exception as e:
        return Response(
            f"#EXTM3U\n# ERROR: {str(e)}\n",
            mimetype="application/vnd.apple.mpegurl"
        )


# =====================================
# HEALTH
# =====================================

@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "ok": True,
        "service": "GEL IPTV YouTube HLS Extractor",
        "cookies_enabled": bool(
            os.environ.get(
                "YT_COOKIES_B64",
                ""
            ).strip()
        ),
        "endpoints": {
            "json": "/extract?url=YOUTUBE_URL",
            "m3u": "/m3u?url=YOUTUBE_URL&name=CHANNEL_NAME"
        }
    })


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=8080
    )
