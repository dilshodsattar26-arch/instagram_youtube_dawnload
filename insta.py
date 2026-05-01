#!/usr/bin/env python3
"""
pip install requests yt-dlp
python video_bot.py
"""



import os, re, time, logging, tempfile, threading
from pathlib import Path
from datetime import datetime
from collections import defaultdict

import requests
import yt_dlp


# ══════════════════════════════════════════
BOT_TOKEN = "8168505753:AAE-x9bxqUPBI8Ue9rkj0HEdSV0OTcWtyEg"
ADMIN_ID  = 8057013675
MAX_MB    = 50
DL_DIR    = tempfile.gettempdir()
API       = f"https://api.telegram.org/bot{BOT_TOKEN}"
# ══════════════════════════════════════════

logging.basicConfig(format="%(asctime)s | %(message)s", datefmt="%H:%M:%S", level=logging.INFO)
log = logging.getLogger("Bot")

stats = {"dl": 0, "users": set(), "plat": defaultdict(int), "start": datetime.now()}
user_data = {}  # {user_id: {url, platform}}

# ─── Telegram API yordamchi funksiyalar ───────────────────────────────────────

def api(method, **kwargs):
    try:
        r = requests.post(f"{API}/{method}", json=kwargs, timeout=30)
        return r.json()
    except Exception as e:
        log.error("API xato: %s", e)
        return {}


def send(chat_id, text, reply_markup=None):
    data = {"chat_id": chat_id, "text": text}
    if reply_markup:
        data["reply_markup"] = reply_markup
    return api("sendMessage", **data)

def edit(chat_id, msg_id, text):
    api("editMessageText", chat_id=chat_id, message_id=msg_id, text=text)

def delete(chat_id, msg_id):
    api("deleteMessage", chat_id=chat_id, message_id=msg_id)

def answer_cb(cb_id):
    api("answerCallbackQuery", callback_query_id=cb_id)

def send_video(chat_id, path, caption):
    with open(path, "rb") as f:
        requests.post(
            f"{API}/sendVideo",
            data={"chat_id": chat_id, "caption": caption, "supports_streaming": True},
            files={"video": f},
            timeout=120,
        )


# ─── Platform ─────────────────────────────────────────────────────────────────

PATTERNS = {
    "youtube":   re.compile(r"(https?://)?(www\.)?(youtube\.com|youtu\.be)/\S+"),
    "instagram": re.compile(r"(https?://)?(www\.)?instagram\.com/\S+"),
    "tiktok":    re.compile(r"(https?://)?(www\.|vm\.)?tiktok\.com/\S+"),
}
PLAT = {
    "youtube":   {"e": "▶️", "n": "YouTube",   "c": "🔴"},
    "instagram": {"e": "📸", "n": "Instagram", "c": "🟣"},
    "tiktok":    {"e": "🎵", "n": "TikTok",    "c": "⚫"},
}


def detect(url):
    for name, pat in PATTERNS.items():
        if pat.search(url):
            return name
    return None

# ─── yt-dlp ───────────────────────────────────────────────────────────────────

FORMATS = {
    "hd":  "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
    "sd":  "bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480]/best",
    "low": "worst[ext=mp4]/worst",
}
QLABELS = {"hd": "🔥 HD 1080p", "sd": "⚡ SD 480p", "low": "💨 Low"}


def download_video(url, quality):
    out = os.path.join(DL_DIR, "%(id)s.%(ext)s")
    opts = {
        "format": FORMATS[quality],
        "outtmpl": out,
        "quiet": True,
        "no_warnings": True,
        "merge_output_format": "mp4",
        "socket_timeout": 30,
        "retries": 3,
        "postprocessors": [{"key": "FFmpegVideoConvertor", "preferedformat": "mp4"}],
        "http_headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
        },
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info  = ydl.extract_info(url, download=True)
        title = (info.get("title") or "Video")[:80]
        dur   = info.get("duration") or 0
        raw   = ydl.prepare_filename(info)

    mp4  = Path(raw).with_suffix(".mp4")
    path = str(mp4) if mp4.exists() else raw
    m, s = divmod(int(dur), 60)
    return path, title, f"{m:02d}:{s:02d}"

# ─── Inline keyboard ──────────────────────────────────────────────────────────

def quality_kb():
    return {
        "inline_keyboard": [
            [
                {"text": "🔥 HD 1080p", "callback_data": "q_hd"},
                {"text": "⚡ SD 480p",  "callback_data": "q_sd"},
            ],
            [{"text": "💨 Low (eng tez)", "callback_data": "q_low"}],
            [{"text": "❌ Bekor",          "callback_data": "q_cancel"}],
        ]
    }

# ─── Xabarlarni qayta ishlash ─────────────────────────────────────────────────

def handle_message(msg):
    chat_id = msg["chat"]["id"]
    user    = msg.get("from", {})
    uid     = user.get("id")
    text    = msg.get("text", "")
    stats["users"].add(uid)

    if text == "/start":
        send(chat_id,
            f"👋 Salom, {user.get('first_name', '')}!\n\n"
            "🎬 Legend Video Downloader\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "▶️  YouTube — video, shorts\n"
            "📸  Instagram — reels, post\n"
            "🎵  TikTok — video\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "📌 Havola yuboring — qolganini men qilaman!"
        )

    elif text == "/help":
        send(chat_id,
            "📖 Yordam\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "1️⃣  Havola yuboring\n"
            "2️⃣  Sifat tanlang\n"
            "3️⃣  Video yuklab beriladi ✅\n\n"
            "/start /help /stats\n\n"
            "⚠️  50 MB dan katta fayllar yuborilmaydi."
        )

    elif text == "/stats":
        up = datetime.now() - stats["start"]
        h, r = divmod(int(up.total_seconds()), 3600)
        m = r // 60
        send(chat_id,
            f"📊 Statistika\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"⬇️  Yuklashlar: {stats['dl']}\n"
            f"👥  Foydalanuvchilar: {len(stats['users'])}\n"
            f"▶️  YouTube: {stats['plat']['youtube']}\n"
            f"📸  Instagram: {stats['plat']['instagram']}\n"
            f"🎵  TikTok: {stats['plat']['tiktok']}\n\n"
            f"⏱  Ishlash vaqti: {h}s {m}d"
        )

    elif text.startswith("/broadcast"):
        if uid != ADMIN_ID:
            send(chat_id, "⛔ Siz admin emassiz!")
            return
        body = text.replace("/broadcast", "", 1).strip()
        if not body:
            send(chat_id, "Ishlatish: /broadcast <xabar>")
            return
        ok = fail = 0
        for u in stats["users"]:
            try: send(u, f"📢 Admin xabari:\n\n{body}"); ok += 1
            except: fail += 1
        send(chat_id, f"✅ Yuborildi: {ok}\n❌ Xato: {fail}")

    elif text and not text.startswith("/"):
        platform = detect(text)
        if not platform:
            send(chat_id,
                "❌ Havola tanilmadi!\n\n"
                "YouTube, Instagram yoki TikTok havolasini yuboring.\n\n"
                "Misol:\nhttps://youtu.be/xxxxx\nhttps://www.tiktok.com/@user/video/xxxxx"
            )
            return
        p = PLAT[platform]
        user_data[uid] = {"url": text.strip(), "platform": platform}
        send(chat_id,
            f"{p['c']} {p['n']} havolasi aniqlandi!\n\n🎚 Sifatni tanlang:",
            reply_markup=quality_kb()
        )


def handle_callback(cb):
    chat_id = cb["message"]["chat"]["id"]
    msg_id  = cb["message"]["message_id"]
    uid     = cb["from"]["id"]
    data    = cb["data"]
    answer_cb(cb["id"])

    if data == "q_cancel":
        edit(chat_id, msg_id, "❌ Bekor qilindi.")
        return

    quality = data.replace("q_", "")
    udata   = user_data.get(uid)
    if not udata:
        edit(chat_id, msg_id, "❌ Havola topilmadi. Qaytadan yuboring.")
        return

    url, platform = udata["url"], udata["platform"]
    p      = PLAT[platform]
    qlabel = QLABELS[quality]

    edit(chat_id, msg_id,
        f"{p['c']} {p['n']} yuklanmoqda...\n"
        f"📐 Sifat: {qlabel}\n\n⏳ Biroz kuting..."
    )

    def do():
        try:
            file_path, title, duration = download_video(url, quality)
            size_mb = os.path.getsize(file_path) / (1024 * 1024)

            if size_mb > MAX_MB:
                os.remove(file_path)
                edit(chat_id, msg_id,
                    f"⚠️ Fayl juda katta!\n"
                    f"📦 Hajm: {size_mb:.1f} MB (limit: {MAX_MB} MB)\n\n"
                    f"💡 SD yoki Low sifat tanlang."
                )
                return

            edit(chat_id, msg_id, "📤 Yuborilmoqda...")
            send_video(chat_id, file_path,
                f"{p['e']} {title}\n"
                f"⏱ {duration}  📦 {size_mb:.1f} MB  📐 {qlabel}"
            )
            delete(chat_id, msg_id)
            os.remove(file_path)

            stats["dl"] += 1
            stats["plat"][platform] += 1
            log.info("✅ [%s] %s — %.1f MB", platform.upper(), title, size_mb)

            send(ADMIN_ID,
                f"📥 Yangi yuklab olish!\n"
                f"👤 {cb['from'].get('full_name', cb['from'].get('first_name',''))} ({uid})\n"
                f"🌐 {p['n']} | {qlabel}\n"
                f"🎬 {title}\n📦 {size_mb:.1f} MB"
            )

        except yt_dlp.utils.DownloadError as e:
            err = str(e).lower()
            reason = "Video mavjud emas yoki o'chirilgan"
            if "private"   in err: reason = "🔒 Video xususiy"
            if "geo"       in err: reason = "🌍 Geografik cheklov"
            if "copyright" in err: reason = "©️ Mualliflik huquqi bloki"
            if "login"     in err: reason = "🔑 Login talab qilinadi"
            edit(chat_id, msg_id, f"❌ Yuklab bo'lmadi!\nSabab: {reason}")

        except Exception as e:
            log.error("Xato: %s", e)
            edit(chat_id, msg_id, "⚠️ Kutilmagan xatolik. Keyinroq urinib ko'ring.")

    threading.Thread(target=do, daemon=True).start()

# ─── Polling ──────────────────────────────────────────────────────────────────

def main():
    log.info("🤖 Legend Bot ishga tushdi!")
    send(ADMIN_ID, f"🚀 Bot ishga tushdi!\n🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    offset = 0
    while True:
        try:
            res = requests.get(f"{API}/getUpdates", params={"offset": offset, "timeout": 25}, timeout=30)
            updates = res.json().get("result", [])
            for upd in updates:
                offset = upd["update_id"] + 1
                if "message" in upd:
                    threading.Thread(target=handle_message, args=(upd["message"],), daemon=True).start()
                elif "callback_query" in upd:
                    threading.Thread(target=handle_callback, args=(upd["callback_query"],), daemon=True).start()
        except Exception as e:
            log.error("Polling xato: %s", e)
            time.sleep(3)

if __name__ == "__main__":
    main()
