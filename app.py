from flask import Flask, request, jsonify
import yt_dlp

app = Flask(__name__)


def extract_youtube_hls(url: str):
    if not url:
        return None

    ydl_opts = {
        "quiet": True,
        "skip_download": True,
        "format": "best[protocol=m3u8]/best",
        "noplaylist": True,
    }

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
        "service": "GEL IPTV YouTube HLS Extractor"
    })


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=8080
    )
