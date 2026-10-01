"""
=============================================================================
DISCORD PRO MODERATION, STATBOT, 16 LOGS, TICKET, WELCOME & CONFIG BOT (PYTHON 3.10+)
- a!stat: Statbot tipli modern, dark, premium aktivlik kartı və statistikası
- a!statboard: Server aktivlik liderlik cədvəli (1 Day / 7 Days / 14 Days düymələrlə)
- Özelleştirilebilir Karşılama Mesajı (Kanal ayarlanabilir ve otomatik silinebilir)
- a!config: Yalnızca sunucu kurucusuna (349152405927231488) özel yönetim paneli
- Çoxsaylı rol seçimi (Ban yetki, Kick yetki, Timeout yetki, Warn yetki, Log yetki, Auto-role)
- Ağıllı səhv təklifləri (Did you mean?), a!gay effekti, 16 log kanalı, Ticket, Snipe və Əyləncə
=============================================================================
"""

import os
import io
import time
import math
import json
import random
import base64
import asyncio
import re
import difflib
import datetime
import urllib.parse
from typing import Optional, List, Dict, Any, Tuple

import aiohttp
import discord
from discord.ext import commands
from discord import ui
from PIL import Image, ImageDraw, ImageFont

# =============================================================================
# SABİT QAYDALAR VƏ İLKİN KONFİQURASİYA
# =============================================================================
FOUNDER_ID = 349152405927231488
DEFAULT_WELCOME_CHANNEL_ID = 1541541365735751730
WARN_ROLE_ID = 1552360072213172247
LOGS_CATEGORY_ID = 1552366205333934081
PROOF_LOG_CHANNEL_ID = 1541541519578628117
INITIAL_MOD_ROLES = [1541540311191523499, 1554257025070932038, 1541567081642725406]
PROOF_REVIEWER_ROLES = [1541540311191523499, 1554257025070932038, 1541567081642725406]
IMMUNITY_ROLE_ID = 1554266448036102255
ALLOWED_PING_ROLE_IDS = [1541567081642725406, 1554257025070932038]

def can_review_proofs(member: discord.Member) -> bool:
    """Yalnızca bu 3 role sahip olanlar veya Kurucu kanıtları inceleyip onaylayabilir/reddedebilir"""
    if not member:
        return False
    if member.id == FOUNDER_ID:
        return True
    if member.guild and member.id == member.guild.owner_id:
        return True
    return any(r.id in PROOF_REVIEWER_ROLES for r in getattr(member, "roles", []))

def has_immunity(member: discord.Member) -> bool:
    """Dokunulmazlık rolüne (1554266448036102255) sahip üyelere hiçbir yetkili ceza uygulayamaz"""
    if not member or not hasattr(member, "roles"):
        return False
    return any(r.id == IMMUNITY_ROLE_ID for r in member.roles)

def is_role_mention_allowed(message: discord.Message) -> bool:
    """
    Yalnızca yöneticiler tüm rolleri etiketleyebilir.
    Normal üyeler ise yalnızca ALLOWED_PING_ROLE_IDS (1541567081642725406, 1554257025070932038) rollerine sahipse rol etiketleyebilir
    veya bu izinli rolleri etiketleyebilir. Diğer durumlarda rol etiketleme kesinlikle engellenir.
    """
    if not message.guild or message.author.bot:
        return True

    # 1. Yönetici, Sunucu Sahibi ve Kurucu serbesttir
    if (getattr(message.author, "guild_permissions", None) and message.author.guild_permissions.administrator) or \
       message.author.id == FOUNDER_ID or \
       (message.guild and message.author.id == message.guild.owner_id):
        return True

    # 2. İzinli rollere (1541567081642725406 ve 1554257025070932038) sahip olanlar serbesttir
    author_role_ids = [r.id for r in getattr(message.author, "roles", [])]
    if any(r_id in ALLOWED_PING_ROLE_IDS for r_id in author_role_ids):
        return True

    # 3. Normal kullanıcılar için kontrol:
    # @everyone ve @here yasaktır
    if message.mention_everyone:
        return False

    # Metindeki ham <@&rol_id> etiketleri ve message.role_mentions
    raw_role_mentions = [int(x) for x in re.findall(r'<@&(\d+)>', message.content)]
    all_mentioned_role_ids = set([r.id for r in message.role_mentions] + raw_role_mentions)

    if all_mentioned_role_ids:
        for r_id in all_mentioned_role_ids:
            if r_id not in ALLOWED_PING_ROLE_IDS:
                return False

    return True

LOG_CHANNELS = {
    "ban": 1552366207389147188,
    "kick": 1552366209184432281,
    "timeout": 1552366210832801922,
    "untimeout": 1552366212602798151,
    "warn": 1552366214456549376,
    "message": 1552366216041992272,
    "role": 1552366217677766779,
    "nickname": 1552366220488212570,
    "channel": 1552366222182711318,
    "server": 1552366224120479834,
    "member": 1552366226208981023,
    "voice": 1552366227500957839,
    "security": 1552366229866553354,
    "invite": 1552366234274758696,
    "webhook": 1552366236451479592,
    "boost": 1552366237529415752,
}

DATA_FILE = "bot_database.json"
BOT_START_TIME = datetime.datetime.now(datetime.timezone.utc)

last_deleted_message = {}
last_edited_message = {}

# =============================================================================
# MƏLUMAT BAZASI (DATABASE) İDARƏETMƏSİ (JSON)
# =============================================================================
def load_data():
    if not os.path.exists(DATA_FILE):
        default_data = {
            "warns": {},
            "afk": {},
            "config": {
                "welcome_channel_id": DEFAULT_WELCOME_CHANNEL_ID,
                "welcome_delete_seconds": 15,
                "welcome_enabled": True,
                "warn_roles": [WARN_ROLE_ID],
                "ban_roles": [],
                "kick_roles": [],
                "timeout_roles": [],
                "log_roles": [],
                "autorole_ids": [],
                "ticket_category_id": LOGS_CATEGORY_ID
            },
            "log_counter": {
                "BAN": 0, "KICK": 0, "TIMEOUT": 0, "UNTIMEOUT": 0,
                "WARN": 0, "MSG": 0, "ROLE": 0, "NICK": 0,
                "CHAN": 0, "SERV": 0, "MEM": 0, "VOICE": 0,
                "SEC": 0, "INV": 0, "HOOK": 0, "BOOST": 0, "PROOF": 0
            },
            "stats": {},
            "proof_cases": {}
        }
        save_data(default_data)
        return default_data
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        try:
            loaded = json.load(f)
            loaded.setdefault("stats", {})
            loaded.setdefault("proof_cases", {})
            return loaded
        except Exception:
            return {"warns": {}, "afk": {}, "config": {}, "log_counter": {}, "stats": {}, "proof_cases": {}}

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

db = load_data()

def get_config() -> dict:
    conf = db.setdefault("config", {})
    conf.setdefault("welcome_channel_id", DEFAULT_WELCOME_CHANNEL_ID)
    conf.setdefault("welcome_delete_seconds", 15)
    conf.setdefault("welcome_enabled", True)
    conf.setdefault("warn_roles", [WARN_ROLE_ID])
    conf.setdefault("ban_roles", [])
    conf.setdefault("kick_roles", [])
    conf.setdefault("timeout_roles", [])
    conf.setdefault("log_roles", [])
    conf.setdefault("autorole_ids", [])
    conf.setdefault("ticket_category_id", LOGS_CATEGORY_ID)
    return conf

def get_next_log_id(prefix: str) -> str:
    counter = db.setdefault("log_counter", {})
    current = counter.get(prefix, 0) + 1
    counter[prefix] = current
    save_data(db)
    return f"{prefix}-{current:06d}"

# =============================================================================
# QADAĞAN OLUNMUŞ SÖZLƏR (BLACKLIST) VƏ TƏHLÜKƏSİZLİK QORUMASI
# =============================================================================
def check_blacklisted_content(content: str) -> Optional[str]:
    """
    Qadağan olunmuş ifadələri yoxlayır:
    1. .gg
    2. https
    3. /
    4. capulcu / çapulcu
    5. yaz gir (və ya yaz g1r, y4z gir, y4z g1r - eyni cümlədə/mesajda)
    Returns: uyğun gələn ifadə və ya None
    """
    if not content:
        return None

    raw_lower = content.lower()

    # 1. .gg yoxlanışı
    if ".gg" in raw_lower:
        return ".gg"

    # 2. https yoxlanışı
    if "https" in raw_lower:
        return "https"

    # 3. / yoxlanışı
    if "/" in content:
        return "/"

    # 4. capulcu / çapulcu yoxlanışı
    if "capulcu" in raw_lower or "çapulcu" in raw_lower:
        return "capulcu"

    # 5. yaz ... gir kombinasiyası (yaz gir, yaz g1r, y4z gir, y4z g1r)
    # Hərflərin rəqəmlə əvəzlənməsi bypass-larını aradan qaldırırıq (4 -> a, 1 -> i, ı -> i)
    norm = raw_lower.replace("4", "a").replace("1", "i").replace("ı", "i")
    if "yaz" in norm and "gir" in norm:
        return "yaz gir"

    return None

def is_exempt_from_blacklist(member: discord.Member) -> bool:
    """Kurucu, sunucu sahibi, dokunulmazlık rolü, admin ve moderatörler blacklist filtresinden muaftır"""
    if not member or member.bot:
        return True
    if has_immunity(member):
        return True
    if member.id == FOUNDER_ID:
        return True
    if member.guild and member.id == member.guild.owner_id:
        return True
    if member.guild_permissions.administrator or member.guild_permissions.manage_guild or member.guild_permissions.manage_messages:
        return True
    conf = get_config()
    exempt_roles = set(INITIAL_MOD_ROLES + PROOF_REVIEWER_ROLES + [IMMUNITY_ROLE_ID] + conf.get("ban_roles", []) + conf.get("kick_roles", []) + conf.get("timeout_roles", []) + conf.get("warn_roles", []))
    if any(r.id in exempt_roles for r in getattr(member, "roles", [])):
        return True
    return False

async def auto_delete_message(msg: discord.Message, delay: int = 4):
    await asyncio.sleep(delay)
    try:
        await msg.delete()
    except Exception:
        pass

# =============================================================================
# STATBOT SİSTEMİ (TRACKING, REAL-TIME DURATION, RANK & DARK CARD GENERATOR)
# =============================================================================
def get_stat_db() -> dict:
    return db.setdefault("stats", {})

def format_duration(seconds: int) -> str:
    if seconds <= 0:
        return "0h"
    hours, remainder = divmod(int(seconds), 3600)
    minutes, _ = divmod(remainder, 60)
    if hours >= 24:
        days, hours = divmod(hours, 24)
        return f"{days}d {hours}h"
    elif hours > 0:
        return f"{hours}h {minutes}m"
    elif minutes > 0:
        return f"{minutes}m"
    else:
        return f"{int(seconds)}s"

def get_date_keys(days: int) -> List[str]:
    today = datetime.date.today()
    return [(today - datetime.timedelta(days=i)).strftime("%Y-%m-%d") for i in range(days)]

def record_user_message(guild_id: int, user_id: int, channel_id: int):
    g_id = str(guild_id)
    u_id = str(user_id)
    c_id = str(channel_id)
    today_str = datetime.date.today().strftime("%Y-%m-%d")

    stats = get_stat_db()
    guild_stats = stats.setdefault(g_id, {"users": {}, "active_voice": {}})
    users_map = guild_stats.setdefault("users", {})
    user_data = users_map.setdefault(u_id, {
        "messages": {},
        "channels": {},
        "voice_seconds": {},
        "voice_channels": {}
    })

    user_data["messages"][today_str] = user_data["messages"].get(today_str, 0) + 1
    user_data["channels"][c_id] = user_data["channels"].get(c_id, 0) + 1

    # Keep database optimized (prune entries older than 35 days)
    if len(user_data["messages"]) > 35:
        cutoff = (datetime.date.today() - datetime.timedelta(days=32)).strftime("%Y-%m-%d")
        user_data["messages"] = {k: v for k, v in user_data["messages"].items() if k >= cutoff}

    save_data(db)

def track_voice_state_update(guild_id: int, user_id: int, before_chan, after_chan):
    g_id = str(guild_id)
    u_id = str(user_id)
    now = datetime.datetime.now().timestamp()
    today_str = datetime.date.today().strftime("%Y-%m-%d")

    stats = get_stat_db()
    guild_stats = stats.setdefault(g_id, {"users": {}, "active_voice": {}})
    active_map = guild_stats.setdefault("active_voice", {})
    users_map = guild_stats.setdefault("users", {})

    user_data = users_map.setdefault(u_id, {
        "messages": {},
        "channels": {},
        "voice_seconds": {},
        "voice_channels": {}
    })

    # Case 1: Member left voice channel
    if before_chan is not None and after_chan is None:
        if u_id in active_map:
            session = active_map.pop(u_id)
            duration = max(0, int(now - session.get("joined_at", now)))
            c_id = str(session.get("channel_id", before_chan.id))
            user_data["voice_seconds"][today_str] = user_data["voice_seconds"].get(today_str, 0) + duration
            user_data["voice_channels"][c_id] = user_data["voice_channels"].get(c_id, 0) + duration
        save_data(db)

    # Case 2: Member joined voice channel
    elif before_chan is None and after_chan is not None:
        active_map[u_id] = {
            "channel_id": after_chan.id,
            "joined_at": now
        }
        save_data(db)

    # Case 3: Member switched voice channels
    elif before_chan is not None and after_chan is not None and before_chan.id != after_chan.id:
        if u_id in active_map:
            session = active_map.pop(u_id)
            duration = max(0, int(now - session.get("joined_at", now)))
            c_id = str(session.get("channel_id", before_chan.id))
            user_data["voice_seconds"][today_str] = user_data["voice_seconds"].get(today_str, 0) + duration
            user_data["voice_channels"][c_id] = user_data["voice_channels"].get(c_id, 0) + duration
        active_map[u_id] = {
            "channel_id": after_chan.id,
            "joined_at": now
        }
        save_data(db)

def get_user_current_active_voice_seconds(guild_id: int, user_id: int) -> Tuple[int, Optional[int]]:
    g_id = str(guild_id)
    u_id = str(user_id)
    stats = get_stat_db()
    guild_stats = stats.get(g_id, {})
    active_map = guild_stats.get("active_voice", {})
    if u_id in active_map:
        session = active_map[u_id]
        elapsed = max(0, int(datetime.datetime.now().timestamp() - session.get("joined_at", datetime.datetime.now().timestamp())))
        return elapsed, session.get("channel_id")
    return 0, None

def get_user_stat_data(guild: discord.Guild, member: discord.Member) -> dict:
    g_id = str(guild.id)
    u_id = str(member.id)
    stats = get_stat_db()
    guild_stats = stats.get(g_id, {})
    users_map = guild_stats.get("users", {})
    user_data = users_map.get(u_id, {
        "messages": {},
        "channels": {},
        "voice_seconds": {},
        "voice_channels": {}
    })

    keys_1d = get_date_keys(1)
    keys_7d = get_date_keys(7)
    keys_14d = get_date_keys(14)

    msg_map = user_data.get("messages", {})
    msg_1d = sum(msg_map.get(d, 0) for d in keys_1d)
    msg_7d = sum(msg_map.get(d, 0) for d in keys_7d)
    msg_14d = sum(msg_map.get(d, 0) for d in keys_14d)

    voice_map = user_data.get("voice_seconds", {})
    voice_1d_sec = sum(voice_map.get(d, 0) for d in keys_1d)
    voice_7d_sec = sum(voice_map.get(d, 0) for d in keys_7d)
    voice_14d_sec = sum(voice_map.get(d, 0) for d in keys_14d)

    # Real-time active voice duration for current session
    active_sec, active_chan_id = get_user_current_active_voice_seconds(guild.id, member.id)
    if active_sec > 0:
        voice_1d_sec += active_sec
        voice_7d_sec += active_sec
        voice_14d_sec += active_sec

    # Top Text Channels (Last 14 days or overall tracked)
    chans_map = user_data.get("channels", {})
    sorted_chans = sorted(chans_map.items(), key=lambda x: x[1], reverse=True)
    top_channels = []
    for cid_str, cnt in sorted_chans[:3]:
        ch = guild.get_channel(int(cid_str))
        name = f"#{ch.name}" if ch else f"#deleted-{cid_str[-4:]}"
        top_channels.append((name, cnt))

    # Top Voice Channels
    voice_chans_map = dict(user_data.get("voice_channels", {}))
    if active_sec > 0 and active_chan_id:
        ac_str = str(active_chan_id)
        voice_chans_map[ac_str] = voice_chans_map.get(ac_str, 0) + active_sec

    sorted_voice_chans = sorted(voice_chans_map.items(), key=lambda x: x[1], reverse=True)
    top_voice_channels = []
    for cid_str, secs in sorted_voice_chans[:3]:
        ch = guild.get_channel(int(cid_str))
        name = f"🔊 {ch.name}" if ch else f"🔊 voice-{cid_str[-4:]}"
        top_voice_channels.append((name, secs))

    # 14-day daily message trend for the graph
    today = datetime.date.today()
    daily_chart_data = []
    for i in reversed(range(14)):
        dt = today - datetime.timedelta(days=i)
        d_str = dt.strftime("%Y-%m-%d")
        d_label = dt.strftime("%d/%m")
        cnt = msg_map.get(d_str, 0)
        daily_chart_data.append((d_label, cnt))

    # Calculate server ranks
    msg_rank = 1
    voice_rank = 1
    ranked_users_count = 0

    for other_uid, odata in users_map.items():
        try:
            m = guild.get_member(int(other_uid))
            if m and m.bot:
                continue
        except Exception:
            pass

        ranked_users_count += 1
        other_msg_14d = sum(odata.get("messages", {}).get(d, 0) for d in keys_14d)
        if other_msg_14d > msg_14d:
            msg_rank += 1

        other_voice_14d = sum(odata.get("voice_seconds", {}).get(d, 0) for d in keys_14d)
        other_active, _ = get_user_current_active_voice_seconds(guild.id, int(other_uid))
        other_voice_14d += other_active
        if other_voice_14d > voice_14d_sec:
            voice_rank += 1

    return {
        "msg_1d": msg_1d,
        "msg_7d": msg_7d,
        "msg_14d": msg_14d,
        "voice_1d_sec": voice_1d_sec,
        "voice_7d_sec": voice_7d_sec,
        "voice_14d_sec": voice_14d_sec,
        "top_channels": top_channels,
        "top_voice_channels": top_voice_channels,
        "daily_chart_data": daily_chart_data,
        "msg_rank": msg_rank,
        "voice_rank": voice_rank,
        "total_active": max(1, ranked_users_count)
    }

def get_pil_font(size: int, bold: bool = False):
    font_candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf" if bold else "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
        "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf",
        "arialbd.ttf" if bold else "arial.ttf",
        "arial.ttf"
    ]
    for fpath in font_candidates:
        if os.path.exists(fpath):
            try:
                return ImageFont.truetype(fpath, size)
            except Exception:
                pass
    try:
        return ImageFont.load_default(size=size)
    except Exception:
        return ImageFont.load_default()

async def generate_stat_card_image(guild: discord.Guild, member: discord.Member, data: dict) -> io.BytesIO:
    width, height = 1000, 560
    card = Image.new("RGBA", (width, height), (13, 17, 23, 255))
    draw = ImageDraw.Draw(card)

    # Outer container with rounded corners and border
    draw.rounded_rectangle((15, 15, width - 15, height - 15), radius=16, fill=(22, 27, 34, 255), outline=(48, 54, 61, 255), width=2)

    font_title = get_pil_font(23, bold=True)
    font_bold = get_pil_font(16, bold=True)
    font_metric = get_pil_font(18, bold=True)
    font_regular = get_pil_font(13, bold=False)
    font_small = get_pil_font(11, bold=False)
    font_badge = get_pil_font(12, bold=True)

    # 1. Avatar fetch
    avatar_loaded = False
    try:
        avatar_url = member.display_avatar.with_format("png").with_size(128).url
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=3)) as session:
            async with session.get(avatar_url) as resp:
                if resp.status == 200:
                    raw_b = await resp.read()
                    av_img = Image.open(io.BytesIO(raw_b)).convert("RGBA")
                    av_img = av_img.resize((86, 86), Image.Resampling.LANCZOS)
                    mask = Image.new("L", (86, 86), 0)
                    ImageDraw.Draw(mask).ellipse((0, 0, 86, 86), fill=255)
                    av_img.putalpha(mask)
                    card.paste(av_img, (35, 32), av_img)
                    avatar_loaded = True
    except Exception:
        avatar_loaded = False

    if not avatar_loaded:
        draw.ellipse((35, 32, 121, 118), fill=(88, 101, 242, 255))
        initial = (member.display_name or member.name or "U")[0].upper()
        draw.text((68, 52), initial, fill=(255, 255, 255, 255), font=get_pil_font(34, bold=True))

    # Avatar glowing ring
    draw.ellipse((33, 30, 123, 120), outline=(88, 101, 242, 255), width=3)

    # User Header Info
    disp_name = member.display_name[:22]
    draw.text((140, 32), disp_name, fill=(255, 255, 255, 255), font=font_title)
    draw.text((140, 64), f"@{member.name}", fill=(139, 148, 158, 255), font=font_regular)

    created_str = member.created_at.strftime("%d.%m.%Y")
    joined_str = member.joined_at.strftime("%d.%m.%Y") if member.joined_at else "Bilinmiyor"
    draw.text((140, 92), f"📅 Created: {created_str}   •   📥 Joined: {joined_str}", fill=(139, 148, 158, 255), font=font_small)

    # Badges (Top-Right)
    # Message Rank Badge
    msg_rank_text = f"MSG RANK #{data['msg_rank']}"
    draw.rounded_rectangle((655, 34, 805, 70), radius=18, fill=(49, 46, 129, 255), outline=(99, 102, 241, 255), width=1)
    draw.text((672, 44), msg_rank_text, fill=(224, 231, 255, 255), font=font_badge)

    # Voice Rank Badge
    voice_rank_text = f"VOICE RANK #{data['voice_rank']}"
    draw.rounded_rectangle((820, 34, 965, 70), radius=18, fill=(6, 78, 59, 255), outline=(16, 185, 129, 255), width=1)
    draw.text((833, 44), voice_rank_text, fill=(167, 243, 208, 255), font=font_badge)

    draw.text((795, 84), f"{data['total_active']} active members", fill=(139, 148, 158, 255), font=font_small)

    # Header Divider
    draw.line((35, 130, 965, 130), fill=(33, 38, 45, 255), width=1)

    # LEFT CARD: MESSAGES
    draw.rounded_rectangle((35, 145, 485, 360), radius=12, fill=(18, 22, 30, 255), outline=(48, 54, 61, 255), width=1)
    draw.text((50, 160), "💬 MESSAGES", fill=(56, 189, 248, 255), font=font_bold)

    draw.text((55, 192), "1d", fill=(139, 148, 158, 255), font=font_small)
    draw.text((55, 210), f"{data['msg_1d']} msgs", fill=(240, 246, 252, 255), font=font_metric)

    draw.text((195, 192), "7d", fill=(139, 148, 158, 255), font=font_small)
    draw.text((195, 210), f"{data['msg_7d']} msgs", fill=(240, 246, 252, 255), font=font_metric)

    draw.text((335, 192), "14d", fill=(139, 148, 158, 255), font=font_small)
    draw.text((335, 210), f"{data['msg_14d']} msgs", fill=(56, 189, 248, 255), font=font_metric)

    draw.line((50, 248, 470, 248), fill=(33, 38, 45, 255), width=1)
    draw.text((50, 258), "TOP CHANNELS (14D)", fill=(139, 148, 158, 255), font=font_small)

    if data['top_channels']:
        y_ch = 278
        for ch_name, cnt in data['top_channels'][:3]:
            ch_clean = ch_name[:24]
            draw.text((50, y_ch), f"• {ch_clean}", fill=(201, 209, 217, 255), font=font_regular)
            draw.text((380, y_ch), f"{cnt} msgs", fill=(139, 148, 158, 255), font=font_regular)
            y_ch += 24
    else:
        draw.text((50, 285), "• Aktif kanal bulunamadı", fill=(110, 118, 129, 255), font=font_regular)

    # RIGHT CARD: VOICE ACTIVITY
    draw.rounded_rectangle((515, 145, 965, 360), radius=12, fill=(18, 22, 30, 255), outline=(48, 54, 61, 255), width=1)
    draw.text((530, 160), "🎙️ VOICE ACTIVITY", fill=(52, 211, 153, 255), font=font_bold)

    draw.text((535, 192), "1d", fill=(139, 148, 158, 255), font=font_small)
    draw.text((535, 210), format_duration(data['voice_1d_sec']), fill=(240, 246, 252, 255), font=font_metric)

    draw.text((675, 192), "7d", fill=(139, 148, 158, 255), font=font_small)
    draw.text((675, 210), format_duration(data['voice_7d_sec']), fill=(240, 246, 252, 255), font=font_metric)

    draw.text((815, 192), "14d", fill=(139, 148, 158, 255), font=font_small)
    draw.text((815, 210), format_duration(data['voice_14d_sec']), fill=(52, 211, 153, 255), font=font_metric)

    draw.line((530, 248, 950, 248), fill=(33, 38, 45, 255), width=1)
    draw.text((530, 258), "TOP VOICE CHANNELS (14D)", fill=(139, 148, 158, 255), font=font_small)

    if data['top_voice_channels']:
        y_vch = 278
        for vch_name, secs in data['top_voice_channels'][:3]:
            vch_clean = vch_name[:24]
            draw.text((530, y_vch), f"• {vch_clean}", fill=(201, 209, 217, 255), font=font_regular)
            draw.text((860, y_vch), format_duration(secs), fill=(139, 148, 158, 255), font=font_regular)
            y_vch += 24
    else:
        draw.text((530, 285), "• Ses aktivitesi bulunamadı", fill=(110, 118, 129, 255), font=font_regular)

    # BOTTOM CARD: 14-DAY ACTIVITY TREND CHART
    draw.rounded_rectangle((35, 375, 965, 525), radius=12, fill=(18, 22, 30, 255), outline=(48, 54, 61, 255), width=1)
    draw.text((50, 386), "📈 14-GÜNLÜK AKTİVLİK TRENDİ (GÜNLÜK MESAJLAR)", fill=(139, 148, 158, 255), font=font_small)
    draw.text((760, 386), "STATBOT PRO • 24/7 TRACKING", fill=(110, 118, 129, 255), font=font_small)

    chart_data = data.get("daily_chart_data", [])
    max_val = max([cnt for _, cnt in chart_data] + [1])
    bar_width = 46
    bar_gap = 17
    start_x = 55
    y_base = 492
    max_bar_h = 58

    for idx, (d_lbl, cnt) in enumerate(chart_data[:14]):
        bx = start_x + idx * (bar_width + bar_gap)
        bar_h = int((cnt / max_val) * max_bar_h) if cnt > 0 else 4
        bar_top = y_base - bar_h

        bar_fill = (88, 101, 242, 255) if cnt > 0 else (33, 38, 45, 255)
        draw.rounded_rectangle((bx, bar_top, bx + bar_width, y_base), radius=4, fill=bar_fill)

        if cnt > 0:
            draw.text((bx + 10, bar_top - 14), str(cnt), fill=(224, 231, 255, 255), font=font_small)

        draw.text((bx + 8, y_base + 8), d_lbl, fill=(139, 148, 158, 255), font=font_small)

    out = io.BytesIO()
    card.save(out, format="PNG")
    out.seek(0)
    return out

def build_statboard_embed(guild: discord.Guild, period_days: int) -> discord.Embed:
    g_id = str(guild.id)
    stats = get_stat_db()
    guild_stats = stats.get(g_id, {})
    users_map = guild_stats.get("users", {})
    keys = get_date_keys(period_days)

    period_title = {1: "Son 1 Günlük (1 Day)", 7: "Son 7 Günlük (7 Days)", 14: "Son 14 Günlük (14 Days)"}.get(period_days, f"Son {period_days} Günlük")

    msg_leaders = []
    voice_leaders = []
    total_messages = 0
    total_voice_sec = 0

    for uid_str, udata in users_map.items():
        try:
            uid = int(uid_str)
        except ValueError:
            continue

        member = guild.get_member(uid)
        if member and member.bot:
            continue

        m_count = sum(udata.get("messages", {}).get(d, 0) for d in keys)
        if m_count > 0:
            total_messages += m_count
            msg_leaders.append((uid, m_count))

        v_sec = sum(udata.get("voice_seconds", {}).get(d, 0) for d in keys)
        active_sec, _ = get_user_current_active_voice_seconds(guild.id, uid)
        v_sec += active_sec
        if v_sec > 0:
            total_voice_sec += v_sec
            voice_leaders.append((uid, v_sec))

    msg_leaders.sort(key=lambda x: x[1], reverse=True)
    voice_leaders.sort(key=lambda x: x[1], reverse=True)

    medals = ["🥇", "🥈", "🥉"]

    msg_lines = []
    for idx, (uid, cnt) in enumerate(msg_leaders[:10]):
        rank_icon = medals[idx] if idx < 3 else f"`{idx + 1}.`"
        m = guild.get_member(uid)
        name = m.mention if m else f"<@{uid}>"
        msg_lines.append(f"{rank_icon} {name} — **{cnt:,}** messages")

    voice_lines = []
    for idx, (uid, secs) in enumerate(voice_leaders[:10]):
        rank_icon = medals[idx] if idx < 3 else f"`{idx + 1}.`"
        m = guild.get_member(uid)
        name = m.mention if m else f"<@{uid}>"
        voice_lines.append(f"{rank_icon} {name} — **{format_duration(secs)}**")

    embed = discord.Embed(
        title=f"🏆 SERVER AKTİVLİK LİDERLİK CƏDVƏLİ",
        description=f"📅 **Müddət:** `{period_title}`\nServerin ən aktiv istifadəçiləri aşağıda göstərilmişdir:",
        color=0x5865F2,
        timestamp=discord.utils.utcnow()
    )
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)

    embed.add_field(
        name="💬 Message Leaderboard",
        value="\n".join(msg_lines) if msg_lines else "*Bu müddət ərzində heç bir mesaj yazılmayıb.*",
        inline=False
    )

    embed.add_field(
        name="🎙️ Voice Leaderboard",
        value="\n".join(voice_lines) if voice_lines else "*Bu müddət ərzində voice-da heç kim olmayıb.*",
        inline=False
    )

    embed.add_field(
        name="📊 Ümumi Statistika",
        value=(
            f"• Cəmi Mesaj: **{total_messages:,}** messages\n"
            f"• Cəmi Səs Aktivliyi: **{format_duration(total_voice_sec)}**\n"
            f"• İzlənən Aktiv Üzv: **{len(set([x[0] for x in msg_leaders] + [x[0] for x in voice_leaders]))}** nəfər"
        ),
        inline=False
    )

    embed.set_footer(text="Aşağıdakı düymələrlə müddəti dəyişə bilərsiniz • Statbot Pro")
    return embed

class StatboardView(ui.View):
    def __init__(self, period_days: int = 14):
        super().__init__(timeout=300)
        self.period_days = period_days
        self.update_buttons()

    def update_buttons(self):
        self.clear_items()

        btn_1d = ui.Button(
            label="1 Day",
            style=discord.ButtonStyle.primary if self.period_days == 1 else discord.ButtonStyle.secondary,
            emoji="📅",
            custom_id="sb_1d"
        )
        btn_7d = ui.Button(
            label="7 Days",
            style=discord.ButtonStyle.primary if self.period_days == 7 else discord.ButtonStyle.secondary,
            emoji="📅",
            custom_id="sb_7d"
        )
        btn_14d = ui.Button(
            label="14 Days",
            style=discord.ButtonStyle.success if self.period_days == 14 else discord.ButtonStyle.secondary,
            emoji="📅",
            custom_id="sb_14d"
        )
        btn_refresh = ui.Button(
            label="Yenile",
            style=discord.ButtonStyle.secondary,
            emoji="🔄",
            custom_id="sb_refresh"
        )

        async def cb_1d(interaction: discord.Interaction):
            self.period_days = 1
            self.update_buttons()
            embed = build_statboard_embed(interaction.guild, 1)
            await interaction.response.edit_message(embed=embed, view=self)

        async def cb_7d(interaction: discord.Interaction):
            self.period_days = 7
            self.update_buttons()
            embed = build_statboard_embed(interaction.guild, 7)
            await interaction.response.edit_message(embed=embed, view=self)

        async def cb_14d(interaction: discord.Interaction):
            self.period_days = 14
            self.update_buttons()
            embed = build_statboard_embed(interaction.guild, 14)
            await interaction.response.edit_message(embed=embed, view=self)

        async def cb_refresh(interaction: discord.Interaction):
            embed = build_statboard_embed(interaction.guild, self.period_days)
            await interaction.response.edit_message(embed=embed, view=self)

        btn_1d.callback = cb_1d
        btn_7d.callback = cb_7d
        btn_14d.callback = cb_14d
        btn_refresh.callback = cb_refresh

        self.add_item(btn_1d)
        self.add_item(btn_7d)
        self.add_item(btn_14d)
        self.add_item(btn_refresh)

# =============================================================================
# YETKİ YOXLANIŞI (FOUNDER, ADMIN VƏ YA XÜSUSİ TƏYİN EDİLMİŞ ROLLAR)
# =============================================================================
def is_founder(user_id: int) -> bool:
    return user_id == FOUNDER_ID

def check_permission(ctx: commands.Context, perm_key: str, default_role_id: Optional[int] = None) -> bool:
    if ctx.author.id == FOUNDER_ID or ctx.author.id == ctx.guild.owner_id or ctx.author.guild_permissions.administrator:
        return True
    conf = get_config()
    allowed_role_ids = conf.get(f"{perm_key}_roles", [])
    if default_role_id and default_role_id not in allowed_role_ids:
        allowed_role_ids.append(default_role_id)
    user_roles = [r.id for r in ctx.author.roles]
    return any(r_id in user_roles for r_id in allowed_role_ids)

def can_manage_channels(member: discord.Member) -> bool:
    if not member or not hasattr(member, "guild") or not member.guild:
        return False
    if member.id == FOUNDER_ID or member.id == member.guild.owner_id:
        return True
    if member.guild_permissions.administrator or member.guild_permissions.manage_channels:
        return True
    return False

# =============================================================================
# DISCORD BOT INITIALIZATION
# =============================================================================
intents = discord.Intents.all()
bot = commands.Bot(command_prefix=["a!", "!"], intents=intents, help_command=None, case_insensitive=True)

invite_cache = {}

async def send_log(guild: discord.Guild, channel_key: str, embed: discord.Embed):
    channel_id = LOG_CHANNELS.get(channel_key)
    if not channel_id:
        return
    channel = guild.get_channel(channel_id)
    if channel:
        try:
            await channel.send(embed=embed)
        except Exception as e:
            print(f"Log gönderilirken hata ({channel_key}): {e}")

# =============================================================================
# AĞILLI SƏHV VƏ KOMANDA TƏKLİF SİSTEMİ (DID YOU MEAN?)
# =============================================================================
@bot.event
async def on_command_error(ctx: commands.Context, error: commands.CommandError):
    if isinstance(error, commands.CommandNotFound):
        invoked = ctx.invoked_with
        if not invoked:
            return

        all_commands = []
        for cmd in bot.commands:
            if not cmd.hidden:
                all_commands.append(cmd.name)
                all_commands.extend(cmd.aliases)

        matches = difflib.get_close_matches(invoked.lower(), all_commands, n=3, cutoff=0.4)

        embed = discord.Embed(
            title="❌ Hatalı Komut!",
            color=0xef4444,
            timestamp=discord.utils.utcnow()
        )
        embed.description = f"**`{ctx.prefix}{invoked}`** adlı komut bulunamadı."

        if matches:
            suggestions = " və ya ".join([f"`{ctx.prefix}{m}`" for m in matches])
            embed.add_field(
                name="💡 Bunu mu demek istediniz?",
                value=suggestions,
                inline=False
            )
        else:
            embed.add_field(
                name="ℹ️ Yardıma mı İhtiyacınız Var?",
                value=f"Tüm komutların listesini görmek için **`{ctx.prefix}help`** yazın.",
                inline=False
            )
        await ctx.send(embed=embed)

    elif isinstance(error, commands.MissingPermissions):
        perms = ", ".join(error.missing_permissions)
        await ctx.send(f"❌ Bu komutu kullanmak için yetkiniz yetersiz! (Gereken: `{perms}`)")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"❌ Eksik parametre! Doğru kullanım: `{ctx.prefix}{ctx.command.name} {ctx.command.signature}`")
    elif isinstance(error, commands.BadArgument):
        await ctx.send(f"❌ Hatalı parametre girildi! Lütfen istenen değeri doğru yazın.")
    elif isinstance(error, commands.CommandOnCooldown):
        await ctx.send(f"⏳ Bu komut için beklemeniz gerekiyor: `{error.retry_after:.1f}` saniyə.")
    else:
        print(f"Hata ({ctx.command}): {error}")

# =============================================================================
# BOT HAZIR OLDUQDA
# =============================================================================
@bot.event
async def on_ready():
    print("=" * 65)
    print(f"🚀 Bot aktivdir: {bot.user} (ID: {bot.user.id})")
    print(f"👑 Kurucu ID: {FOUNDER_ID}")
    print(f"🚪 Karşılama Kanalı: {get_config().get('welcome_channel_id', DEFAULT_WELCOME_CHANNEL_ID)}")
    print(f"⚙️ a!config paneli yalnızca Kurucuya açıktır!")
    print("=" * 65)

    bot.add_view(TicketLauncherView())
    bot.add_view(TicketCloseView())

    for guild in bot.guilds:
        try:
            invites = await guild.invites()
            invite_cache[guild.id] = {inv.code: inv.uses for inv in invites}
        except Exception:
            pass

        # Statbot: Initialize active voice sessions for users currently in voice channels
        try:
            g_id = str(guild.id)
            stats = get_stat_db()
            guild_stats = stats.setdefault(g_id, {"users": {}, "active_voice": {}})
            active_map = guild_stats.setdefault("active_voice", {})
            now_ts = datetime.datetime.now().timestamp()
            for vc in guild.voice_channels:
                for member in vc.members:
                    if not member.bot and str(member.id) not in active_map:
                        active_map[str(member.id)] = {
                            "channel_id": vc.id,
                            "joined_at": now_ts
                        }
            save_data(db)
        except Exception as e:
            print(f"Error initializing voice tracking on ready: {e}")

        # Moderasiya Sübut Kanalı icazələrinin avtomatik sinxronlaşdırılması (1541541519578628117)
        try:
            allowed_r = await sync_proof_channel_permissions(guild)
            if allowed_r:
                print(f"🔒 Kanıt kanalı ({PROOF_LOG_CHANNEL_ID}) {len(allowed_r)} yetkili role açıldı.")
        except Exception as e:
            print(f"Kanıt kanalı izin hatası ({guild.name}): {e}")

    await bot.change_presence(activity=discord.Game(name="a!stat | a!statboard | a!config | a!help"))

@bot.event
async def on_interaction(interaction: discord.Interaction):
    # Persistent Proof button handler across reboots
    custom_id = interaction.data.get("custom_id", "") if interaction.data else ""
    if custom_id and (custom_id.startswith("proof_app_") or custom_id.startswith("proof_rej_")):
        case_id = custom_id.replace("proof_app_", "").replace("proof_rej_", "")
        is_approve = custom_id.startswith("proof_app_")

        if not can_review_proofs(interaction.user):
            roles_txt = " • ".join([f"<@&{r}>" for r in PROOF_REVIEWER_ROLES])
            return await interaction.response.send_message(
                f"❌ Bu kanıtı yalnızca belirlenen 3 denetleyici rolüne ({roles_txt}) sahip olanlar veya Kurucu (<@{FOUNDER_ID}>) inceleyebilir!",
                ephemeral=True
            )

        cases = db.setdefault("proof_cases", {})
        case_data = cases.get(case_id)
        if not case_data:
            return await interaction.response.send_message("❌ Dosya bilgisi veritabanında bulunamadı!", ephemeral=True)

        if case_data.get("status") in ["approved", "rejected"]:
            return await interaction.response.send_message(f"⚠️ Bu dosya zaten incelendi! Mevcut durum: `{case_data.get('status')}`", ephemeral=True)

        now_str = datetime.datetime.now().strftime("%d.%m.%Y %H:%M:%S")
        case_data["reviewer_id"] = interaction.user.id
        case_data["reviewed_at"] = now_str

        orig_embed = interaction.message.embeds[0] if interaction.message.embeds else None
        new_embed = orig_embed.copy() if orig_embed else discord.Embed(title=f"Dosye {case_id}")

        if is_approve:
            case_data["status"] = "approved"
            save_data(db)
            new_embed.color = 0x10b981
            new_embed.title = f"🛡️ MODERASYON KANIT DOSYASI • {case_id} [ONAYLANDI]"
            for idx, f in enumerate(new_embed.fields):
                if "Status" in f.name:
                    new_embed.set_field_at(
                        idx,
                        name="🚦 Status",
                        value=f"✅ **Onaylandı**\n👑 **Onaylayan:** {interaction.user.mention} (`{now_str}`)",
                        inline=False
                    )
                    break

            view = ui.View.from_message(interaction.message) if interaction.message else None
            if view:
                for item in view.children:
                    item.disabled = True
            await interaction.response.edit_message(embed=new_embed, view=view)
            return await interaction.followup.send(f"✅ **{case_id}** numaralı kanıt dosyası onaylandı.", ephemeral=True)
        else:
            case_data["status"] = "rejected"
            save_data(db)
            guild = interaction.guild
            target_id = case_data.get("target_id")
            action = str(case_data.get("action", "")).upper()
            revert_note = ""

            if "BAN" in action:
                try:
                    await guild.unban(discord.Object(id=target_id), reason=f"Kanıt {interaction.user} tarafından reddedildi")
                    revert_note = "\n🔓 **Kullanıcının banı otomatik olarak kaldırıldı!**"
                except Exception as e:
                    revert_note = f"\n⚠️ Ban kaldırılırken hata: {e}"
            elif "TIMEOUT" in action or "MUTE" in action:
                try:
                    target_member = guild.get_member(target_id)
                    if target_member:
                        await target_member.timeout(None, reason=f"Kanıt {interaction.user} tarafından reddedildi")
                        revert_note = "\n🔓 **Kullanıcının susturma (timeout) cezası kaldırıldı!**"
                except Exception as e:
                    revert_note = f"\n⚠️ Timeout kaldırılırken hata: {e}"
            elif "WARN" in action:
                try:
                    u_warns = db.get("warns", {}).get(str(target_id), [])
                    if u_warns:
                        u_warns.pop()
                        save_data(db)
                        revert_note = f"\n🟢 **1 uyarı otomatik silindi! (Kalan uyarı: {len(u_warns)})**"
                except Exception as e:
                    revert_note = f"\n⚠️ Uyarı silinirken hata: {e}"
            elif "KICK" in action:
                revert_note = "\nℹ️ *Kullanıcı sunucudan atılmıştı (kick), cezanın haksız olduğu tespit edildi.*"

            new_embed.color = 0xef4444
            new_embed.title = f"🛡️ MODERASYON KANIT DOSYASI • {case_id} [REDDEDİLDİ]"
            for idx, f in enumerate(new_embed.fields):
                if "Status" in f.name:
                    new_embed.set_field_at(
                        idx,
                        name="🚦 Status",
                        value=f"❌ **Reddedildi (Yetersiz Kanıt)**\n👑 **Reddeden:** {interaction.user.mention} (`{now_str}`){revert_note}",
                        inline=False
                    )
                    break

            view = ui.View.from_message(interaction.message) if interaction.message else None
            if view:
                for item in view.children:
                    item.disabled = True
            await interaction.response.edit_message(embed=new_embed, view=view)
            return await interaction.followup.send(f"❌ **{case_id}** numaralı kanıt reddedildi ve uygulanan ceza geri alındı.{revert_note}", ephemeral=True)

# =============================================================================
# ON MEMBER JOIN (15 Saniyelik Xoşgəldin Mesajı + Auto-Role + Audit)
# =============================================================================
@bot.event
async def on_member_join(member: discord.Member):
    guild = member.guild
    conf = get_config()

    # 1. 15 saniyə sonra silinən xoşgəldin mesajı
    if conf.get("welcome_enabled", True):
        welcome_channel_id = conf.get("welcome_channel_id", DEFAULT_WELCOME_CHANNEL_ID)
        welcome_channel = guild.get_channel(welcome_channel_id)
        if welcome_channel:
            delete_seconds = conf.get("welcome_delete_seconds", 15)
            # Tələb: "user sunucuya geldi ."
            msg_text = f"👋 {member.mention} sunucuya geldi ."
            try:
                await welcome_channel.send(msg_text, delete_after=delete_seconds)
            except Exception as e:
                print(f"Karşılama mesajı hatası: {e}")

    # 2. Gələnə Avtomatik Rol (Auto-Role)
    autorole_ids = conf.get("autorole_ids", [])
    for r_id in autorole_ids:
        role = guild.get_role(r_id)
        if role:
            try:
                await member.add_roles(role, reason="Auto-role on join")
            except Exception as e:
                print(f"Auto-role verilmədi: {e}")

    # 3. Server Logları
    log_id = get_next_log_id("MEM")
    embed = discord.Embed(title="📥 MEMBER JOINED", color=0x10b981, timestamp=discord.utils.utcnow())
    embed.add_field(name="User", value=f"{member.mention} (`{member.id}`)", inline=True)
    embed.add_field(name="Account Created", value=discord.utils.format_dt(member.created_at, 'R'), inline=True)
    embed.add_field(name="Is Bot?", value="Bəli 🤖" if member.bot else "Xeyr 👤", inline=True)
    embed.set_footer(text=f"Log ID: {log_id}")
    await send_log(guild, "member", embed)

    if member.bot:
        sec_log_id = get_next_log_id("SEC")
        sec_embed = discord.Embed(title="🚨 BOT ADDED TO SERVER", color=0xef4444, timestamp=discord.utils.utcnow())
        sec_embed.add_field(name="Bot", value=f"{member.mention} (`{member.id}`)", inline=True)
        sec_embed.set_footer(text=f"Log ID: {sec_log_id}")
        await send_log(guild, "security", sec_embed)

# =============================================================================
# INTERAKTİV QURU İDARƏETMƏ PANELİ (a!config) - YALNIZ 349152405927231488 İÇİN
# =============================================================================
def build_config_embed(guild: discord.Guild) -> discord.Embed:
    conf = get_config()
    wel_ch_id = conf.get("welcome_channel_id", DEFAULT_WELCOME_CHANNEL_ID)
    wel_del = conf.get("welcome_delete_seconds", 15)
    wel_enabled = "Aktif ✅" if conf.get("welcome_enabled", True) else "Devre Dışı ❌"

    def format_roles(role_ids: List[int]) -> str:
        if not role_ids:
            return "*Belirlenmedi (Yalnızca Yönetici)*"
        valid = [f"<@&{rid}>" for rid in role_ids]
        return ", ".join(valid) if valid else "*Belirlenmedi*"

    embed = discord.Embed(
        title="⚙️ SUNUCU KURUCUSU YÖNETİM PANELİ",
        description=(
            f"👑 **Kurucu:** <@{FOUNDER_ID}>\n"
            f"Bu panel üzerinden botun tüm izinlerini, karşılama mesajını ve yetki rollerini doğrudan yapılandırabilirsiniz.\n"
            f"Aşağıdakı menyudan dəyişmək istədiyiniz parametri seçin."
        ),
        color=0x5865F2,
        timestamp=discord.utils.utcnow()
    )

    embed.add_field(
        name="🚪 Karşılama Mesajı Ayarları",
        value=(
            f"• **Status:** {wel_enabled}\n"
            f"• **Kanal:** <#{wel_ch_id}> (`{wel_ch_id}`)\n"
            f"• **Silinme Süresi:** `{wel_del}` saniye\n"
            f"• **Format:** `[User] sunucuya geldi .`"
        ),
        inline=False
    )

    embed.add_field(name="🔨 Ban Yetkisi Rolleri", value=format_roles(conf.get("ban_roles", [])), inline=True)
    embed.add_field(name="👢 Kick Yetkisi Rolleri", value=format_roles(conf.get("kick_roles", [])), inline=True)
    embed.add_field(name="⏱️ Timeout / Mute Yetkisi Rolleri", value=format_roles(conf.get("timeout_roles", [])), inline=True)
    embed.add_field(name="⚠️ Uyarı (Warn) Yetkisi Rolleri", value=format_roles(conf.get("warn_roles", [WARN_ROLE_ID])), inline=True)
    embed.add_field(name="📜 Log Yönetim Rolleri", value=format_roles(conf.get("log_roles", [])), inline=True)
    embed.add_field(name="🎭 Otomatik Rol (Yeni Üyelere Verilen)", value=format_roles(conf.get("autorole_ids", [])), inline=True)

    ticket_cat = conf.get("ticket_category_id", LOGS_CATEGORY_ID)
    embed.add_field(name="🎫 Destek (Ticket) Kategorisi", value=f"<#{ticket_cat}> (`{ticket_cat}`)", inline=False)
    embed.set_footer(text="Yalnızca Kurucu (ID: 349152405927231488) değişiklik yapabilir")
    return embed

class ConfigRoleSelect(ui.RoleSelect):
    def __init__(self, perm_key: str, placeholder: str):
        super().__init__(placeholder=placeholder, min_values=0, max_values=10)
        self.perm_key = perm_key

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != FOUNDER_ID:
            return await interaction.response.send_message("❌ Bu paneli yalnızca sunucu kurucusu (<@349152405927231488>) yönetebilir!", ephemeral=True)

        conf = get_config()
        selected_ids = [r.id for r in self.values]
        conf[f"{self.perm_key}_roles"] = selected_ids
        save_data(db)

        role_mentions = ", ".join([r.mention for r in self.values]) if self.values else "Temizlendi (Yalnızca Yönetici)"
        await interaction.response.send_message(f"✅ **{self.perm_key.upper()}** yetkisi rolleri başarıyla güncellendi: {role_mentions}", ephemeral=True)
        # Əsas paneli yeniləyirik
        await self.view.refresh_main(interaction)

class ConfigChannelSelect(ui.ChannelSelect):
    def __init__(self, channel_type: discord.ChannelType, target_key: str, placeholder: str):
        super().__init__(placeholder=placeholder, channel_types=[channel_type], min_values=1, max_values=1)
        self.target_key = target_key

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != FOUNDER_ID:
            return await interaction.response.send_message("❌ Bu paneli yalnızca sunucu kurucusu (<@349152405927231488>) yönetebilir!", ephemeral=True)

        conf = get_config()
        channel = self.values[0]
        conf[self.target_key] = channel.id
        save_data(db)

        await interaction.response.send_message(f"✅ Kanal başarıyla seçildi: {channel.mention}", ephemeral=True)
        await self.view.refresh_main(interaction)

class ConfigMainSelect(ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Karşılama Kanalı Seçimi", value="opt_welcome_ch", emoji="🚪", description="Yeni gelen üyelerin mesajının gönderileceği kanal"),
            discord.SelectOption(label="Karşılama Mesajını Aç / Kapat", value="opt_welcome_toggle", emoji="🔄", description="Karşılama mesajını aktif veya devre dışı bırak"),
            discord.SelectOption(label="Silinme Süresini Değiştir", value="opt_welcome_time", emoji="⏱️", description="10sn, 15sn, 30sn veya 60sn seç"),
            discord.SelectOption(label="Ban Yetkisi Rolleri", value="opt_ban_roles", emoji="🔨", description="Ban komutunu kullanabilen roller"),
            discord.SelectOption(label="Kick Yetkisi Rolleri", value="opt_kick_roles", emoji="👢", description="Kick komutunu kullanabilen roller"),
            discord.SelectOption(label="Timeout Yetkisi Rolleri", value="opt_timeout_roles", emoji="⏱️", description="Timeout / susturma uygulayabilen roller"),
            discord.SelectOption(label="Uyarı (Warn) Yetkisi Rolleri", value="opt_warn_roles", emoji="⚠️", description="Uyarı verebilen ve silebilen roller"),
            discord.SelectOption(label="Log Görüntüleme Rolleri", value="opt_log_roles", emoji="📜", description="Logları inceleyebilen yetkili roller"),
            discord.SelectOption(label="Otomatik Rol (Girişte Verilen)", value="opt_autorole", emoji="🎭", description="Yeni katılan üyelere otomatik verilecek roller"),
            discord.SelectOption(label="Destek Talebi Kategorisi", value="opt_ticket_cat", emoji="🎫", description="Taleplerin açılacağı kategori"),
        ]
        super().__init__(placeholder="Hangi ayarı düzenlemek istiyorsunuz? (Seçin)", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != FOUNDER_ID:
            return await interaction.response.send_message("❌ Bu paneli yalnızca sunucu kurucusu (<@349152405927231488>) yönetebilir!", ephemeral=True)

        val = self.values[0]
        v = self.view

        if val == "opt_welcome_ch":
            sub_view = ui.View(timeout=120)
            sub_view.add_item(ConfigChannelSelect(discord.ChannelType.text, "welcome_channel_id", "🚪 Yeni Karşılama Kanalını Seçin"))
            await interaction.response.send_message("Aşağıdaki menüden yeni karşılama kanalını seçin:", view=sub_view, ephemeral=True)

        elif val == "opt_welcome_toggle":
            conf = get_config()
            conf["welcome_enabled"] = not conf.get("welcome_enabled", True)
            save_data(db)
            state = "Aktif edildi ✅" if conf["welcome_enabled"] else "Devre dışı bırakıldı ❌"
            await interaction.response.send_message(f"🚪 Karşılama mesajı durumu: **{state}**", ephemeral=True)
            await v.refresh_main(interaction)

        elif val == "opt_welcome_time":
            time_view = ui.View(timeout=120)
            for secs in [5, 10, 15, 30, 60]:
                btn = ui.Button(label=f"{secs} Saniye", style=discord.ButtonStyle.secondary, custom_id=f"weltime_{secs}")
                async def btn_callback(btn_int: discord.Interaction, s=secs):
                    if btn_int.user.id != FOUNDER_ID:
                        return await btn_int.response.send_message("❌ İzniniz yok!", ephemeral=True)
                    conf = get_config()
                    conf["welcome_delete_seconds"] = s
                    save_data(db)
                    await btn_int.response.send_message(f"⏱️ Karşılama mesajının silinme süresi **{s} saniyə** olarak ayarlandı.", ephemeral=True)
                    await v.refresh_main(btn_int)
                btn.callback = btn_callback
                time_view.add_item(btn)
            await interaction.response.send_message("Mesajın kaç saniye sonra silinmesini istersiniz?", view=time_view, ephemeral=True)

        elif val == "opt_ban_roles":
            sub_view = ui.View(timeout=120)
            sub_view.add_item(ConfigRoleSelect("ban", "🔨 Ban Yetkisi için rolleri seçin (1 veya birden fazla)"))
            await interaction.response.send_message("Ban yetkisine sahip rolleri seçin:", view=sub_view, ephemeral=True)

        elif val == "opt_kick_roles":
            sub_view = ui.View(timeout=120)
            sub_view.add_item(ConfigRoleSelect("kick", "👢 Kick Yetkisi için rolleri seçin"))
            await interaction.response.send_message("Kick yetkisine sahip rolleri seçin:", view=sub_view, ephemeral=True)

        elif val == "opt_timeout_roles":
            sub_view = ui.View(timeout=120)
            sub_view.add_item(ConfigRoleSelect("timeout", "⏱️ Timeout Yetkisi için rolleri seçin"))
            await interaction.response.send_message("Timeout yetkisine sahip rolleri seçin:", view=sub_view, ephemeral=True)

        elif val == "opt_warn_roles":
            sub_view = ui.View(timeout=120)
            sub_view.add_item(ConfigRoleSelect("warn", "⚠️ Uyarı Yetkisi için rolleri seçin"))
            await interaction.response.send_message("Uyarı yetkisine sahip rolleri seçin:", view=sub_view, ephemeral=True)

        elif val == "opt_log_roles":
            sub_view = ui.View(timeout=120)
            sub_view.add_item(ConfigRoleSelect("log", "📜 Log İnceleme rollerini seçin"))
            await interaction.response.send_message("Logları görüntüleyebilecek yetkili rolleri seçin:", view=sub_view, ephemeral=True)

        elif val == "opt_autorole":
            sub_view = ui.View(timeout=120)
            sub_view.add_item(ConfigRoleSelect("autorole", "🎭 Yeni gelenlere verilecek rolleri seçin"))
            await interaction.response.send_message("Sunucuya katılanlara otomatik verilecek rolleri seçin:", view=sub_view, ephemeral=True)

        elif val == "opt_ticket_cat":
            sub_view = ui.View(timeout=120)
            sub_view.add_item(ConfigChannelSelect(discord.ChannelType.category, "ticket_category_id", "🎫 Destek Talebi Kategorisinı Seçin"))
            await interaction.response.send_message("Taleplerin açılacağı kategorinı seçin:", view=sub_view, ephemeral=True)

class ConfigDashboardView(ui.View):
    def __init__(self, original_message=None):
        super().__init__(timeout=300)
        self.original_message = original_message
        self.add_item(ConfigMainSelect())

    async def refresh_main(self, interaction: discord.Interaction):
        embed = build_config_embed(interaction.guild)
        if self.original_message:
            try:
                await self.original_message.edit(embed=embed, view=self)
            except Exception:
                pass

    @ui.button(label="Yenile", style=discord.ButtonStyle.success, emoji="🔄", row=1)
    async def btn_refresh(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user.id != FOUNDER_ID:
            return await interaction.response.send_message("❌ Bu paneli yalnızca sunucu kurucusu (<@349152405927231488>) yönetebilir!", ephemeral=True)
        embed = build_config_embed(interaction.guild)
        await interaction.response.edit_message(embed=embed, view=self)

    @ui.button(label="Paneli Kapat", style=discord.ButtonStyle.danger, emoji="✖️", row=1)
    async def btn_close(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user.id != FOUNDER_ID:
            return await interaction.response.send_message("❌ İzniniz yok!", ephemeral=True)
        await interaction.message.delete()

@bot.command(name="config", aliases=["panel", "ayar", "ayarlar"])
async def cmd_config(ctx):
    """a!config - Yalnızca sunucu kurucusu (349152405927231488) için interaktif yönetim paneli"""
    if ctx.author.id != FOUNDER_ID:
        return await ctx.send(f"❌ Bu yönetim panelini yalnızca sunucu kurucusu (<@{FOUNDER_ID}>) açabilir!")

    embed = build_config_embed(ctx.guild)
    view = ConfigDashboardView()
    msg = await ctx.send(embed=embed, view=view)
    view.original_message = msg

# =============================================================================
# 1. a!gay (GAY / PRIDE ŞƏFFAF BAYRAQ AVATAR EFFEKTİ)
# =============================================================================
@bot.command(name="gay", aliases=["pride"])
async def cmd_gay(ctx, member: Optional[discord.Member] = None):
    """a!gay @user - İstifadəçinin profilinin üstünə şəffaf rəngbərəng bayraq effekti qoyur"""
    target = member or ctx.author

    async with ctx.typing():
        try:
            avatar_url = target.display_avatar.with_format("png").with_size(512).url
            async with aiohttp.ClientSession() as session:
                async with session.get(avatar_url) as resp:
                    if resp.status != 200:
                        return await ctx.send("❌ İstifadəçinin avatarı yüklənə bilmədi.")
                    avatar_bytes = await resp.read()

            avatar_img = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA")
            width, height = avatar_img.size

            rainbow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
            draw = ImageDraw.Draw(rainbow)

            # Rənglər: Qırmızı, Narıncı, Sarı, Yaşıl, Mavi, Bənövşəyi (Şəffaflıq: 115 / 255)
            colors = [
                (255, 0, 24, 115),
                (255, 165, 44, 115),
                (255, 255, 65, 115),
                (0, 128, 24, 115),
                (0, 0, 249, 115),
                (134, 0, 125, 115)
            ]
            stripe_height = height / len(colors)
            for i, color in enumerate(colors):
                top = int(i * stripe_height)
                bottom = int((i + 1) * stripe_height) if i < len(colors) - 1 else height
                draw.rectangle([0, top, width, bottom], fill=color)

            result = Image.alpha_composite(avatar_img, rainbow)

            output_buffer = io.BytesIO()
            result.save(output_buffer, format="PNG")
            output_buffer.seek(0)

            file = discord.File(fp=output_buffer, filename=f"gay_{target.id}.png")
            embed = discord.Embed(
                title=f"🏳️‍🌈 {target.display_name} Gay / Pride Avatarı",
                color=0xe81416,
                timestamp=discord.utils.utcnow()
            )
            embed.set_image(url=f"attachment://gay_{target.id}.png")
            embed.set_footer(text=f"Tələb edən: {ctx.author.display_name}")
            await ctx.send(file=file, embed=embed)
        except Exception as e:
            await ctx.send(f"❌ Resim oluşturulurken hata meydana geldi: {e}")

# =============================================================================
# MODERASİYA SÜBUT VƏ ONAY SİSTEMİ (KANAL: 1541541519578628117)
# =============================================================================
def get_next_proof_id() -> str:
    counter = db.setdefault("log_counter", {})
    current = counter.get("PROOF", 0) + 1
    counter["PROOF"] = current
    save_data(db)
    return f"PROOF-{current:05d}"

async def sync_proof_channel_permissions(guild: discord.Guild) -> List[discord.Role]:
    """Sübut kanalını (1541541519578628117) ban/kick/mute yetkisi olan rollara açır və @everyone-ı bağlayır"""
    channel = guild.get_channel(PROOF_LOG_CHANNEL_ID)
    if not channel:
        return []

    conf = get_config()
    target_role_ids = set(PROOF_REVIEWER_ROLES + INITIAL_MOD_ROLES + [WARN_ROLE_ID])

    for key in ["ban_roles", "kick_roles", "timeout_roles", "warn_roles", "log_roles"]:
        for rid in conf.get(key, []):
            target_role_ids.add(rid)

    for role in guild.roles:
        if (role.permissions.administrator or
            role.permissions.ban_members or
            role.permissions.kick_members or
            role.permissions.moderate_members or
            role.permissions.manage_guild):
            target_role_ids.add(role.id)

    # 1. Adi istifadəçilərə (@everyone) kanalı bağlayırıq
    try:
        current_def = channel.overwrites_for(guild.default_role)
        current_def.view_channel = False
        await channel.set_permissions(guild.default_role, overwrite=current_def, reason="Kanıt kanalı @everyone için kapatıldı")
    except Exception as e:
        print(f"Kanıt kanalı @everyone hatası: {e}")

    # 2. Bütün yetkili rollara baxış və oxuma icazəsi veririk
    allowed_roles = []
    for r_id in target_role_ids:
        r = guild.get_role(r_id)
        if r:
            try:
                ov = channel.overwrites_for(r)
                ov.view_channel = True
                ov.read_message_history = True
                ov.send_messages = True
                ov.attach_files = True
                await channel.set_permissions(r, overwrite=ov, reason="Moderasyon kanıt inceleme izni")
                allowed_roles.append(r)
            except Exception as e:
                print(f"Rol {r.name} izin hatası: {e}")

    return allowed_roles

class ProofReviewView(ui.View):
    def __init__(self, case_id: str):
        super().__init__(timeout=None)
        self.case_id = case_id

        btn_approve = ui.Button(label="Onayla ✅", style=discord.ButtonStyle.success, custom_id=f"proof_app_{case_id}")
        btn_reject = ui.Button(label="Reddet & Cezayı Kaldır ❌", style=discord.ButtonStyle.danger, custom_id=f"proof_rej_{case_id}")

        async def cb_approve(interaction: discord.Interaction):
            if not can_review_proofs(interaction.user):
                roles_txt = " • ".join([f"<@&{r}>" for r in PROOF_REVIEWER_ROLES])
                return await interaction.response.send_message(
                    f"❌ Bu kanıtı yalnızca belirlenen 3 denetleyici rolüne ({roles_txt}) sahip olanlar veya Kurucu (<@{FOUNDER_ID}>) onaylayabilir!",
                    ephemeral=True
                )

            cases = db.setdefault("proof_cases", {})
            case_data = cases.get(self.case_id)
            if not case_data:
                return await interaction.response.send_message("❌ Dosya bilgisi veritabanında bulunamadı!", ephemeral=True)

            if case_data.get("status") in ["approved", "rejected"]:
                return await interaction.response.send_message(f"⚠️ Bu dosya zaten incelendi! Mevcut durum: `{case_data.get('status')}`", ephemeral=True)

            now_str = datetime.datetime.now().strftime("%d.%m.%Y %H:%M:%S")
            case_data["status"] = "approved"
            case_data["reviewer_id"] = interaction.user.id
            case_data["reviewed_at"] = now_str
            save_data(db)

            if interaction.message.embeds:
                orig_embed = interaction.message.embeds[0]
                new_embed = orig_embed.copy()
                new_embed.color = 0x10b981
                new_embed.title = f"🛡️ MODERASYON KANIT DOSYASI • {self.case_id} [ONAYLANDI]"

                for idx, f in enumerate(new_embed.fields):
                    if "Status" in f.name:
                        new_embed.set_field_at(
                            idx,
                            name="🚦 Status",
                            value=f"✅ **Onaylandı**\n👑 **Onaylayan Denetleyici:** {interaction.user.mention} (`{now_str}`)",
                            inline=False
                        )
                        break

                btn_approve.disabled = True
                btn_reject.disabled = True
                await interaction.response.edit_message(embed=new_embed, view=self)
                await interaction.followup.send(f"✅ **{self.case_id}** numaralı kanıt dosyası başarıyla onaylandı.", ephemeral=True)

        async def cb_reject(interaction: discord.Interaction):
            if not can_review_proofs(interaction.user):
                roles_txt = " • ".join([f"<@&{r}>" for r in PROOF_REVIEWER_ROLES])
                return await interaction.response.send_message(
                    f"❌ Bu kanıtı yalnızca belirlenen 3 denetleyici rolüne ({roles_txt}) sahip olanlar veya Kurucu (<@{FOUNDER_ID}>) reddedebilir!",
                    ephemeral=True
                )

            cases = db.setdefault("proof_cases", {})
            case_data = cases.get(self.case_id)
            if not case_data:
                return await interaction.response.send_message("❌ Dosya bilgisi veritabanında bulunamadı!", ephemeral=True)

            if case_data.get("status") in ["approved", "rejected"]:
                return await interaction.response.send_message(f"⚠️ Bu dosya zaten incelendi! Mevcut durum: `{case_data.get('status')}`", ephemeral=True)

            now_str = datetime.datetime.now().strftime("%d.%m.%Y %H:%M:%S")
            case_data["status"] = "rejected"
            case_data["reviewer_id"] = interaction.user.id
            case_data["reviewed_at"] = now_str
            save_data(db)

            guild = interaction.guild
            target_id = case_data.get("target_id")
            action = str(case_data.get("action", "")).upper()
            revert_note = ""

            if "BAN" in action:
                try:
                    await guild.unban(discord.Object(id=target_id), reason=f"Kanıt {interaction.user} tarafından reddedildi")
                    revert_note = "\n🔓 **Kullanıcının banı otomatik olarak kaldırıldı!**"
                except Exception as e:
                    revert_note = f"\n⚠️ Ban kaldırılırken hata: {e}"
            elif "TIMEOUT" in action or "MUTE" in action:
                try:
                    target_member = guild.get_member(target_id)
                    if target_member:
                        await target_member.timeout(None, reason=f"Kanıt {interaction.user} tarafından reddedildi")
                        revert_note = "\n🔓 **Kullanıcının susturma (timeout) cezası kaldırıldı!**"
                except Exception as e:
                    revert_note = f"\n⚠️ Timeout kaldırılırken hata: {e}"
            elif "WARN" in action:
                try:
                    u_warns = db.get("warns", {}).get(str(target_id), [])
                    if u_warns:
                        u_warns.pop()
                        save_data(db)
                        revert_note = f"\n🟢 **1 uyarı otomatik silindi! (Kalan uyarı: {len(u_warns)})**"
                except Exception as e:
                    revert_note = f"\n⚠️ Uyarı silinirken hata: {e}"
            elif "KICK" in action:
                revert_note = "\nℹ️ *Kullanıcı sunucudan atılmıştı (kick), cezanın haksız olduğu onaylandı.*"

            if interaction.message.embeds:
                orig_embed = interaction.message.embeds[0]
                new_embed = orig_embed.copy()
                new_embed.color = 0xef4444
                new_embed.title = f"🛡️ MODERASYON KANIT DOSYASI • {self.case_id} [REDDEDİLDİ]"

                for idx, f in enumerate(new_embed.fields):
                    if "Status" in f.name:
                        new_embed.set_field_at(
                            idx,
                            name="🚦 Status",
                            value=f"❌ **Reddedildi (Yetersiz Kanıt)**\n👑 **Reddeden Denetleyici:** {interaction.user.mention} (`{now_str}`){revert_note}",
                            inline=False
                        )
                        break

                btn_approve.disabled = True
                btn_reject.disabled = True
                await interaction.response.edit_message(embed=new_embed, view=self)
                await interaction.followup.send(f"❌ **{self.case_id}** numaralı kanıt reddedildi ve uygulanan ceza geri alındı.{revert_note}", ephemeral=True)

        btn_approve.callback = cb_approve
        btn_reject.callback = cb_reject

        self.add_item(btn_approve)
        self.add_item(btn_reject)

class ProofModal(ui.Modal):
    def __init__(self, action_name: str, target: discord.Member, initial_reason: Optional[str] = None):
        super().__init__(title=f"🛡️ {action_name}: {target.display_name}"[:45])
        self.action_name = action_name
        self.target = target

        default_r = initial_reason if initial_reason and initial_reason not in ["None", "No reason provided", "Sebep belirtilmedi", "Səbəb qeyd edilməyib"] else ""
        self.reason_input = ui.TextInput(
            label="📝 Ceza Sebebi",
            style=discord.TextStyle.paragraph,
            placeholder="Ceza sebebini detaylıca yazın...",
            default=default_r,
            required=True,
            max_length=500
        )
        self.proof_input = ui.TextInput(
            label="📸 Resim / Ekran Görüntüsü Kanıt Linki",
            style=discord.TextStyle.short,
            placeholder="Resim linki, Discord dosya bağlantısı (yoksa boş bırakın)",
            required=False,
            max_length=500
        )
        self.add_item(self.reason_input)
        self.add_item(self.proof_input)

        self.submitted = False
        self.reason_val = None
        self.proof_val = None

    async def on_submit(self, interaction: discord.Interaction):
        self.submitted = True
        self.reason_val = self.reason_input.value.strip()
        self.proof_val = self.proof_input.value.strip() or None
        await interaction.response.send_message(
            f"✅ Sebep ve kanıt kaydedildi! Dosya doğrudan <#{PROOF_LOG_CHANNEL_ID}> kanalına iletiliyor...",
            ephemeral=True
        )

class ModeratorProofPromptView(ui.View):
    def __init__(self, moderator: discord.Member, target: discord.Member, action_name: str, initial_reason: Optional[str]):
        super().__init__(timeout=90)
        self.moderator = moderator
        self.target = target
        self.action_name = action_name
        self.final_reason = initial_reason
        self.proof_url = None
        self.completed = False
        self.cancelled = False
        self.message = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.moderator.id:
            await interaction.response.send_message("❌ Bu işlem yalnızca komutu uygulayan yetkiliye aittir!", ephemeral=True)
            return False
        return True

    @ui.button(label="Sebep ve Resim Gir 📝", style=discord.ButtonStyle.primary, emoji="📝")
    async def btn_modal(self, interaction: discord.Interaction, button: ui.Button):
        modal = ProofModal(self.action_name, self.target, self.final_reason)
        await interaction.response.send_modal(modal)
        timed_out = await modal.wait()
        if not timed_out and modal.submitted:
            self.final_reason = modal.reason_val
            self.proof_url = modal.proof_val
            self.completed = True
            self.stop()

    @ui.button(label="İptal Et ❌", style=discord.ButtonStyle.secondary, emoji="❌")
    async def btn_cancel(self, interaction: discord.Interaction, button: ui.Button):
        self.cancelled = True
        self.completed = False
        self.stop()
        await interaction.response.send_message("❌ İşlem iptal edildi.", ephemeral=True)

async def collect_reason_and_proof(ctx: commands.Context, action_name: str, target: discord.Member, initial_reason: Optional[str]) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Yetkili cəza komandası (ban, kick, timeout, warn) verəndə:
    1. Sual yalnız cəzanı icra edən yetkiliyə görünür (Şəxsi Mesaj / DM və ya ekranda yalnız onun görə biləcəyi Modal formu).
    2. Səbəb və şəkil sübutu yazıldıqda birbaşa (pramoy) sübut kanalına (1541541519578628117) göndərilir.
    Returns: (is_success, final_reason, proof_image_url)
    """
    has_valid_reason = bool(initial_reason and initial_reason.strip() not in ["None", "No reason provided", "Sebep belirtilmedi", "Səbəb qeyd edilməyib"])

    proof_image_url = None
    if ctx.message.attachments:
        proof_image_url = ctx.message.attachments[0].url

    if has_valid_reason and proof_image_url:
        return True, initial_reason.strip(), proof_image_url

    prompt_view = ModeratorProofPromptView(ctx.author, target, action_name, initial_reason.strip() if has_valid_reason else None)

    embed = discord.Embed(
        title=f"🛡️ MODERASYON ONAYI: {action_name.upper()}",
        description=(
            f"👤 **Cezalandırılan:** {target.mention} (`{target.id}`)\n"
            f"👮 **Uygulayan Yetkili:** {ctx.author.mention}\n\n"
            f"Lütfen aşağıdaki **'Sebep ve Resim Gir 📝'** butonuna tıklayın.\n"
            f"*(Açılan form **yalnızca sizin ekranınızda** görünecektir. Girdiğiniz sebep ve resim doğrudan kanıt kanalına iletilecektir)*"
        ),
        color=0xf59e0b
    )
    if has_valid_reason:
        embed.add_field(name="📝 Belirtilen Sebep", value=f"`{initial_reason.strip()}`", inline=False)
    embed.set_footer(text="Ayrıca size özel mesaj (DM) da iletildi • Hangisi kolayınıza gelirse oradan yanıtlayabilirsiniz")

    prompt_msg = await ctx.send(embed=embed, view=prompt_view)
    prompt_view.message = prompt_msg

    dm_channel = None
    try:
        dm_channel = await ctx.author.create_dm()
        reason_txt = f" (Qeyd edilmiş səbəb: `{initial_reason.strip()}`)" if has_valid_reason else ""
        if not has_valid_reason:
            await dm_channel.send(
                f"🔔 Merhaba {ctx.author.display_name}! **{target.display_name}** (`{target.id}`) için **{action_name.upper()}** cezası uyguluyorsunuz.\n"
                f"📝 **1. Adım:** Lütfen bu cezanın **sebebini** buraya yazın:\n"
                f"*(Ləğv etmək üçün `ləğv` yazın, vaxt: 90 saniyə)*"
            )
        else:
            await dm_channel.send(
                f"🔔 Merhaba {ctx.author.display_name}! **{target.display_name}** için **{action_name.upper()}** cezası uyguluyorsunuz{reason_txt}.\n"
                f"📸 **Kanıt:** Lütfen bu cezanın **ekran görüntüsü/resim kanıtını** buraya dosya olarak yükleyin veya linkini atın:\n"
                f"*(Kanıt yoksa `yok` yazın, süre: 90 saniye)*"
            )
    except Exception:
        dm_channel = None

    def check_dm(m: discord.Message):
        return dm_channel and m.author.id == ctx.author.id and m.channel.id == dm_channel.id

    async def wait_dm_flow():
        if not dm_channel:
            return None, None
        try:
            curr_reason = initial_reason.strip() if has_valid_reason else None
            if not curr_reason:
                r_msg = await bot.wait_for("message", check=check_dm, timeout=85)
                if r_msg.content.strip().lower() in ["ləğv", "legv", "cancel", "imtina"]:
                    await dm_channel.send("❌ Ceza işlemi iptal edildi.")
                    return "CANCEL", None
                curr_reason = r_msg.content.strip()

                await dm_channel.send(
                    f"✅ Sebep kaydedildi: `{curr_reason}`\n"
                    f"📸 **2. Adım:** Lütfen **resim/ekran görüntüsü kanıtını** buraya dosya olarak yükleyin veya linkini iletin:\n"
                    f"*(Kanıt yoksa `yok` yazın, süre: 90 saniye)*"
                )

            p_msg = await bot.wait_for("message", check=check_dm, timeout=85)
            img_url = None
            if p_msg.attachments:
                img_url = p_msg.attachments[0].url
            elif p_msg.content.strip().startswith(("http://", "https://")):
                img_url = p_msg.content.strip()
            elif p_msg.content.strip().lower() in ["yoxdur", "yox", "none", "no"]:
                img_url = None
            else:
                img_url = p_msg.content.strip()

            await dm_channel.send(f"✅ Sebep ve kanıt resmi doğrudan <#{PROOF_LOG_CHANNEL_ID}> kanalına gönderildi!")
            return curr_reason, img_url
        except Exception:
            return None, None

    dm_task = asyncio.create_task(wait_dm_flow())
    view_task = asyncio.create_task(prompt_view.wait())

    done, pending = await asyncio.wait([dm_task, view_task], return_when=asyncio.FIRST_COMPLETED)

    final_reason_res = None
    proof_url_res = None
    success = False

    if dm_task in done:
        dm_reason, dm_proof = dm_task.result()
        if dm_reason == "CANCEL":
            try:
                await prompt_msg.delete()
            except Exception:
                pass
            return False, None, None
        if dm_reason:
            final_reason_res = dm_reason
            proof_url_res = dm_proof
            success = True

    if not success and prompt_view.completed:
        final_reason_res = prompt_view.final_reason
        proof_url_res = prompt_view.proof_url
        success = True

    for task in pending:
        task.cancel()

    try:
        await prompt_msg.delete()
    except Exception:
        pass

    if not success or prompt_view.cancelled:
        return False, None, None

    return True, final_reason_res, proof_url_res

async def dispatch_moderation_proof(guild: discord.Guild, moderator: discord.Member, target: discord.Member, action: str, reason: str, proof_url: Optional[str]) -> Optional[str]:
    channel = guild.get_channel(PROOF_LOG_CHANNEL_ID)
    if not channel:
        print(f"Kanıt kanalı {PROOF_LOG_CHANNEL_ID} bulunamadı!")
        return None

    case_id = get_next_proof_id()
    db.setdefault("proof_cases", {})[case_id] = {
        "case_id": case_id,
        "moderator_id": moderator.id,
        "target_id": target.id,
        "target_name": str(target),
        "action": action,
        "reason": reason,
        "proof_url": proof_url,
        "status": "pending",
        "created_at": datetime.datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    }
    save_data(db)

    roles_display = " • ".join([f"<@&{r}>" for r in PROOF_REVIEWER_ROLES])
    embed = discord.Embed(
        title=f"🛡️ MODERASYON KANIT DOSYASI • {case_id}",
        description=(
            f"Yetkili tarafından sunucuda moderasyon cezası uygulandı.\n"
            f"Kanıt yalnızca belirlenen 3 denetleyici rolünün ({roles_display}) veya Kurucunun (<@{FOUNDER_ID}>) incelemesi ve onayı için sunulmuştur."
        ),
        color=0xf59e0b,
        timestamp=discord.utils.utcnow()
    )
    embed.add_field(name="👮 Uygulayan Yetkili", value=f"{moderator.mention} (`{moderator.id}`)", inline=True)
    embed.add_field(name="👤 Cezalandırılan Kullanıcı", value=f"{target.mention} (`{target.id}`)", inline=True)
    embed.add_field(name="⚖️ Ceza Türü", value=f"`{action}`", inline=True)
    embed.add_field(name="📝 Ceza Sebebi", value=f"```{reason}```", inline=False)
    embed.add_field(name="👥 Yetkili Denetleyici Roller (Yalnızca bu 3 rol)", value=roles_display, inline=False)

    if proof_url and proof_url.startswith(("http://", "https://")):
        embed.set_image(url=proof_url)
        embed.add_field(name="📸 Sunulan Kanıt", value=f"[Resmi Görüntüle]({proof_url})", inline=False)
    elif proof_url:
        embed.add_field(name="📸 Kanıt Notu", value=f"`{proof_url}`", inline=False)
    else:
        embed.add_field(name="📸 Kanıt Resmi", value="*⚠️ Kanıt resmi sunulmadı (veya 'yok' belirtildi)*", inline=False)

    embed.add_field(
        name="🚦 Status",
        value=(
            "⏳ **Beklemede (3 Denetleyici Rolünün Onayı Bekleniyor)**\n"
            "*Yalnızca bu 3 role sahip olanlar aşağıdaki butonlarla kanıtı onaylayabilir veya yetersiz görerek cezayı otomatik iptal edebilir.*"
        ),
        inline=False
    )
    embed.set_footer(text=f"Dosya: {case_id} • Kanıt Kanalı (ID: {PROOF_LOG_CHANNEL_ID})")

    view = ProofReviewView(case_id=case_id)
    try:
        await channel.send(
            content=f"🔔 **Denetleyici Bildirimi:** {roles_display} — Yeni moderasyon kanıt dosyası geldi!",
            embed=embed,
            view=view
        )
    except Exception as e:
        print(f"Kanıt dosyası gönderilirken hata: {e}")

    return case_id

# =============================================================================
# 2. WARN SİSTEMİ (!warn, !warns, !unwarn)
# =============================================================================
@bot.command(name="warn")
async def cmd_warn(ctx, member: discord.Member, *, reason: Optional[str] = None):
    """!warn @user [sebep]"""
    if has_immunity(member):
        return await ctx.send(f"🛡️ {member.mention} kullanıcısı **Dokunulmazlık Rolüne** (`{IMMUNITY_ROLE_ID}`) sahip olduğu için hiçbir yetkili veya yönetici üzerinde ceza uygulayamaz!")
    if not check_permission(ctx, "warn", WARN_ROLE_ID):
        return await ctx.send(f"❌ Bu komutu yalnızca belirlenen Uyarı (Warn) yetki rolüne sahip olanlar kullanabilir!")

    if member.top_role >= ctx.author.top_role and ctx.author.id != ctx.guild.owner_id and ctx.author.id != FOUNDER_ID:
        return await ctx.send("❌ Bu kullanıcının rolü sizinle eşit veya daha yüksektir!")

    success, final_reason, proof_url = await collect_reason_and_proof(ctx, "Warn", member, reason)
    if not success:
        return

    user_id = str(member.id)
    guild_warns = db["warns"].setdefault(user_id, [])
    guild_warns.append({
        "moderator_id": ctx.author.id,
        "reason": final_reason,
        "time": datetime.datetime.now().strftime("%d.%m.%Y %H:%M"),
        "proof_url": proof_url
    })
    save_data(db)
    total_warns = len(guild_warns)

    await ctx.send(f"⚠️ {member.mention} başarıyla uyarıldı! (Toplam uyarı: **{total_warns}**)\n📸 Kanıt ve dosya onay için <#{PROOF_LOG_CHANNEL_ID}> kanalına gönderildi.")

    log_id = get_next_log_id("WARN")
    embed = discord.Embed(title="⚠️ USER WARNED", color=0xf59e0b, timestamp=discord.utils.utcnow())
    embed.add_field(name="Moderator", value=f"{ctx.author.mention} (`{ctx.author.id}`)", inline=True)
    embed.add_field(name="User", value=f"{member.mention} (`{member.id}`)", inline=True)
    embed.add_field(name="Total Warnings", value=f"`{total_warns}`", inline=True)
    embed.add_field(name="Reason", value=f"`{final_reason}`", inline=False)
    if proof_url and proof_url.startswith(("http://", "https://")):
        embed.set_image(url=proof_url)
    embed.set_footer(text=f"Log ID: {log_id}")
    await send_log(ctx.guild, "warn", embed)

    await dispatch_moderation_proof(
        guild=ctx.guild,
        moderator=ctx.author,
        target=member,
        action="WARN",
        reason=final_reason,
        proof_url=proof_url
    )

@bot.command(name="warns")
async def cmd_warns(ctx, member: Optional[discord.Member] = None):
    """!warns və ya !warns @user"""
    if member:
        user_warns = db["warns"].get(str(member.id), [])
        if not user_warns:
            return await ctx.send(f"✨ {member.mention} kullanıcısının hiç aktif uyarısı bulunmuyor.")

        embed = discord.Embed(title=f"📋 Uyarı Geçmişi: {member.display_name}", color=0x3b82f6)
        embed.description = f"Toplam uyarı sayısı: **{len(user_warns)}**"
        for idx, w in enumerate(user_warns, 1):
            embed.add_field(
                name=f"Warn #{idx} | {w['time']}",
                value=f"Moderator: <@{w['moderator_id']}>\nSəbəb: `{w['reason']}`",
                inline=False
            )
        await ctx.send(embed=embed)
    else:
        all_warns = db.get("warns", {})
        active = {uid: w for uid, w in all_warns.items() if len(w) > 0}
        if not active:
            return await ctx.send("✨ Sunucuda kimsede uyarı bulunmuyor.")

        embed = discord.Embed(title="📋 Sunucu Uyarı Listesi", color=0x3b82f6)
        lines = []
        for uid, w_list in list(active.items())[:25]:
            lines.append(f"• <@{uid}> (`{uid}`) — **{len(w_list)}** warn")
        embed.description = "\n".join(lines)
        await ctx.send(embed=embed)

@bot.command(name="unwarn")
async def cmd_unwarn(ctx, member: discord.Member):
    """!unwarn @user - 1 uyarıyı siler"""
    if has_immunity(member):
        return await ctx.send(f"🛡️ {member.mention} kullanıcısı **Dokunulmazlık Rolüne** (`{IMMUNITY_ROLE_ID}`) sahiptir.")
    if not check_permission(ctx, "warn", WARN_ROLE_ID):
        return await ctx.send(f"❌ Bu komutu yalnızca belirlenen Uyarı (Warn) yetki rolüne sahip olanlar kullanabilir!")

    user_id = str(member.id)
    guild_warns = db["warns"].get(user_id, [])
    if not guild_warns:
        return await ctx.send(f"❌ {member.mention} kullanıcısının hiçbir uyarısı bulunmuyor!")

    guild_warns.pop()
    save_data(db)
    remaining = len(guild_warns)

    await ctx.send(f"🟢 {member.mention} kullanıcısından 1 uyarı silindi! (Kalan uyarı: **{remaining}**)")

    log_id = get_next_log_id("WARN")
    embed = discord.Embed(title="🟢 WARNING REMOVED", color=0x10b981, timestamp=discord.utils.utcnow())
    embed.add_field(name="Moderator", value=f"{ctx.author.mention} (`{ctx.author.id}`)", inline=True)
    embed.add_field(name="User", value=f"{member.mention} (`{member.id}`)", inline=True)
    embed.add_field(name="Remaining Warnings", value=f"`{remaining}`", inline=True)
    embed.set_footer(text=f"Log ID: {log_id}")
    await send_log(ctx.guild, "warn", embed)

# =============================================================================
# 3. ZAR & AFK SİSTEMİ
# =============================================================================
@bot.command(name="zar")
async def cmd_zar(ctx, range_str: str = "1-10"):
    """!zar 1-10 - 1-dən 10-a qədər random bir rəqəm seçir"""
    try:
        if "-" in range_str:
            parts = range_str.split("-")
            low = int(parts[0].strip())
            high = int(parts[1].strip())
        else:
            low = 1
            high = int(range_str.strip())

        if low > high:
            low, high = high, low

        result = random.randint(low, high)
        await ctx.send(f"🎲 {ctx.author.mention}, zar atıldı! Sonuç: **{result}** *(Aralık: {low} - {high})*")
    except Exception:
        await ctx.send("❌ Doğru formatta yazın! Örnek: `!zar 1-10` veya `!zar 100`")

@bot.command(name="afk")
async def cmd_afk(ctx, *, reason: str = "AFK"):
    """a!afk [sebeb]"""
    user_id = str(ctx.author.id)
    db["afk"][user_id] = {
        "reason": reason,
        "time": datetime.datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    }
    save_data(db)
    await ctx.send(f"💤 {ctx.author.mention}, AFK moduna geçtiniz! Sebep: `{reason}`")

# =============================================================================
# 4. MODERASİYA KOMANDALARI (CONFIG ROLLARI DƏSTƏYİ İLƏ)
# =============================================================================
@bot.command(name="ban")
async def cmd_ban(ctx, member: discord.Member, *, reason: Optional[str] = None):
    """a!ban @user [sebep]"""
    if has_immunity(member):
        return await ctx.send(f"🛡️ {member.mention} kullanıcısı **Dokunulmazlık Rolüne** (`{IMMUNITY_ROLE_ID}`) sahip olduğu için banlanamaz!")
    if not (ctx.author.guild_permissions.ban_members or check_permission(ctx, "ban")):
        return await ctx.send("❌ Bu komutu kullanmak için Ban yetki rolüne sahip olmalısınız!")

    if member.top_role >= ctx.author.top_role and ctx.author.id != ctx.guild.owner_id and ctx.author.id != FOUNDER_ID:
        return await ctx.send("❌ Bu kullanıcının rolü sizinle eşit veya daha yüksektir!")

    success, final_reason, proof_url = await collect_reason_and_proof(ctx, "Ban", member, reason)
    if not success:
        return

    await member.ban(reason=f"{ctx.author.name}: {final_reason}")
    await ctx.send(f"🔨 {member.mention} başarıyla sunucudan yasaklandı (ban). Sebep: `{final_reason}`\n📸 Kanıt ve dosya onay için <#{PROOF_LOG_CHANNEL_ID}> kanalına gönderildi.")

    await dispatch_moderation_proof(
        guild=ctx.guild,
        moderator=ctx.author,
        target=member,
        action="BAN",
        reason=final_reason,
        proof_url=proof_url
    )

@bot.command(name="unban")
async def cmd_unban(ctx, user_id: int, *, reason: str = "Sebep belirtilmedi"):
    """a!unban <user_id> [sebeb]"""
    if not (ctx.author.guild_permissions.ban_members or check_permission(ctx, "ban")):
        return await ctx.send("❌ Bu komutu kullanmak için Ban yetki rolüne sahip olmalısınız!")

    user = await bot.fetch_user(user_id)
    await ctx.guild.unban(user, reason=f"{ctx.author.name}: {reason}")
    await ctx.send(f"🔓 **{user}** (`{user.id}`) kullanıcısının banı kaldırıldı.")

@bot.command(name="banlist")
async def cmd_banlist(ctx):
    """a!banlist - Sunucudan yasaklanan kullanıcıların listesi"""
    if not (ctx.author.guild_permissions.ban_members or check_permission(ctx, "ban")):
        return await ctx.send("❌ Bu komutu kullanmak için Ban yetki rolüne sahip olmalısınız!")

    bans = [entry async for entry in ctx.guild.bans(limit=50)]
    if not bans:
        return await ctx.send("✨ Sunucuda şu anda yasaklı kullanıcı bulunmuyor.")

    embed = discord.Embed(title=f"🔨 Ban Listesi ({len(bans)} kişi)", color=0xef4444)
    desc = []
    for b in bans[:25]:
        desc.append(f"• **{b.user}** (`{b.user.id}`) — Səbəb: `{b.reason or 'Yoxdur'}`")
    embed.description = "\n".join(desc)
    await ctx.send(embed=embed)

@bot.command(name="kick")
async def cmd_kick(ctx, member: discord.Member, *, reason: Optional[str] = None):
    """a!kick @user [sebep]"""
    if has_immunity(member):
        return await ctx.send(f"🛡️ {member.mention} kullanıcısı **Dokunulmazlık Rolüne** (`{IMMUNITY_ROLE_ID}`) sahip olduğu için sunucudan atılamaz!")
    if not (ctx.author.guild_permissions.kick_members or check_permission(ctx, "kick")):
        return await ctx.send("❌ Bu komutu kullanmak için Kick yetki rolüne sahip olmalısınız!")

    if member.top_role >= ctx.author.top_role and ctx.author.id != ctx.guild.owner_id and ctx.author.id != FOUNDER_ID:
        return await ctx.send("❌ Bu kullanıcının rolü sizinle eşit veya daha yüksektir!")

    success, final_reason, proof_url = await collect_reason_and_proof(ctx, "Kick", member, reason)
    if not success:
        return

    await member.kick(reason=f"{ctx.author.name}: {final_reason}")
    await ctx.send(f"👢 {member.mention} sunucudan atıldı (kick). Sebep: `{final_reason}`\n📸 Kanıt ve dosya onay için <#{PROOF_LOG_CHANNEL_ID}> kanalına gönderildi.")

    await dispatch_moderation_proof(
        guild=ctx.guild,
        moderator=ctx.author,
        target=member,
        action="KICK",
        reason=final_reason,
        proof_url=proof_url
    )

@bot.command(name="timeout", aliases=["mute"])
async def cmd_timeout(ctx, member: discord.Member, minutes: Optional[int] = None, *, reason: Optional[str] = None):
    """a!timeout @user [dakika] [sebep]"""
    if has_immunity(member):
        return await ctx.send(f"🛡️ {member.mention} kullanıcısı **Dokunulmazlık Rolüne** (`{IMMUNITY_ROLE_ID}`) sahip olduğu için susturulamaz (mute/timeout uygulanamaz)!")
    if not (ctx.author.guild_permissions.moderate_members or check_permission(ctx, "timeout")):
        return await ctx.send("❌ Bu komutu kullanmak için Timeout yetki rolüne sahip olmalısınız!")

    if member.top_role >= ctx.author.top_role and ctx.author.id != ctx.guild.owner_id and ctx.author.id != FOUNDER_ID:
        return await ctx.send("❌ Bu kullanıcının rolü sizinle eşit veya daha yüksektir!")

    if minutes is None:
        minutes = 10

    success, final_reason, proof_url = await collect_reason_and_proof(ctx, f"Timeout ({minutes} dəq)", member, reason)
    if not success:
        return

    until = discord.utils.utcnow() + datetime.timedelta(minutes=minutes)
    await member.timeout(until, reason=f"{ctx.author.name}: {final_reason}")
    await ctx.send(f"⏱️ {member.mention} kullanıcısına **{minutes} dakikalık** timeout verildi. Sebep: `{final_reason}`\n📸 Kanıt ve dosya onay için <#{PROOF_LOG_CHANNEL_ID}> kanalına gönderildi.")

    await dispatch_moderation_proof(
        guild=ctx.guild,
        moderator=ctx.author,
        target=member,
        action=f"TIMEOUT ({minutes} dəq)",
        reason=final_reason,
        proof_url=proof_url
    )

@bot.command(name="untimeout", aliases=["unmute"])
async def cmd_untimeout(ctx, member: discord.Member):
    """a!untimeout @user"""
    if has_immunity(member):
        return await ctx.send(f"🛡️ {member.mention} kullanıcısı **Dokunulmazlık Rolüne** (`{IMMUNITY_ROLE_ID}`) sahiptir.")
    if not (ctx.author.guild_permissions.moderate_members or check_permission(ctx, "timeout")):
        return await ctx.send("❌ Bu komutu kullanmak için Timeout yetki rolüne sahip olmalısınız!")

    await member.timeout(None, reason=f"{ctx.author.name} tarafından timeout kaldırıldı")
    await ctx.send(f"🔓 {member.mention} üzerinden timeout kaldırıldı.")

@bot.command(name="sil", aliases=["clear", "purge", "temizle"])
async def cmd_sil(ctx, amount: Optional[int] = None):
    """!sil say - Son 'say' qədər mesajı silir (Maksimum 100)"""
    if not (ctx.author.guild_permissions.manage_messages or ctx.author.guild_permissions.administrator or ctx.author.id == FOUNDER_ID or ctx.author.id == ctx.guild.owner_id):
        return await ctx.send("❌ Bu komutu kullanmak için Mesajları Yönet veya Yönetici yetkiniz olmalıdır!")

    if amount is None:
        return await ctx.send("❌ Lütfen silinecek mesaj sayısını girin! Örnek: `!sil 5` (Maksimum 100)")

    if amount < 1:
        return await ctx.send("❌ En az 1 mesaj silinmelidir!")

    if amount > 100:
        amount = 100

    deleted = await ctx.channel.purge(limit=amount + 1)
    actual_count = max(0, len(deleted) - 1)
    msg = await ctx.send(f"🧹 **{actual_count}** adet mesaj silindi.")
    await asyncio.sleep(3)
    try:
        await msg.delete()
    except Exception:
        pass

# =============================================================================
# KANAL SİLMƏ VƏ TƏSDİQ SİSTEMİ (a!delete & a!deletepanel)
# =============================================================================
class ChannelDeleteConfirmView(ui.View):
    def __init__(self, author: discord.Member, target_channel: discord.abc.GuildChannel):
        super().__init__(timeout=60)
        self.author = author
        self.target_channel = target_channel
        self.message = None
        self.confirmed = False

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author.id and not can_manage_channels(interaction.user):
            await interaction.response.send_message("❌ Bu onay butonunu yalnızca komutu başlatan yetkili kullanabilir!", ephemeral=True)
            return False
        return True

    @ui.button(label="Evet, Kanalı Sil", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def confirm(self, interaction: discord.Interaction, button: ui.Button):
        self.confirmed = True
        for child in self.children:
            child.disabled = True

        chan_name = self.target_channel.name
        chan_id = self.target_channel.id
        is_same = (interaction.channel.id == self.target_channel.id)

        try:
            await interaction.response.edit_message(content=f"🗑️ `#{chan_name}` kanalı siliniyor...", embed=None, view=self)
        except Exception:
            pass

        await asyncio.sleep(1)
        try:
            await self.target_channel.delete(reason=f"Kanal {interaction.user} ({interaction.user.id}) tarafından a!delete ile onaylanarak silindi.")
            if not is_same:
                await interaction.followup.send(f"✅ `#{chan_name}` (`{chan_id}`) kanalı başarıyla silindi.", ephemeral=True)
        except discord.Forbidden:
            if not is_same:
                await interaction.followup.send("❌ Botun bu kanalı silmek için `Kanalları Yönet` izni yetersiz!", ephemeral=True)
        except Exception as e:
            if not is_same:
                await interaction.followup.send(f"❌ Kanal silinirken hata oluştu: {e}", ephemeral=True)

    @ui.button(label="Ləğv Et", style=discord.ButtonStyle.secondary, emoji="❌")
    async def cancel(self, interaction: discord.Interaction, button: ui.Button):
        self.confirmed = True
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(content=f"❌ **#{self.target_channel.name}** kanalının silinmesi iptal edildi.", embed=None, view=self)

    async def on_timeout(self):
        if not self.confirmed and self.message:
            for child in self.children:
                child.disabled = True
            try:
                await self.message.edit(content="⌛ Onay süresi (60 saniye) doldu. Silme iptal edildi.", embed=None, view=self)
            except Exception:
                pass

@bot.command(name="delete", aliases=["kanalsil", "channeldelete", "deletechannel"])
async def cmd_delete(ctx, target_channel: Optional[discord.abc.GuildChannel] = None):
    """a!delete [#kanal] - Kanalı silmək üçün təsdiq paneli açır və təsdiq edildikdə kanalı silir (Yalnız yetkililər)"""
    if not can_manage_channels(ctx.author):
        return await ctx.send("❌ Bu komutu yalnızca Kanalları Yönet yetkisine sahip yetkililer kullanabilir!")

    target = target_channel or ctx.channel
    is_private = not target.permissions_for(ctx.guild.default_role).view_channel
    status_str = "🔒 Gizli (Özel Kanal)" if is_private else "🌐 Açık (Herkese Açık Kanal)"

    embed = discord.Embed(
        title="⚠️ KANAL SİLME ONAYI",
        description=(
            f"🛑 **{target.mention}** (`#{target.name}`) kanalını tamamen silmek istediğinizden emin misiniz?\n\n"
            f"• **Kanal:** `#{target.name}`\n"
            f"• **Kanal ID:** `{target.id}`\n"
            f"• **Kanal Türü:** `{str(target.type).capitalize()}`\n"
            f"• **Status:** {status_str}\n\n"
            f"⚠️ **DİKKAT:** Bu işlem geri alınamaz! Kanal içerisindeki tüm mesajlar, dosyalar ve ayarlar anında silinecektir."
        ),
        color=0xef4444,
        timestamp=discord.utils.utcnow()
    )
    embed.set_footer(text=f"Onaylamak için 60 saniyeniz var • Yalnızca {ctx.author.display_name} onaylayabilir")
    view = ChannelDeleteConfirmView(ctx.author, target)
    msg = await ctx.send(embed=embed, view=view)
    view.message = msg

def build_deletepanel_embed(guild: discord.Guild, selected_channels: List[discord.abc.GuildChannel] = None) -> discord.Embed:
    selected_channels = selected_channels or []
    
    total_chans = len(guild.channels)
    text_chans = len(guild.text_channels)
    voice_chans = len(guild.voice_channels)
    cat_chans = len(guild.categories)

    private_channels = []
    public_channels = []

    for ch in guild.channels:
        if isinstance(ch, discord.CategoryChannel):
            continue
        is_priv = not ch.permissions_for(guild.default_role).view_channel
        if is_priv:
            private_channels.append(ch)
        else:
            public_channels.append(ch)

    embed = discord.Embed(
        title="🎛️ TOPLU KANAL İDARƏETMƏ & SİLMƏ PANELİ",
        description=(
            f"🏰 **Server:** `{guild.name}`\n"
            f"📊 **Ümumi Kanallar:** `{total_chans}` (Mətn: `{text_chans}` | Səs: `{voice_chans}` | Kateqoriya: `{cat_chans}`)\n"
            f"🔒 **Gizli Kanallar:** `{len(private_channels)}` | 🌐 **Açıq Kanallar:** `{len(public_channels)}`\n\n"
            f"Aşağıdakı menyudan **1 və ya bir neçə kanalı** seçin. Seçim etdikdən sonra **'Seçilən Kanalları Sürətli Sil'** düyməsini sıxaraq onları dərhal silə bilərsiniz."
        ),
        color=0x5865F2,
        timestamp=discord.utils.utcnow()
    )

    # Show list of private and public channels
    priv_display = []
    for pch in private_channels[:15]:
        icon = "🔊" if isinstance(pch, discord.VoiceChannel) else "🔒"
        priv_display.append(f"{icon} `{pch.name}`")
    if len(private_channels) > 15:
        priv_display.append(f"*...və daha {len(private_channels) - 15} gizli kanal*")
    embed.add_field(
        name=f"🔒 Gizli (Özəl) Kanallar ({len(private_channels)})",
        value="\n".join(priv_display) if priv_display else "*Gizli kanal yoxdur*",
        inline=True
    )

    pub_display = []
    for pub_ch in public_channels[:15]:
        icon = "🔊" if isinstance(pub_ch, discord.VoiceChannel) else "🌐"
        pub_display.append(f"{icon} `{pub_ch.name}`")
    if len(public_channels) > 15:
        pub_display.append(f"*...və daha {len(public_channels) - 15} açıq kanal*")
    embed.add_field(
        name=f"🌐 Açıq (İctimai) Kanallar ({len(public_channels)})",
        value="\n".join(pub_display) if pub_display else "*Açıq kanal yoxdur*",
        inline=True
    )

    if selected_channels:
        sel_text = []
        for ch in selected_channels:
            is_priv = not ch.permissions_for(guild.default_role).view_channel
            icon = "🔒" if is_priv else ("🔊" if isinstance(ch, discord.VoiceChannel) else ("📁" if isinstance(ch, discord.CategoryChannel) else "🌐"))
            sel_text.append(f"• {icon} **{ch.name}** (`{ch.id}`)")
        embed.add_field(
            name=f"🎯 Hazırda Seçilmiş Kanallar ({len(selected_channels)} ədəd)",
            value="\n".join(sel_text[:20]) + (f"\n*...və daha {len(sel_text) - 20} kanal*" if len(sel_text) > 20 else ""),
            inline=False
        )

    embed.set_footer(text="Diqqətli olun: Kanalların silinməsi geri qaytarıla bilməz!")
    return embed

class DeletePanelChannelSelect(ui.ChannelSelect):
    def __init__(self):
        super().__init__(
            placeholder="Silmək istədiyiniz kanalları seçin (1-25 ədəd)...",
            min_values=1,
            max_values=25,
            channel_types=[
                discord.ChannelType.text,
                discord.ChannelType.voice,
                discord.ChannelType.stage_voice,
                discord.ChannelType.news,
                discord.ChannelType.category
            ]
        )

    async def callback(self, interaction: discord.Interaction):
        if not can_manage_channels(interaction.user):
            return await interaction.response.send_message("❌ İzniniz yok!", ephemeral=True)

        self.view.selected_channels = self.values
        self.view.update_components()
        embed = build_deletepanel_embed(interaction.guild, self.view.selected_channels)
        await interaction.response.edit_message(embed=embed, view=self.view)

class DeletePanelView(ui.View):
    def __init__(self, author: discord.Member, original_message=None):
        super().__init__(timeout=300)
        self.author = author
        self.original_message = original_message
        self.selected_channels: List[discord.abc.GuildChannel] = []
        self.update_components()

    def update_components(self):
        self.clear_items()
        self.add_item(DeletePanelChannelSelect())

        count = len(self.selected_channels)
        btn_delete = ui.Button(
            label=f"Seçilən Kanalları Sürətli Sil ({count})" if count > 0 else "Kanalları Sil",
            style=discord.ButtonStyle.danger,
            emoji="🗑️",
            disabled=(count == 0),
            row=1
        )
        btn_clear = ui.Button(
            label="Seçimi Sıfırla",
            style=discord.ButtonStyle.secondary,
            emoji="🔄",
            disabled=(count == 0),
            row=1
        )
        btn_close = ui.Button(
            label="Paneli Kapat",
            style=discord.ButtonStyle.secondary,
            emoji="✖️",
            row=1
        )

        async def cb_delete(interaction: discord.Interaction):
            if not can_manage_channels(interaction.user):
                return await interaction.response.send_message("❌ Bu işlemi yalnızca kanal yetkilileri yapabilir!", ephemeral=True)

            if not self.selected_channels:
                return await interaction.response.send_message("❌ Əvvəlcə silinəcək ən azı 1 kanal seçməlisiniz!", ephemeral=True)

            current_chan_id = interaction.channel.id
            current_is_deleted = any(ch.id == current_chan_id for ch in self.selected_channels)

            target_list = list(self.selected_channels)
            self.selected_channels = []
            self.update_components()

            await interaction.response.defer(ephemeral=True)

            deleted_list = []
            failed_list = []

            async def do_delete(ch):
                try:
                    cname = ch.name
                    cid = ch.id
                    is_priv = not ch.permissions_for(interaction.guild.default_role).view_channel
                    icon = "🔒" if is_priv else ("🔊" if isinstance(ch, discord.VoiceChannel) else ("📁" if isinstance(ch, discord.CategoryChannel) else "🌐"))
                    await ch.delete(reason=f"Toplu silinmə a!deletepanel vasitəsilə: {interaction.user} ({interaction.user.id})")
                    deleted_list.append(f"{icon} `#{cname}` (`{cid}`)")
                except Exception as err:
                    failed_list.append(f"`#{ch.name}`: {err}")

            # Sürətli paralel silinmə
            await asyncio.gather(*[do_delete(ch) for ch in target_list], return_exceptions=True)

            if not current_is_deleted:
                try:
                    res_embed = discord.Embed(
                        title="⚡ TOPLU KANAL SİLMƏ ƏMƏLİYYATI TAMAMLANDI",
                        description=f"✅ Cəmi **{len(deleted_list)}** kanal sürətli şəkildə silindi.",
                        color=0x10b981 if not failed_list else 0xf59e0b,
                        timestamp=discord.utils.utcnow()
                    )
                    if deleted_list:
                        res_embed.add_field(
                            name=f"🗑️ Silinmiş Kanallar ({len(deleted_list)})",
                            value="\n".join(deleted_list[:25]) + (f"\n*...və daha {len(deleted_list) - 25} kanal*" if len(deleted_list) > 25 else ""),
                            inline=False
                        )
                    if failed_list:
                        res_embed.add_field(
                            name=f"❌ Hata Oluşanlar ({len(failed_list)})",
                            value="\n".join(failed_list[:10]),
                            inline=False
                        )
                    res_embed.set_footer(text=f"Əmri icra edən: {interaction.user.display_name}")
                    await interaction.channel.send(embed=res_embed)
                    await interaction.followup.send(f"✅ İşlem başarıyla tamamlandı! {len(deleted_list)} kanal silindi.", ephemeral=True)
                except Exception:
                    pass

        async def cb_clear(interaction: discord.Interaction):
            if not can_manage_channels(interaction.user):
                return await interaction.response.send_message("❌ İzniniz yok!", ephemeral=True)
            self.selected_channels = []
            self.update_components()
            embed = build_deletepanel_embed(interaction.guild, [])
            await interaction.response.edit_message(embed=embed, view=self)

        async def cb_close(interaction: discord.Interaction):
            if not can_manage_channels(interaction.user):
                return await interaction.response.send_message("❌ İzniniz yok!", ephemeral=True)
            await interaction.message.delete()

        btn_delete.callback = cb_delete
        btn_clear.callback = cb_clear
        btn_close.callback = cb_close

        self.add_item(btn_delete)
        self.add_item(btn_clear)
        self.add_item(btn_close)

@bot.command(name="deletepanel", aliases=["kanallarpanel", "bulkdeletepanel", "delpanel"])
async def cmd_deletepanel(ctx):
    """a!deletepanel - Bütün gizli və açıq kanalların siyahılandığı, çoxsaylı kanal seçib sürətli silmə paneli"""
    if not can_manage_channels(ctx.author):
        return await ctx.send("❌ Bu yönetim panelini yalnızca Kanalları Yönet veya Yönetici yetkisine sahip üyeler açabilir!")

    embed = build_deletepanel_embed(ctx.guild, [])
    view = DeletePanelView(author=ctx.author)
    msg = await ctx.send(embed=embed, view=view)
    view.original_message = msg

@bot.command(name="restart", aliases=["nuke", "kanalsifirla", "kanalsıfırla", "yenile", "kanalyenile", "kanaltemizle"])
async def cmd_restart(ctx):
    """!restart / !nuke - Kanalın bütün mesajlarını siler, klonlayarak tertemiz yeniden başlatır"""
    if not can_manage_channels(ctx.author):
        return await ctx.send("❌ Bu komutu kullanmak için Kanalları Yönet veya Yönetici yetkiniz olmalıdır!")

    old_channel = ctx.channel
    pos = old_channel.position
    try:
        new_channel = await old_channel.clone(reason=f"Kanal {ctx.author} tarafından yeniden başlatıldı (restart)")
        await old_channel.delete(reason=f"Kanal {ctx.author} tarafından yeniden başlatıldı (restart)")
        await new_channel.edit(position=pos)
        embed = discord.Embed(
            title="🔄 Kanal Yeniden Başlatıldı (Restart)!",
            description=(
                f"Bu kanaldaki bütün mesajlar silindi ve kanal başarıyla sıfırlandı!\n\n"
                f"👑 **Yetkili:** {ctx.author.mention}\n"
                f"🧹 **İşlem:** Kanal klonlandı ve tüm mesaj geçmişi temizlendi.\n"
                f"⚡ **Durum:** Aktif & Tertemiz"
            ),
            color=0x10b981,
            timestamp=discord.utils.utcnow()
        )
        embed.set_image(url="https://media.giphy.com/media/oe33xf3B50fsc/giphy.gif")
        embed.set_footer(text=f"Sunucu: {ctx.guild.name}")
        await new_channel.send(embed=embed)
    except Exception as e:
        await ctx.send(f"❌ Kanal yeniden başlatılırken bir hata oluştu: {e}")

@bot.command(name="sayim", aliases=["say", "sayi", "sunucusay", "count"])
async def cmd_sayim(ctx):
    """!sayim / !say - Sunucunun gerçek zamanlı detaylı üye, ses, aktiflik ve boost sayımını gösterir"""
    guild = ctx.guild
    total_members = guild.member_count or len(guild.members)
    online_members = sum(1 for m in guild.members if m.status in [discord.Status.online, discord.Status.idle, discord.Status.dnd])
    voice_members = sum(len(vc.members) for vc in guild.voice_channels)
    bots_count = sum(1 for m in guild.members if m.bot)
    humans_count = total_members - bots_count
    boost_count = guild.premium_subscription_count or 0
    boost_level = guild.premium_tier
    text_channels_count = len(guild.text_channels)
    voice_channels_count = len(guild.voice_channels)
    roles_count = len(guild.roles)

    embed = discord.Embed(
        title=f"📊 {guild.name} — Sunucu Sayım İstatistikleri",
        description="Sunucunun anlık canlı üye, ses ve aktiflik durum tablosu:",
        color=0x6366f1,
        timestamp=discord.utils.utcnow()
    )
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    embed.add_field(name="👥 Toplam Üye", value=f"**{total_members:,}**", inline=True)
    embed.add_field(name="🟢 Aktif / Çevrimiçi", value=f"**{online_members:,}**", inline=True)
    embed.add_field(name="🎙️ Sesteki Üyeler", value=f"**{voice_members:,}**", inline=True)
    embed.add_field(name="👤 Gerçek Kullanıcı", value=f"**{humans_count:,}**", inline=True)
    embed.add_field(name="🤖 Botlar", value=f"**{bots_count:,}**", inline=True)
    embed.add_field(name=f"🚀 Boost (Seviye {boost_level})", value=f"**{boost_count}** Takviye", inline=True)
    embed.add_field(name="💬 Metin Kanalları", value=f"**{text_channels_count}**", inline=True)
    embed.add_field(name="🔊 Ses Kanalları", value=f"**{voice_channels_count}**", inline=True)
    embed.add_field(name="🏷️ Toplam Rol", value=f"**{roles_count}**", inline=True)
    embed.set_footer(text=f"İsteyen: {ctx.author.display_name}")
    await ctx.send(embed=embed)

@bot.command(name="yaz", aliases=["echo", "botyaz", "duyuruyaz"])
@commands.has_permissions(manage_messages=True)
async def cmd_yaz(ctx, *, text: str):
    """!yaz [metin] - Bot üzerinden kanala mesaj yazdırır"""
    try:
        await ctx.message.delete()
    except Exception:
        pass
    await ctx.send(text)

@bot.command(name="embed", aliases=["embedyaz", "duyuruembed"])
@commands.has_permissions(manage_messages=True)
async def cmd_embed(ctx, *, content: str):
    """!embed Başlık | İçerik | [Renk Kodu] - Özel tasarımlı duyuru kutusu gönderir"""
    parts = [p.strip() for p in content.split("|")]
    title = parts[0]
    desc = parts[1] if len(parts) > 1 else ""
    color_hex = parts[2] if len(parts) > 2 else "6366f1"
    try:
        color_int = int(color_hex.replace("#", ""), 16)
    except ValueError:
        color_int = 0x6366f1

    try:
        await ctx.message.delete()
    except Exception:
        pass

    embed = discord.Embed(title=title, description=desc, color=color_int, timestamp=discord.utils.utcnow())
    embed.set_footer(text=f"Yayınlayan: {ctx.author.display_name}", icon_url=ctx.author.display_avatar.url if ctx.author.display_avatar else None)
    await ctx.send(embed=embed)

@bot.command(name="nick")
@commands.has_permissions(manage_nicknames=True)
async def cmd_nick(ctx, member: discord.Member, *, new_nick: str):
    """!nick @user yeni_ad - Kullanıcının takma adını değiştirir"""
    if has_immunity(member):
        return await ctx.send(f"🛡️ {member.mention} kullanıcısı **Dokunulmazlık Rolüne** (`{IMMUNITY_ROLE_ID}`) sahip olduğu için takma adı değiştirilemez!")
    old_nick = member.display_name
    await member.edit(nick=new_nick)
    await ctx.send(f"🏷️ {member.mention} kullanıcısının takma adı değiştirildi: `{old_nick}` ➔ `{new_nick}`")

@bot.command(name="role")
@commands.has_permissions(manage_roles=True)
async def cmd_role(ctx, member: discord.Member, role: discord.Role):
    """!role @user @rol - Kullanıcıda rol varsa alır, yoksa verir"""
    if has_immunity(member):
        return await ctx.send(f"🛡️ {member.mention} kullanıcısı **Dokunulmazlık Rolüne** (`{IMMUNITY_ROLE_ID}`) sahip olduğu için üzerinde rol işlemi uygulanamaz!")
    if role >= ctx.guild.me.top_role:
        return await ctx.send(f"❌ Bu rol benim en yüksek rolümden ({ctx.guild.me.top_role.mention}) daha yüksek veya eşit olduğu için işlem yapamam!")
    if ctx.author.id != ctx.guild.owner_id and ctx.author.id != FOUNDER_ID and role >= ctx.author.top_role:
        return await ctx.send("❌ Kendi en yüksek rolünüzden daha yüksek veya eşit bir rol üzerinde işlem yapamazsınız!")

    if role in member.roles:
        await member.remove_roles(role)
        await ctx.send(f"➖ {member.mention} kullanıcısından {role.mention} rolü alındı.")
    else:
        await member.add_roles(role)
        await ctx.send(f"➕ {member.mention} kullanıcısına {role.mention} rolü verildi.")

@bot.command(name="rolver", aliases=["addrole", "rolekle"])
@commands.has_permissions(manage_roles=True)
async def cmd_rolver(ctx, member: discord.Member, role: discord.Role):
    """!rolver @üye @rol - Belirtilen üyeye belirtilen rolü ekler"""
    if has_immunity(member):
        return await ctx.send(f"🛡️ {member.mention} kullanıcısı **Dokunulmazlık Rolüne** (`{IMMUNITY_ROLE_ID}`) sahip olduğu için rol verilemez!")
    if role in member.roles:
        return await ctx.send(f"ℹ️ {member.mention} kullanıcısı zaten {role.mention} rolüne sahip.")
    if role >= ctx.guild.me.top_role:
        return await ctx.send(f"❌ Bu rol benim en yüksek rolümden ({ctx.guild.me.top_role.mention}) daha yüksek veya eşit olduğu için veremem!")
    if ctx.author.id != ctx.guild.owner_id and ctx.author.id != FOUNDER_ID and role >= ctx.author.top_role:
        return await ctx.send("❌ Kendi en yüksek rolünüzden daha yüksek veya eşit bir rolü veremezsiniz!")

    await member.add_roles(role, reason=f"Rol {ctx.author} tarafından verildi")
    embed = discord.Embed(
        title="➕ Rol Verildi",
        description=f"{member.mention} kullanıcısına {role.mention} rolü başarıyla verildi.",
        color=0x10b981
    )
    embed.set_footer(text=f"Yetkili: {ctx.author.display_name}")
    await ctx.send(embed=embed)

@bot.command(name="rolal", aliases=["removerole", "rolcikar", "rolçıkar"])
@commands.has_permissions(manage_roles=True)
async def cmd_rolal(ctx, member: discord.Member, role: discord.Role):
    """!rolal @üye @rol - Belirtilen üyeden belirtilen rolü kaldırır"""
    if has_immunity(member):
        return await ctx.send(f"🛡️ {member.mention} kullanıcısı **Dokunulmazlık Rolüne** (`{IMMUNITY_ROLE_ID}`) sahip olduğu için rol alınamaz!")
    if role not in member.roles:
        return await ctx.send(f"ℹ️ {member.mention} kullanıcısı zaten {role.mention} rolüne sahip değil.")
    if role >= ctx.guild.me.top_role:
        return await ctx.send(f"❌ Bu rol benim en yüksek rolümden ({ctx.guild.me.top_role.mention}) daha yüksek veya eşit olduğu için alamam!")
    if ctx.author.id != ctx.guild.owner_id and ctx.author.id != FOUNDER_ID and role >= ctx.author.top_role:
        return await ctx.send("❌ Kendi en yüksek rolünüzden daha yüksek veya eşit bir rolü alamazsınız!")

    await member.remove_roles(role, reason=f"Rol {ctx.author} tarafından alındı")
    embed = discord.Embed(
        title="➖ Rol Alındı",
        description=f"{member.mention} kullanıcısından {role.mention} rolü başarıyla alındı.",
        color=0xef4444
    )
    embed.set_footer(text=f"Yetkili: {ctx.author.display_name}")
    await ctx.send(embed=embed)

@bot.command(name="slowmode", aliases=["yavaşmod", "yavasmod", "yavas-mod", "yavas"])
async def cmd_slowmode(ctx, seconds: Optional[str] = None):
    """!slowmode / !yavaşmod [saniye/kapat] - Kanalın yavaş mod süresini ayarlar"""
    if not can_manage_channels(ctx.author):
        return await ctx.send("❌ Bu komutu kullanmak için Kanalları Yönet veya Yönetici yetkiniz olmalıdır!")

    if seconds is None:
        return await ctx.send("ℹ️ Lütfen bir süre belirtin! Örnek: `!yavaşmod 5` veya kapatmak için `!yavaşmod 0` (veya `!yavaşmod kapat`)")

    if seconds.lower() in ["kapat", "off", "sıfır", "sifir"]:
        sec = 0
    else:
        clean_s = seconds.lower().replace("s", "").replace("sn", "")
        if "m" in seconds.lower() or "dk" in seconds.lower():
            clean_s = clean_s.replace("m", "").replace("dk", "")
            try:
                sec = int(float(clean_s) * 60)
            except ValueError:
                return await ctx.send("❌ Geçersiz süre formatı! Örnek: `!yavaşmod 10` veya `!yavaşmod 1dk`")
        else:
            try:
                sec = int(clean_s)
            except ValueError:
                return await ctx.send("❌ Geçersiz süre! Lütfen saniye olarak sayı girin (Maksimum 21600 saniye / 6 saat).")

    if sec < 0 or sec > 21600:
        return await ctx.send("❌ Yavaş mod süresi 0 ile 21600 saniye (6 saat) arasında olmalıdır!")

    await ctx.channel.edit(slowmode_delay=sec)
    if sec == 0:
        await ctx.send("⏱️ Bu kanal için **yavaş mod kapatıldı**.")
    else:
        await ctx.send(f"⏱️ Bu kanal için yavaş mod süresi **{sec} saniye** olarak ayarlandı.")

@bot.command(name="kilitle", aliases=["lock", "kilit", "kanalkilitle", "channellock"])
async def cmd_lock(ctx, channel: Optional[discord.TextChannel] = None, *, reason: Optional[str] = None):
    """!kilitle [#kanal] [sebep] - Kanalı kilitler, yetkisi olmayan hiç kimse mesaj yazamaz"""
    if not can_manage_channels(ctx.author):
        return await ctx.send("❌ Bu komutu kullanmak için Kanalları Yönet veya Yönetici yetkiniz olmalıdır!")

    target = channel or ctx.channel
    try:
        current_overwrite = target.overwrites_for(ctx.guild.default_role)
        current_overwrite.send_messages = False
        current_overwrite.send_messages_in_threads = False
        current_overwrite.create_public_threads = False
        current_overwrite.create_private_threads = False
        current_overwrite.add_reactions = False
        await target.set_permissions(ctx.guild.default_role, overwrite=current_overwrite, reason=f"Kanal {ctx.author} tarafından kilitlendi: {reason or 'Sebep belirtilmedi'}")

        embed = discord.Embed(
            title="🔒 Kanal Kilitlendi!",
            description=(
                f"**Kanal:** {target.mention} (`{target.name}`)\n"
                f"Bu kanal {ctx.author.mention} tarafından mesaj gönderimine kapatıldı.\n"
                f"Artık yetkisi olmayan hiçbir üye bu kanala yazı yazamaz."
            ),
            color=0xef4444,
            timestamp=discord.utils.utcnow()
        )
        if reason:
            embed.add_field(name="📝 Sebep", value=reason, inline=False)
        embed.add_field(name="🔓 Kilidi Açmak İçin", value="`!kilidiaç` veya `!unlock` komutunu kullanabilirsiniz.", inline=False)
        embed.set_footer(text=f"Yetkili: {ctx.author.display_name}")
        await target.send(embed=embed)
        if target.id != ctx.channel.id:
            await ctx.send(f"✅ {target.mention} kanalı başarıyla kilitlendi.")
    except Exception as e:
        await ctx.send(f"❌ Kanal kilitlenirken hata oluştu: {e}")

@bot.command(name="kilidiac", aliases=["unlock", "kilidiaç", "kilitac", "kilit-ac", "kanalkilidiac", "kanalkilidiaç"])
async def cmd_unlock(ctx, channel: Optional[discord.TextChannel] = None):
    """!kilidiaç [#kanal] - Kanalın kilidini açar, üyeler yeniden mesaj yazabilir"""
    if not can_manage_channels(ctx.author):
        return await ctx.send("❌ Bu komutu kullanmak için Kanalları Yönet veya Yönetici yetkiniz olmalıdır!")

    target = channel or ctx.channel
    try:
        current_overwrite = target.overwrites_for(ctx.guild.default_role)
        current_overwrite.send_messages = None
        current_overwrite.send_messages_in_threads = None
        current_overwrite.create_public_threads = None
        current_overwrite.create_private_threads = None
        current_overwrite.add_reactions = None
        await target.set_permissions(ctx.guild.default_role, overwrite=current_overwrite, reason=f"Kanal kilidi {ctx.author} tarafından açıldı")

        embed = discord.Embed(
            title="🔓 Kanal Kilidi Açıldı!",
            description=(
                f"**Kanal:** {target.mention} (`{target.name}`)\n"
                f"Bu kanalın kilidi {ctx.author.mention} tarafından başarıyla açıldı.\n"
                f"Artık üyeler bu kanala yeniden mesaj gönderebilir."
            ),
            color=0x10b981,
            timestamp=discord.utils.utcnow()
        )
        embed.set_footer(text=f"Yetkili: {ctx.author.display_name}")
        await target.send(embed=embed)
        if target.id != ctx.channel.id:
            await ctx.send(f"✅ {target.mention} kanalının kilidi başarıyla açıldı.")
    except Exception as e:
        await ctx.send(f"❌ Kanal kilidi açılırken hata oluştu: {e}")

@bot.command(name="sicil", aliases=["ceza", "cezalar", "cezagecmisi"])
async def cmd_sicil(ctx, member: Optional[discord.Member] = None):
    """!sicil [@üye] - Kullanıcının ceza ve uyarı geçmişini görüntüler"""
    target = member or ctx.author
    db = load_db()
    user_id_str = str(target.id)
    user_warns = db.get("warns", {}).get(user_id_str, [])

    embed = discord.Embed(
        title=f"📜 {target.display_name} — Ceza & Sicil Dosyası",
        color=0xf59e0b if user_warns else 0x10b981,
        timestamp=discord.utils.utcnow()
    )
    embed.set_thumbnail(url=target.display_avatar.url)
    embed.add_field(name="👤 Kullanıcı", value=f"{target.mention} (`{target.id}`)", inline=True)
    embed.add_field(name="⚠️ Toplam Uyarı", value=f"**{len(user_warns)}** adet", inline=True)

    if has_immunity(target):
        embed.add_field(name="🛡️ Durum", value="**DOKUNULMAZ** (`1554266448036102255`)", inline=True)

    if not user_warns:
        embed.description = "✅ Bu kullanıcının veri tabanında hiçbir aktif ceza veya uyarısı bulunmamaktadır. Sicili tertemiz!"
    else:
        lines = []
        for idx, w in enumerate(user_warns[-5:], 1):
            ts = int(w.get('timestamp', time.time()))
            lines.append(f"**{idx}.** Yetkili: <@{w.get('moderator_id', 'Bilinmiyor')}> | Sebep: `{w.get('reason', 'Sebep yok')}` | Tarih: <t:{ts}:R>")
        embed.add_field(name="Son Uyarılar", value="\n".join(lines), inline=False)

    embed.set_footer(text=f"Sorgulayan: {ctx.author.display_name}")
    await ctx.send(embed=embed)

@bot.command(name="kanaligizle", aliases=["kanaligizlet", "hidechannel", "gizle"])
async def cmd_kanaligizle(ctx, channel: Optional[discord.TextChannel] = None):
    """!kanaligizle [#kanal] - Kanalı adi üzvlər (@everyone) üçün gizli edir (Yalnız adminlər)"""
    if not (ctx.author.guild_permissions.administrator or ctx.author.id == FOUNDER_ID or ctx.author.id == ctx.guild.owner_id):
        return await ctx.send("❌ Bu komutu yalnızca sunucu yöneticileri kullanabilir!")

    target = channel or ctx.channel
    try:
        current_overwrite = target.overwrites_for(ctx.guild.default_role)
        current_overwrite.view_channel = False
        await target.set_permissions(ctx.guild.default_role, overwrite=current_overwrite, reason=f"Kanal {ctx.author} tarafından gizlendi")

        embed = discord.Embed(
            title="🔒 Kanal Gizlendi!",
            description=(
                f"**Kanal:** {target.mention} (`{target.name}`)\n"
                f"Bu kanal {ctx.author.mention} tərəfindən **gizli (özəl)** edildi.\n"
                f"Artıq adi üzvlər (`@everyone`) bu kanalı görə bilməz."
            ),
            color=0xef4444,
            timestamp=discord.utils.utcnow()
        )
        embed.set_footer(text=f"Uygulayan: {ctx.author.display_name}")
        await ctx.send(embed=embed)
    except Exception as e:
        await ctx.send(f"❌ Kanal gizlenirken hata oluştu: {e}")

@bot.command(name="kanaliac", aliases=["kanalac", "unhidechannel", "showchannel"])
async def cmd_kanaliac(ctx, channel: Optional[discord.TextChannel] = None):
    """!kanaliac [#kanal] - Kanalı hər kəs (@everyone) üçün yenidən görünən edir (Yalnız adminlər)"""
    if not (ctx.author.guild_permissions.administrator or ctx.author.id == FOUNDER_ID or ctx.author.id == ctx.guild.owner_id):
        return await ctx.send("❌ Bu komutu yalnızca sunucu yöneticileri kullanabilir!")

    target = channel or ctx.channel
    try:
        current_overwrite = target.overwrites_for(ctx.guild.default_role)
        current_overwrite.view_channel = True
        await target.set_permissions(ctx.guild.default_role, overwrite=current_overwrite, reason=f"Kanal {ctx.author} tarafından herkese açıldı")

        embed = discord.Embed(
            title="🌐 Kanal Görünür Yapıldı!",
            description=(
                f"**Kanal:** {target.mention} (`{target.name}`)\n"
                f"Bu kanal {ctx.author.mention} tərəfindən yenidən **açıq (ictimai)** edildi.\n"
                f"Artıq hər kəs (`@everyone`) bu kanalı görə bilər."
            ),
            color=0x10b981,
            timestamp=discord.utils.utcnow()
        )
        embed.set_footer(text=f"Uygulayan: {ctx.author.display_name}")
        await ctx.send(embed=embed)
    except Exception as e:
        await ctx.send(f"❌ Kanal açılırken hata oluştu: {e}")

@bot.command(name="syncproof", aliases=["proofsync", "subutkanali", "subutayarla"])
async def cmd_syncproof(ctx):
    """a!syncproof - Sübut kanalını (1541541519578628117) bütün ban/kick/mute yetkili rollarına açır və icazələri tənzimləyir"""
    if not (ctx.author.guild_permissions.administrator or ctx.author.id == FOUNDER_ID or ctx.author.id == ctx.guild.owner_id):
        return await ctx.send("❌ Bu komutu yalnızca Sunucu Kurucusu veya Yöneticiler kullanabilir!")

    msg = await ctx.send(f"⏳ Kanıt kanalı (<#{PROOF_LOG_CHANNEL_ID}>) izinleri kontrol ediliyor ve senkronize ediliyor...")
    roles = await sync_proof_channel_permissions(ctx.guild)
    role_mentions = ", ".join([r.mention for r in roles[:20]]) if roles else "Hiçbir rol bulunamadı"
    await msg.edit(content=(
        f"✅ Kanıt kanalı (<#{PROOF_LOG_CHANNEL_ID}>) izinleri başarıyla senkronize edildi!\n"
        f"🔒 **@everyone:** Kanala erişim kapatıldı (Gizli)\n"
        f"👥 **Erişim ve Mesaj İzni Verilen Yetkili Rolleri ({len(roles)}):**\n{role_mentions}"
    ))

# =============================================================================
# 5. SNIPE & EDITSNIPE SİSTEMİ
# =============================================================================
@bot.command(name="snipe")
async def cmd_snipe(ctx):
    """a!snipe - Bu kanalda ən son silinən mesajı göstərir"""
    data = last_deleted_message.get(ctx.channel.id)
    if not data:
        return await ctx.send("❌ Bu kanalda silinen mesaj bulunamadı!")

    embed = discord.Embed(
        title="🎯 Son Silinen Mesaj",
        description=data["content"] or "*[Metin yok - dosya veya embed]*",
        color=0xf97316,
        timestamp=data["time"]
    )
    embed.set_author(name=f"{data['author'].display_name} ({data['author']})", icon_url=data['author'].display_avatar.url)
    if data.get("attachments"):
        embed.add_field(name="Fayllar", value="\n".join(data["attachments"]), inline=False)
    embed.set_footer(text="Silinme zamanı")
    await ctx.send(embed=embed)

@bot.command(name="editsnipe")
async def cmd_editsnipe(ctx):
    """a!editsnipe - Bu kanalda ən son redaktə olunan mesajı göstərir"""
    data = last_edited_message.get(ctx.channel.id)
    if not data:
        return await ctx.send("❌ Bu kanalda düzenlenen mesaj bulunamadı!")

    embed = discord.Embed(
        title="✏️ Son Düzenlenen Mesaj",
        color=0x3b82f6,
        timestamp=data["time"]
    )
    embed.set_author(name=f"{data['author'].display_name} ({data['author']})", icon_url=data['author'].display_avatar.url)
    embed.add_field(name="Önceki Metin", value=data["before"][:1000] or "Boş", inline=False)
    embed.add_field(name="Yeni Metin", value=data["after"][:1000] or "Boş", inline=False)
    await ctx.send(embed=embed)

# =============================================================================
# 6. STATBOT SİSTEMİ & SERVER MƏLUMAT KOMANDALARI
# =============================================================================
@bot.command(name="stat", aliases=["stats", "profilestat", "istatistik"])
async def cmd_stat(ctx, member: Optional[discord.Member] = None):
    """a!stat [@user] - İstifadəçinin Statbot tipli modern dark aktivlik kartını və ətraflı göstəricilərini göstərir"""
    target = member or ctx.author
    if target.bot:
        return await ctx.send("❌ Botlar için aktivite istatistiği tutulmamaktadır.")

    async with ctx.typing():
        data = get_user_stat_data(ctx.guild, target)
        img_buffer = await generate_stat_card_image(ctx.guild, target, data)

        file = discord.File(fp=img_buffer, filename=f"stat_{target.id}.png")

        created_str = discord.utils.format_dt(target.created_at, "D")
        created_rel = discord.utils.format_dt(target.created_at, "R")
        joined_str = discord.utils.format_dt(target.joined_at, "D") if target.joined_at else "Bilinmiyor"
        joined_rel = f"({discord.utils.format_dt(target.joined_at, 'R')})" if target.joined_at else ""

        embed = discord.Embed(
            title=f"📊 {target.display_name} — Sunucu İstatistikleri",
            description=(
                f"👤 **İstifadəçi:** {target.mention} (`{target.id}`)\n"
                f"📅 **Hesap Açılış:** {created_str} ({created_rel})\n"
                f"📥 **Sunucuya Katılış:** {joined_str} {joined_rel}"
            ),
            color=0x5865F2,
            timestamp=discord.utils.utcnow()
        )
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.set_image(url=f"attachment://stat_{target.id}.png")

        embed.add_field(
            name="💬 Messages",
            value=(
                f"• **1d:** `{data['msg_1d']}` messages\n"
                f"• **7d:** `{data['msg_7d']}` messages\n"
                f"• **14d:** `{data['msg_14d']}` messages"
            ),
            inline=True
        )

        embed.add_field(
            name="🎙️ Voice Activity",
            value=(
                f"• **1d:** `{format_duration(data['voice_1d_sec'])}`\n"
                f"• **7d:** `{format_duration(data['voice_7d_sec'])}`\n"
                f"• **14d:** `{format_duration(data['voice_14d_sec'])}`"
            ),
            inline=True
        )

        embed.add_field(
            name="🏆 Server Ranks",
            value=(
                f"• **Message Rank:** `#{data['msg_rank']}`\n"
                f"• **Voice Rank:** `#{data['voice_rank']}`\n"
                f"• **Aktif Üyeler:** `{data['total_active']}`"
            ),
            inline=True
        )

        if data['top_channels']:
            top_ch_text = "\n".join([f"• {ch} — `{cnt}` messages" for ch, cnt in data['top_channels']])
        else:
            top_ch_text = "*Bilgi yok*"
        embed.add_field(name="📍 En Çok Mesaj Gönderilen Kanallar (14d)", value=top_ch_text, inline=True)

        if data['top_voice_channels']:
            top_vch_text = "\n".join([f"• {vch} — `{format_duration(secs)}`" for vch, secs in data['top_voice_channels']])
        else:
            top_vch_text = "*Bilgi yok*"
        embed.add_field(name="🔊 En Çok Vakit Geçirilen Ses Kanalları (14d)", value=top_vch_text, inline=True)

        embed.set_footer(text="Statbot Pro • Sunucu Aktivite Takip Sistemi", icon_url=ctx.guild.icon.url if ctx.guild.icon else None)
        await ctx.send(file=file, embed=embed)

@bot.command(name="statboard", aliases=["leaderboard", "top", "siralamasi", "statlar"])
async def cmd_statboard(ctx):
    """a!statboard - Serverin ümumi statistika liderlik cədvəlini (1d / 7d / 14d) göstərir"""
    view = StatboardView(period_days=14)
    embed = build_statboard_embed(ctx.guild, 14)
    await ctx.send(embed=embed, view=view)

@bot.command(name="userinfo", aliases=["ui", "whois"])
async def cmd_userinfo(ctx, member: Optional[discord.Member] = None):
    """a!userinfo @user"""
    target = member or ctx.author
    roles = [r.mention for r in target.roles[1:]] or ["Yoxdur"]

    embed = discord.Embed(title=f"👤 Kullanıcı Bilgisi: {target.display_name}", color=target.color)
    embed.set_thumbnail(url=target.display_avatar.url)
    embed.add_field(name="Kullanıcı Adı", value=f"`{target}`", inline=True)
    embed.add_field(name="Kullanıcı ID", value=f"`{target.id}`", inline=True)
    embed.add_field(name="Bot mu?", value="Evet 🤖" if target.bot else "Hayır 👤", inline=True)
    embed.add_field(name="Hesap Oluşturulma", value=discord.utils.format_dt(target.created_at, "F"), inline=False)
    embed.add_field(name="Sunucuya Katılma", value=discord.utils.format_dt(target.joined_at, "F"), inline=False)
    embed.add_field(name=f"Rollar ({len(target.roles) - 1})", value=", ".join(roles[:15]), inline=False)
    embed.set_footer(text=f"Sorgulayan: {ctx.author.display_name}")
    await ctx.send(embed=embed)

@bot.command(name="serverinfo", aliases=["si"])
async def cmd_serverinfo(ctx):
    """a!serverinfo"""
    g = ctx.guild
    text_count = len(g.text_channels)
    voice_count = len(g.voice_channels)
    category_count = len(g.categories)
    member_count = g.member_count
    humans = len([m for m in g.members if not m.bot])
    bots = len([m for m in g.members if m.bot])

    embed = discord.Embed(title=f"🏰 Sunucu İstatistikleri: {g.name}", color=0x6366f1)
    if g.icon:
        embed.set_thumbnail(url=g.icon.url)
    embed.add_field(name="👑 Sunucu Sahibi", value=f"{g.owner.mention if g.owner else 'Bilinmiyor'}", inline=True)
    embed.add_field(name="🆔 Sunucu ID", value=f"`{g.id}`", inline=True)
    embed.add_field(name="📅 Kuruluş Tarihi", value=discord.utils.format_dt(g.created_at, "D"), inline=True)
    embed.add_field(name="👥 Üyeler", value=f"Toplam: **{member_count}**\nİnsan: **{humans}** | Bot: **{bots}**", inline=True)
    embed.add_field(name="📁 Kanallar", value=f"Metin: **{text_count}**\nSes: **{voice_count}**\nKategori: **{category_count}**", inline=True)
    embed.add_field(name="🚀 Takviye (Boost)", value=f"Seviye: **{g.premium_tier}**\nBoost Sayısı: **{g.premium_subscription_count}**", inline=True)
    embed.add_field(name="🎭 Roller", value=f"**{len(g.roles)}** adet rol", inline=True)
    await ctx.send(embed=embed)

@bot.command(name="avatar", aliases=["av"])
async def cmd_avatar(ctx, member: Optional[discord.Member] = None):
    """a!avatar @user"""
    target = member or ctx.author
    embed = discord.Embed(title=f"🖼️ {target.display_name} Avatarı", color=0x3b82f6)
    embed.set_image(url=target.display_avatar.url)
    embed.add_field(name="🔗 Birbaşa Link", value=f"[Buradan İndir]({target.display_avatar.url})")
    await ctx.send(embed=embed)

@bot.command(name="banner")
async def cmd_banner(ctx, member: Optional[discord.Member] = None):
    """a!banner @user"""
    target = member or ctx.author
    user = await bot.fetch_user(target.id)
    if user.banner:
        embed = discord.Embed(title=f"🎨 {user.display_name} Banneri", color=0x8b5cf6)
        embed.set_image(url=user.banner.url)
        await ctx.send(embed=embed)
    else:
        await ctx.send(f"❌ **{user.display_name}** kullanıcısının afişi (banner) bulunmuyor.")

@bot.command(name="roles")
async def cmd_roles(ctx):
    """a!roles"""
    roles = [f"{r.mention} (`{len(r.members)}` üzv)" for r in reversed(ctx.guild.roles[1:])]
    if not roles:
        return await ctx.send("Sunucuda rol bulunamadı.")
    embed = discord.Embed(title=f"🎭 Sunucu Rolleri ({len(roles)})", color=0xec4899)
    embed.description = "\n".join(roles[:30])
    await ctx.send(embed=embed)

@bot.command(name="ping")
async def cmd_ping(ctx):
    """a!ping"""
    latency = round(bot.latency * 1000)
    await ctx.send(f"🏓 Pong! Gecikme: **{latency}ms**")

@bot.command(name="botinfo")
async def cmd_botinfo(ctx):
    """a!botinfo"""
    delta = datetime.datetime.now(datetime.timezone.utc) - BOT_START_TIME
    hours, remainder = divmod(int(delta.total_seconds()), 3600)
    minutes, seconds = divmod(remainder, 60)
    uptime_str = f"{hours} saat {minutes} dakika {seconds} saniye"

    embed = discord.Embed(title="🤖 Bot Məlumatı & Statistika", color=0x10b981)
    embed.add_field(name="👑 Kurucu", value=f"<@{FOUNDER_ID}>", inline=True)
    embed.add_field(name="📶 Ping", value=f"`{round(bot.latency * 1000)}ms`", inline=True)
    embed.add_field(name="⏱️ Uptime", value=f"`{uptime_str}`", inline=True)
    embed.add_field(name="🏰 Serverlər", value=f"`{len(bot.guilds)}` server", inline=True)
    embed.add_field(name="👥 Üyeler", value=f"`{sum(g.member_count for g in bot.guilds)}` kullanıcı", inline=True)
    embed.add_field(name="🐍 Kitabxana", value="`discord.py 2.4+ (Python 3.10+)`", inline=True)
    await ctx.send(embed=embed)

# =============================================================================
# 7. UTILITY, GİVEAWAY, POLL VƏ ALƏTLƏR
# =============================================================================
@bot.command(name="poll", aliases=["anket", "oylama", "survey"])
async def cmd_poll(ctx, *, args: str):
    """!poll / !anket Soru | Seçenek 1 | Seçenek 2 | ..."""
    parts = [p.strip() for p in args.split("|")]
    if len(parts) < 3:
        return await ctx.send("❌ Format: `!anket Sorunuz | Seçenek 1 | Seçenek 2 [| Seçenek 3...]`")

    question = parts[0]
    options = parts[1:]
    if len(options) > 10:
        return await ctx.send("❌ En fazla 10 seçenek belirleyebilirsiniz!")

    emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    desc = []
    for idx, opt in enumerate(options):
        desc.append(f"{emojis[idx]} **{opt}**")

    embed = discord.Embed(title=f"📊 Oylama: {question}", description="\n\n".join(desc), color=0x06b6d4)
    embed.set_footer(text=f"Başlatan: {ctx.author.display_name}")
    poll_msg = await ctx.send(embed=embed)

    for idx in range(len(options)):
        await poll_msg.add_reaction(emojis[idx])

@bot.command(name="announce", aliases=["duyuru", "duyuruyap", "anons"])
@commands.has_permissions(manage_messages=True)
async def cmd_announce(ctx, channel: discord.TextChannel, *, announcement: str):
    """!duyuru #kanal metin - Belirtilen kanala resmi duyuru gönderir"""
    embed = discord.Embed(title="📢 RESMİ DUYURU", description=announcement, color=0xf59e0b, timestamp=discord.utils.utcnow())
    embed.set_footer(text=f"Duyuran: {ctx.author.display_name}", icon_url=ctx.author.display_avatar.url if ctx.author.display_avatar else None)
    await channel.send(embed=embed)
    await ctx.send(f"✅ Duyuru başarıyla {channel.mention} kanalına gönderildi.")

@bot.command(name="giveaway", aliases=["cekilis", "çekiliş", "cekilisbaslat"])
@commands.has_permissions(manage_guild=True)
async def cmd_giveaway(ctx, duration_str: str, *, prize: str):
    """!cekilis 10m Discord Nitro - Çekiliş başlatır"""
    unit = duration_str[-1].lower()
    try:
        val = int(duration_str[:-1])
    except ValueError:
        return await ctx.send("❌ Süre formatı hatalı! Örnek: `!çekiliş 10m Discord Nitro` veya `1h`, `30s`")

    seconds = val * (60 if unit == "m" else 3600 if unit == "h" else 1)
    end_time = discord.utils.utcnow() + datetime.timedelta(seconds=seconds)

    embed = discord.Embed(
        title="🎉 ÇEKİLİŞ BAŞLADI!",
        description=f"🎁 **Ödül:** {prize}\n⏰ **Bitiş:** {discord.utils.format_dt(end_time, 'R')}\n🎉 Katılmak için aşağıdaki **🎉** emojisine tıklayın!",
        color=0xa855f7
    )
    embed.set_footer(text=f"Düzenleyen: {ctx.author.display_name}")
    msg = await ctx.send(embed=embed)
    await msg.add_reaction("🎉")

    await asyncio.sleep(seconds)

    new_msg = await ctx.channel.fetch_message(msg.id)
    reaction = discord.utils.get(new_msg.reactions, emoji="🎉")
    users = [u async for u in reaction.users() if not u.bot] if reaction else []

    if users:
        winner = random.choice(users)
        win_embed = discord.Embed(
            title="🎉 ÇEKİLİŞ KAZANANI!",
            description=f"Tebrikler {winner.mention}! **{prize}** kazandınız! 🎁",
            color=0x10b981
        )
        await ctx.send(content=winner.mention, embed=win_embed)
    else:
        await ctx.send("❌ Kimse katılmadığı için kazanan belirlenemedi!")

@bot.command(name="reminder", aliases=["remind", "hatirlat", "hatırlat", "alarm"])
async def cmd_reminder(ctx, duration_str: str, *, reminder_text: str):
    """!hatirlat 10m Görev - Süreli hatırlatıcı kurar"""
    unit = duration_str[-1].lower()
    try:
        val = int(duration_str[:-1])
    except ValueError:
        return await ctx.send("❌ Süre formatı hatalı! Örnek: `!hatırlat 15m Toplantı`")

    seconds = val * (60 if unit == "m" else 3600 if unit == "h" else 1)
    await ctx.send(f"⏰ {ctx.author.mention}, hatırlatıcı kuruldu! **{duration_str}** sonra hatırlatacağım.")
    await asyncio.sleep(seconds)
    await ctx.send(f"🔔 {ctx.author.mention}, Süre doldu! **Hatırlatma:** {reminder_text}")

@bot.command(name="hesabla", aliases=["calc"])
async def cmd_hesabla(ctx, *, expression: str):
    """a!hesabla 5 * 10 + 2"""
    allowed_chars = "0123456789+-*/(). "
    if not all(c in allowed_chars for c in expression):
        return await ctx.send("❌ Yalnız əsas riyazi simvollardan istifadə edə bilərsiniz (+ - * /)!")
    try:
        result = eval(expression, {"__builtins__": None}, {})
        await ctx.send(f"🧮 **Hesablama:** `{expression}` = **{result}**")
    except Exception:
        await ctx.send("❌ Riyazi ifadə düzgün deyil!")

@bot.command(name="qr")
async def cmd_qr(ctx, *, text_or_url: str):
    """a!qr https://example.com"""
    encoded = urllib.parse.quote(text_or_url)
    qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={encoded}"
    embed = discord.Embed(title="📱 QR Kod Hazırdır!", color=0x3b82f6)
    embed.set_image(url=qr_url)
    embed.set_footer(text=f"Mətn/Link: {text_or_url[:50]}")
    await ctx.send(embed=embed)

# =============================================================================
# 8. ƏYLƏNCƏ KOMANDALARI
# =============================================================================
@bot.command(name="ship")
async def cmd_ship(ctx, user1: discord.Member, user2: Optional[discord.Member] = None):
    """a!ship @user1 [@user2]"""
    target1 = ctx.author if user2 is None else user1
    target2 = user1 if user2 is None else user2

    seed = (target1.id + target2.id) % 101
    filled = int(seed / 10)
    bar = "█" * filled + "░" * (10 - filled)

    if seed >= 85:
        verdict = "💍 Bir-biriniz üçün yaranmısınız! Toy nə vaxtdır? ❤️"
    elif seed >= 50:
        verdict = "💕 Olduqca gözəl bir cütlük ola bilərsiniz!"
    elif seed >= 25:
        verdict = "💔 Yalnız dost qalsanız daha yaxşı olar..."
    else:
        verdict = "💀 Qətiyyən uzaq durun, fəlakət olar!"

    embed = discord.Embed(title="💘 Sevgi / Ship Testi", color=0xec4899)
    embed.description = (
        f"**{target1.display_name}** ❤️ **{target2.display_name}**\n\n"
        f"**Nəticə:** `{seed}%`\n"
        f"`[{bar}]`\n\n"
        f"**Rəy:** {verdict}"
    )
    await ctx.send(embed=embed)

@bot.command(name="8ball")
async def cmd_8ball(ctx, *, question: str):
    """a!8ball Sual"""
    responses = [
        "Bəli, tamamilə əminəm! 🟢",
        "Şübhəsiz ki elədir! 🟢",
        "Böyük ehtimalla bəli. 🟢",
        "İşarələr bəlini göstərir. 🟢",
        "Sonra bir daha soruş, indi aydın deyil. 🟡",
        "İndi bunu deməsəm daha yaxşı olar. 🟡",
        "Məncə yox. 🔴",
        "Heç xəyal belə qurma! 🔴",
        "Ulduzlar xeyr deyir! 🔴"
    ]
    answer = random.choice(responses)
    embed = discord.Embed(title="🎱 Sehrli 8-Ball", color=0x6366f1)
    embed.add_field(name="Sualınız", value=question, inline=False)
    embed.add_field(name="Cavab", value=answer, inline=False)
    await ctx.send(embed=embed)

@bot.command(name="coinflip", aliases=["yazitura"])
async def cmd_coinflip(ctx):
    """a!coinflip"""
    result = random.choice(["🪙 YAZI!", "🪙 ŞƏKİL!"])
    await ctx.send(f"🎲 {ctx.author.mention}, qəpik fırlandı və gəldi: **{result}**")

@bot.command(name="slap")
async def cmd_slap(ctx, member: discord.Member):
    """a!slap @user"""
    await ctx.send(f"🖐️ {ctx.author.mention}, **{member.display_name}** adlı üzvə bərk bir şillə vurdu! 💥")

@bot.command(name="hug")
async def cmd_hug(ctx, member: discord.Member):
    """a!hug @user"""
    await ctx.send(f"🤗 {ctx.author.mention}, **{member.display_name}** adlı üzvü səmimi şəkildə qucaqladı! ❤️")

@bot.command(name="kiss")
async def cmd_kiss(ctx, member: discord.Member):
    """a!kiss @user"""
    await ctx.send(f"💋 {ctx.author.mention}, **{member.display_name}** adlı üzvü yanağından öpdü! 😘")

@bot.command(name="meme")
async def cmd_meme(ctx):
    """a!meme"""
    memes = [
        "Müəllim: 'Kod niyə işləmir?'\nMən: 'Müəllim, kompüterimdə işləyirdi!' 😂",
        "Yazılımcı 1: 'Bir hatayı düzelttim.'\nYazılımcı 2: 'Harika, artık 17 yeni hatamız var!' 💀",
        "CSS ilə element mərkəzləşdirməyə çalışanda bütün kainat sıradan çıxır. 🛸",
        "Saat 03:00-da: 'Sadəcə 1 sətir kod yazıb yatıram.'\nSaat 07:00-da: 'Kompüter niyə tüstüləyir?' ☕"
    ]
    await ctx.send(f"🤣 **Günün Zarafatı:**\n>>> {random.choice(memes)}")

# =============================================================================
# 9. TİCKET SİSTEMİ (a!setupticket, a!add, a!remove, a!rename)
# =============================================================================
class TicketCloseView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="Talebi Kapat", style=discord.ButtonStyle.danger, emoji="🔒", custom_id="btn_ticket_close_persistent")
    async def close_ticket(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_message("🔒 Talep 3 saniye içinde kapatılıyor...", ephemeral=False)
        await asyncio.sleep(3)
        await interaction.channel.delete(reason=f"Ticket closed by {interaction.user}")

class TicketLauncherView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="Destek Talebi Aç", style=discord.ButtonStyle.primary, emoji="🎫", custom_id="btn_create_ticket_persistent")
    async def create_ticket(self, interaction: discord.Interaction, button: ui.Button):
        guild = interaction.guild
        conf = get_config()
        cat_id = conf.get("ticket_category_id", LOGS_CATEGORY_ID)
        category = guild.get_channel(cat_id)

        existing = discord.utils.get(guild.text_channels, name=f"ticket-{interaction.user.name.lower()}")
        if existing:
            return await interaction.response.send_message(f"⚠️ Zaten aktif bir destek talebiniz bulunuyor: {existing.mention}", ephemeral=True)

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True)
        }

        channel = await guild.create_text_channel(
            name=f"ticket-{interaction.user.name}",
            category=category,
            overwrites=overwrites,
            topic=f"Müəllif: {interaction.user.id}"
        )

        embed = discord.Embed(
            title="🎫 Destek Talebi",
            description=f"Merhaba {interaction.user.mention}! Talebinizi detaylıca belirtin, yetkili ekip en kısa sürede ilgilenecektir.",
            color=0x5865F2
        )
        await channel.send(content=f"{interaction.user.mention}", embed=embed, view=TicketCloseView())
        await interaction.response.send_message(f"✅ Destek talebiniz oluşturuldu: {channel.mention}", ephemeral=True)

@bot.command(name="setupticket")
@commands.has_permissions(administrator=True)
async def cmd_setupticket(ctx):
    """a!setupticket"""
    embed = discord.Embed(
        title="🎫 Destek Sistemi",
        description="Yardım, şikayet veya öneri iletmek için aşağıdaki butona tıklayarak bilet açabilirsiniz.",
        color=0x5865F2
    )
    embed.set_footer(text="Talebiniz size özel kanalda açılacaktır.")
    await ctx.send(embed=embed, view=TicketLauncherView())
    await ctx.message.delete()

@bot.command(name="add")
@commands.has_permissions(manage_channels=True)
async def cmd_add(ctx, member: discord.Member):
    """a!add @user"""
    if not ctx.channel.name.startswith("ticket-"):
        return await ctx.send("❌ Bu komut yalnızca destek talebi kanallarında kullanılabilir!")
    await ctx.channel.set_permissions(member, view_channel=True, send_messages=True, attach_files=True)
    await ctx.send(f"✅ {member.mention} başarıyla bu talebe eklendi.")

@bot.command(name="remove")
@commands.has_permissions(manage_channels=True)
async def cmd_remove(ctx, member: discord.Member):
    """a!remove @user"""
    if not ctx.channel.name.startswith("ticket-"):
        return await ctx.send("❌ Bu komut yalnızca destek talebi kanallarında kullanılabilir!")
    await ctx.channel.set_permissions(member, overwrite=None)
    await ctx.send(f"✅ {member.mention} talepten çıkarıldı.")

@bot.command(name="rename")
@commands.has_permissions(manage_channels=True)
async def cmd_rename(ctx, *, new_name: str):
    """a!rename ad"""
    if not ctx.channel.name.startswith("ticket-"):
        return await ctx.send("❌ Bu komut yalnızca destek talebi kanallarında kullanılabilir!")
    await ctx.channel.edit(name=new_name)
    await ctx.send(f"🏷️ Talep adı değiştirildi: `{new_name}`")

# =============================================================================
# 10. KÖMƏK MENYUSU (a!help)
# =============================================================================
@bot.command(name="help", aliases=["yardim", "komutlar", "komandalar"])
async def cmd_help(ctx):
    """!help / !yardım - Tüm komutların detaylı listesi"""
    embed = discord.Embed(
        title="🤖 Discord Bot Komut Listesi",
        description="Bot ön ekleri: **`!`** ve **`a!`**\nHatalı komut yazıldığında bot otomatik olarak en yakın doğru komutu önerir!",
        color=0x6366f1
    )
    embed.add_field(
        name="⚙️ Kurucu Yönetim Paneli",
        value=f"`a!config` — Yalnızca Sunucu Kurucusu (<@{FOUNDER_ID}>) için interaktif kontrol paneli!",
        inline=False
    )
    embed.add_field(
        name="🛡️ Moderasyon & Kanal Yönetimi",
        value=(
            "`!kilitle [#kanal] [sebep]` — Yetkisiz üyelerin kanala yazmasını engeller (Kanalı kilitler)\n"
            "`!kilidiaç [#kanal]` — Kilitlenen kanalın kilidini açar\n"
            "`!restart` (veya `!nuke`) — Kanalı klonlayarak tüm eski mesajları anında siler ve tertemiz başlatır\n"
            "`!sil [sayı]` — Belirtilen sayıda mesajı siler (Örn: `!sil 50`)\n"
            "`!slowmode / !yavaşmod [süre]` — Kanal yavaş modunu ayarlar (Örn: `!yavaşmod 5s` veya `!yavaşmod kapat`)\n"
            "`!kanaligizle` & `!kanaliac` — Kanalı @everyone için gizler veya tekrar görünür yapar\n"
            "`a!delete [#kanal]` & `a!deletepanel` — İnteraktif kanal silme onay paneli\n"
            "`!ban`, `!kick`, `!timeout` / `!mute`, `!untimeout` / `!unmute`\n"
            "`!warn @üye [sebep]`, `!warns [@üye]`, `!unwarn @üye` (Otomatik kanıt sistemi: <#{PROOF_LOG_CHANNEL_ID}>)\n"
            "`!sicil [@üye]` — Kullanıcının aktif uyarı ve sicil kaydını gösterir\n"
            "`!rolver @üye @rol` & `!rolal @üye @rol` — Hızlı ve güvenli rol verme/alma\n"
            "`!nick @üye [yeni_ad]` — Kullanıcı takma adını değiştirir"
        ),
        inline=False
    )
    embed.add_field(
        name="📊 Sunucu İstatistikleri & Bilgi",
        value=(
            "`!sayım` / `!say` — Canlı toplam üye, seste olanlar, çevrimiçi, boost ve kanal sayım tablosu\n"
            "`a!stat [@üye]` — Statbot tarzı koyu tema görsel aktivite kartı (Mesaj/Ses sıralaması)\n"
            "`a!statboard` — Sunucu aktivite liderlik tablosu (1 Gün / 7 Gün / 14 Gün butonlu)\n"
            "`!userinfo [@üye]`, `!serverinfo`, `!avatar [@üye]`, `!banner [@üye]`, `!roles`, `!ping`, `!botinfo`"
        ),
        inline=False
    )
    embed.add_field(
        name="📢 Duyuru, Çekiliş & Araçlar",
        value=(
            "`!duyuru #kanal [metin]` — Belirtilen kanala resmi şık duyuru gönderir\n"
            "`!embed Başlık | İçerik | [Renk]` — Özel tasarımlı embed mesaj yayınlar\n"
            "`!çekiliş [süre] [ödül]` — Otomatik sayaçlı ve kazanan belirleyen çekiliş (Örn: `!çekiliş 10m Nitro`)\n"
            "`!anket Soru | Seçenek 1 | Seçenek 2` — Çoktan seçmeli anket ve oylama başlatır\n"
            "`!hatırlat [süre] [not]` — Zaman ayarlı hatırlatıcı kurar\n"
            "`!yaz [metin]` — Bot üzerinden mesaj yazdırır\n"
            "`!hesapla [işlem]` — Matematiksel hesaplama yapar\n"
            "`!qr [link/metin]` — Anında taranabilir QR kod oluşturur"
        ),
        inline=False
    )
    embed.add_field(
        name="🔍 Snipe & Bilet Sistemi",
        value=(
            "`!snipe` — Son silinen mesajı kurtarır ve gösterir\n"
            "`!editsnipe` — Son düzenlenen mesajın önceki ve sonraki halini gösterir\n"
            "`!setupticket` — Butonlu destek bilet paneli kurar\n"
            "`!add @üye`, `!remove @üye`, `!rename [yeni_ad]` — Bilet yönetim komutları"
        ),
        inline=False
    )
    embed.add_field(
        name="🎲 Eğlence & Topluluk",
        value="`!gay @üye` (Gökkuşağı avatar efekti), `!zar [1-10]`, `!afk [sebep]`, `!ship @üye`, `!8ball [soru]`, `!yazitura`, `!slap`, `!hug`, `!kiss`, `!meme`",
        inline=False
    )
    embed.add_field(
        name="🛡️ Güvenlik & 16 Log Kanalı",
        value=(
            f"• **Dokunulmazlık Rolü:** <@&{IMMUNITY_ROLE_ID}> rolüne sahip kişilere ceza uygulanamaz!\n"
            f"• **Rol Etiketleme Koruması:** Yalnızca yöneticiler ve izinli roller (<@&{ALLOWED_PING_ROLE_IDS[0]}>, <@&{ALLOWED_PING_ROLE_IDS[1]}>) rol etiketleyebilir.\n"
            "• **16 Özel Log Kanalı:** Ban, Kick, Timeout, Warn, Mesaj Silme/Düzenleme, Rol, Kanal, Sunucu, Ses, Güvenlik vb."
        ),
        inline=False
    )
    embed.set_footer(text="Akıllı Öneri: Örneğin !kilitlee veya !sayy yazdığınızda bot doğru komutu otomatik önerir!")
    await ctx.send(embed=embed)

# =============================================================================
# 11. 16 AYRILMIŞ LOG VƏ AUDİT SİSTEMİ
# =============================================================================

# --- BAN LOG ---
@bot.event
async def on_member_ban(guild: discord.Guild, user: discord.User):
    await asyncio.sleep(1)
    moderator = None
    reason = "No reason provided"
    try:
        async for entry in guild.audit_logs(limit=3, action=discord.AuditLogAction.ban):
            if entry.target.id == user.id:
                moderator = entry.user
                if entry.reason:
                    reason = entry.reason
                break
    except Exception:
        pass

    log_id = get_next_log_id("BAN")
    embed = discord.Embed(title="🔨 MEMBER BANNED", color=0xef4444, timestamp=discord.utils.utcnow())
    embed.add_field(name="Moderator", value=f"{moderator.mention if moderator else 'Unknown'} (`{moderator.id if moderator else 'N/A'}`)", inline=True)
    embed.add_field(name="User", value=f"{user.mention} (`{user.id}`)", inline=True)
    embed.add_field(name="Reason", value=f"`{reason}`", inline=False)
    embed.add_field(name="Server", value=guild.name, inline=True)
    embed.set_footer(text=f"Log ID: {log_id}")
    await send_log(guild, "ban", embed)

# --- UNBAN LOG ---
@bot.event
async def on_member_unban(guild: discord.Guild, user: discord.User):
    await asyncio.sleep(1)
    moderator = None
    try:
        async for entry in guild.audit_logs(limit=3, action=discord.AuditLogAction.unban):
            if entry.target.id == user.id:
                moderator = entry.user
                break
    except Exception:
        pass

    log_id = get_next_log_id("BAN")
    embed = discord.Embed(title="🔓 MEMBER UNBANNED", color=0x10b981, timestamp=discord.utils.utcnow())
    embed.add_field(name="Moderator", value=f"{moderator.mention if moderator else 'Unknown'} (`{moderator.id if moderator else 'N/A'}`)", inline=True)
    embed.add_field(name="User", value=f"{user.mention} (`{user.id}`)", inline=True)
    embed.set_footer(text=f"Log ID: {log_id}")
    await send_log(guild, "ban", embed)

# --- KICK LOG & MEMBER REMOVE ---
@bot.event
async def on_member_remove(member: discord.Member):
    guild = member.guild
    await asyncio.sleep(1)

    is_kick = False
    moderator = None
    reason = "No reason provided"
    try:
        async for entry in guild.audit_logs(limit=3, action=discord.AuditLogAction.kick):
            if entry.target.id == member.id and (discord.utils.utcnow() - entry.created_at).total_seconds() < 5:
                is_kick = True
                moderator = entry.user
                if entry.reason:
                    reason = entry.reason
                break
    except Exception:
        pass

    if is_kick:
        log_id = get_next_log_id("KICK")
        embed = discord.Embed(title="👢 MEMBER KICKED", color=0xf97316, timestamp=discord.utils.utcnow())
        embed.add_field(name="Moderator", value=f"{moderator.mention if moderator else 'Unknown'} (`{moderator.id if moderator else 'N/A'}`)", inline=True)
        embed.add_field(name="User", value=f"{member.mention} (`{member.id}`)", inline=True)
        embed.add_field(name="Reason", value=f"`{reason}`", inline=False)
        embed.set_footer(text=f"Log ID: {log_id}")
        await send_log(guild, "kick", embed)
    else:
        log_id = get_next_log_id("MEM")
        embed = discord.Embed(title="📤 MEMBER LEFT", color=0x64748b, timestamp=discord.utils.utcnow())
        embed.add_field(name="User", value=f"{member} (`{member.id}`)", inline=True)
        embed.set_footer(text=f"Log ID: {log_id}")
        await send_log(guild, "member", embed)

# --- TIMEOUT & UNTIMEOUT & NICKNAME & ROLE MEMBER UPDATE LOGS ---
@bot.event
async def on_member_update(before: discord.Member, after: discord.Member):
    guild = after.guild

    # 1. Timeout və Untimeout
    if before.timed_out_until != after.timed_out_until:
        await asyncio.sleep(1)
        moderator = None
        reason = "No reason provided"
        try:
            async for entry in guild.audit_logs(limit=3, action=discord.AuditLogAction.member_update):
                if entry.target.id == after.id:
                    moderator = entry.user
                    if entry.reason:
                        reason = entry.reason
                    break
        except Exception:
            pass

        if after.timed_out_until and after.timed_out_until > discord.utils.utcnow():
            log_id = get_next_log_id("TIMEOUT")
            delta = after.timed_out_until - discord.utils.utcnow()
            minutes = round(delta.total_seconds() / 60)
            embed = discord.Embed(title="⏱️ MEMBER TIMEOUT", color=0xeab308, timestamp=discord.utils.utcnow())
            embed.add_field(name="Moderator", value=f"{moderator.mention if moderator else 'Unknown'}", inline=True)
            embed.add_field(name="User", value=f"{after.mention} (`{after.id}`)", inline=True)
            embed.add_field(name="Süre", value=f"`{minutes} dakika`", inline=True)
            embed.add_field(name="Reason", value=f"`{reason}`", inline=False)
            embed.add_field(name="Ends", value=f"{discord.utils.format_dt(after.timed_out_until, 'R')}", inline=True)
            embed.set_footer(text=f"Log ID: {log_id}")
            await send_log(guild, "timeout", embed)
        else:
            log_id = get_next_log_id("UNTIMEOUT")
            embed = discord.Embed(title="🔓 MEMBER UNTIMEOUT", color=0x10b981, timestamp=discord.utils.utcnow())
            embed.add_field(name="Moderator", value=f"{moderator.mention if moderator else 'Unknown'}", inline=True)
            embed.add_field(name="User", value=f"{after.mention} (`{after.id}`)", inline=True)
            embed.set_footer(text=f"Log ID: {log_id}")
            await send_log(guild, "untimeout", embed)

    # 2. Nickname Dəyişikliyi
    if before.nick != after.nick:
        moderator = None
        try:
            async for entry in guild.audit_logs(limit=3, action=discord.AuditLogAction.member_update):
                if entry.target.id == after.id:
                    moderator = entry.user
                    break
        except Exception:
            pass

        log_id = get_next_log_id("NICK")
        embed = discord.Embed(title="🏷️ NICKNAME CHANGED", color=0x06b6d4, timestamp=discord.utils.utcnow())
        embed.add_field(name="User", value=f"{after.mention} (`{after.id}`)", inline=True)
        embed.add_field(name="Before", value=f"`{before.nick or before.name}`", inline=True)
        embed.add_field(name="After", value=f"`{after.nick or after.name}`", inline=True)
        embed.add_field(name="Changed by", value=f"{moderator.mention if moderator else 'Self'}", inline=False)
        embed.set_footer(text=f"Log ID: {log_id}")
        await send_log(guild, "nickname", embed)

    # 3. Rol Dəyişikliyi
    if before.roles != after.roles:
        added = [r for r in after.roles if r not in before.roles]
        removed = [r for r in before.roles if r not in after.roles]
        moderator = None
        try:
            async for entry in guild.audit_logs(limit=3, action=discord.AuditLogAction.member_role_update):
                if entry.target.id == after.id:
                    moderator = entry.user
                    break
        except Exception:
            pass

        log_id = get_next_log_id("ROLE")
        embed = discord.Embed(title="🎭 MEMBER ROLES UPDATED", color=0xec4899, timestamp=discord.utils.utcnow())
        embed.add_field(name="User", value=f"{after.mention} (`{after.id}`)", inline=True)
        embed.add_field(name="Moderator", value=f"{moderator.mention if moderator else 'Unknown'}", inline=True)
        if added:
            embed.add_field(name="➕ Added Roles", value=", ".join([r.mention for r in added]), inline=False)
        if removed:
            embed.add_field(name="➖ Removed Roles", value=", ".join([r.mention for r in removed]), inline=False)
        embed.set_footer(text=f"Log ID: {log_id}")
        await send_log(guild, "role", embed)

# --- MESSAGE DELETE LOG & SNIPE CACHE ---
@bot.event
async def on_message_delete(message: discord.Message):
    if message.author.bot or not message.guild:
        return

    last_deleted_message[message.channel.id] = {
        "author": message.author,
        "content": message.content,
        "attachments": [a.url for a in message.attachments],
        "time": discord.utils.utcnow()
    }

    deleter = "Unknown"
    try:
        async for entry in message.guild.audit_logs(limit=3, action=discord.AuditLogAction.message_delete):
            if entry.target.id == message.author.id and (discord.utils.utcnow() - entry.created_at).total_seconds() < 4:
                deleter = entry.user.mention
                break
    except Exception:
        pass

    log_id = get_next_log_id("MSG")
    embed = discord.Embed(title="🗑️ MESSAGE DELETED", color=0xf97316, timestamp=discord.utils.utcnow())
    embed.add_field(name="Author", value=f"{message.author.mention} (`{message.author.id}`)", inline=True)
    embed.add_field(name="Deleted by", value=f"{deleter}", inline=True)
    embed.add_field(name="Channel", value=message.channel.mention, inline=True)

    content = message.content or "[Mətn yoxdur - yalnız embed/fayl]"
    embed.add_field(name="Content", value=content[:1000], inline=False)

    if message.attachments:
        att_links = "\n".join([f"[{a.filename}]({a.url})" for a in message.attachments])
        embed.add_field(name="Attachments", value=att_links[:1000], inline=False)

    embed.set_footer(text=f"Message ID: {message.id} | Log ID: {log_id}")
    await send_log(message.guild, "message", embed)

# --- MESSAGE EDIT LOG & EDITSNIPE CACHE ---
@bot.event
async def on_message_edit(before: discord.Message, after: discord.Message):
    if before.author.bot or not before.guild or before.content == after.content:
        return

    last_edited_message[before.channel.id] = {
        "author": before.author,
        "before": before.content,
        "after": after.content,
        "time": discord.utils.utcnow()
    }

    log_id = get_next_log_id("MSG")
    embed = discord.Embed(title="✏️ MESSAGE EDITED", color=0x3b82f6, timestamp=discord.utils.utcnow())
    embed.add_field(name="User", value=f"{before.author.mention} (`{before.author.id}`)", inline=True)
    embed.add_field(name="Channel", value=before.channel.mention, inline=True)
    embed.add_field(name="Before", value=(before.content or "Boş")[:1000], inline=False)
    embed.add_field(name="After", value=(after.content or "Boş")[:1000], inline=False)
    embed.set_footer(text=f"Message ID: {after.id} | Log ID: {log_id}")
    await send_log(before.guild, "message", embed)

# --- ROLE CREATE / DELETE / UPDATE LOGS ---
@bot.event
async def on_guild_role_create(role: discord.Role):
    guild = role.guild
    moderator = None
    try:
        async for entry in guild.audit_logs(limit=3, action=discord.AuditLogAction.role_create):
            if entry.target.id == role.id:
                moderator = entry.user
                break
    except Exception:
        pass

    log_id = get_next_log_id("ROLE")
    embed = discord.Embed(title="🎭 ROLE CREATED", color=0x10b981, timestamp=discord.utils.utcnow())
    embed.add_field(name="Role", value=f"{role.name} (`{role.id}`)", inline=True)
    embed.add_field(name="Created by", value=f"{moderator.mention if moderator else 'Unknown'}", inline=True)
    embed.set_footer(text=f"Log ID: {log_id}")
    await send_log(guild, "role", embed)

@bot.event
async def on_guild_role_delete(role: discord.Role):
    guild = role.guild
    moderator = None
    try:
        async for entry in guild.audit_logs(limit=3, action=discord.AuditLogAction.role_delete):
            if entry.target.id == role.id:
                moderator = entry.user
                break
    except Exception:
        pass

    log_id = get_next_log_id("ROLE")
    embed = discord.Embed(title="🎭 ROLE DELETED", color=0xef4444, timestamp=discord.utils.utcnow())
    embed.add_field(name="Role Name", value=f"`{role.name}` (`{role.id}`)", inline=True)
    embed.add_field(name="Deleted by", value=f"{moderator.mention if moderator else 'Unknown'}", inline=True)
    embed.set_footer(text=f"Log ID: {log_id}")
    await send_log(guild, "role", embed)

@bot.event
async def on_guild_role_update(before: discord.Role, after: discord.Role):
    guild = after.guild
    moderator = None
    try:
        async for entry in guild.audit_logs(limit=3, action=discord.AuditLogAction.role_update):
            if entry.target.id == after.id:
                moderator = entry.user
                break
    except Exception:
        pass

    if before.permissions.administrator != after.permissions.administrator:
        sec_log_id = get_next_log_id("SEC")
        sec_embed = discord.Embed(title="🚨 ADMIN PERMISSION CHANGED", color=0xef4444, timestamp=discord.utils.utcnow())
        sec_embed.add_field(name="Changed by", value=f"{moderator.mention if moderator else 'Unknown'}", inline=True)
        sec_embed.add_field(name="Target Role", value=f"{after.mention} (`{after.id}`)", inline=True)
        sec_embed.add_field(name="Old Administrator", value=f"`{before.permissions.administrator}`", inline=True)
        sec_embed.add_field(name="New Administrator", value=f"`{after.permissions.administrator}`", inline=True)
        sec_embed.set_footer(text=f"Log ID: {sec_log_id}")
        await send_log(guild, "security", sec_embed)

    log_id = get_next_log_id("ROLE")
    embed = discord.Embed(title="🎭 ROLE UPDATED", color=0x3b82f6, timestamp=discord.utils.utcnow())
    embed.add_field(name="Role", value=f"{after.mention} (`{after.id}`)", inline=True)
    embed.add_field(name="Updated by", value=f"{moderator.mention if moderator else 'Unknown'}", inline=True)
    if before.name != after.name:
        embed.add_field(name="Name Change", value=f"`{before.name}` ➔ `{after.name}`", inline=False)
    if before.color != after.color:
        embed.add_field(name="Color Change", value=f"`{before.color}` ➔ `{after.color}`", inline=False)
    embed.set_footer(text=f"Log ID: {log_id}")
    await send_log(guild, "role", embed)

# --- CHANNEL CREATE / DELETE LOGS ---
@bot.event
async def on_guild_channel_create(channel: discord.abc.GuildChannel):
    guild = channel.guild
    moderator = None
    try:
        async for entry in guild.audit_logs(limit=3, action=discord.AuditLogAction.channel_create):
            if entry.target.id == channel.id:
                moderator = entry.user
                break
    except Exception:
        pass

    log_id = get_next_log_id("CHAN")
    embed = discord.Embed(title="📁 CHANNEL CREATED", color=0x10b981, timestamp=discord.utils.utcnow())
    embed.add_field(name="Channel", value=f"#{channel.name} (`{channel.id}`)", inline=True)
    embed.add_field(name="Type", value=f"`{str(channel.type).capitalize()}`", inline=True)
    embed.add_field(name="Created by", value=f"{moderator.mention if moderator else 'Unknown'}", inline=True)
    embed.set_footer(text=f"Log ID: {log_id}")
    await send_log(guild, "channel", embed)

@bot.event
async def on_guild_channel_delete(channel: discord.abc.GuildChannel):
    guild = channel.guild
    moderator = None
    try:
        async for entry in guild.audit_logs(limit=3, action=discord.AuditLogAction.channel_delete):
            if entry.target.id == channel.id:
                moderator = entry.user
                break
    except Exception:
        pass

    log_id = get_next_log_id("CHAN")
    embed = discord.Embed(title="📁 CHANNEL DELETED", color=0xef4444, timestamp=discord.utils.utcnow())
    embed.add_field(name="Channel Name", value=f"`{channel.name}` (`{channel.id}`)", inline=True)
    embed.add_field(name="Deleted by", value=f"{moderator.mention if moderator else 'Unknown'}", inline=True)
    embed.set_footer(text=f"Log ID: {log_id}")
    await send_log(guild, "channel", embed)

# --- VOICE STATE LOGS & STAT TRACKING ---
@bot.event
async def on_voice_state_update(member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
    guild = member.guild
    if not guild:
        return

    # Statbot: Track real-time voice activity (exclude bots)
    if not member.bot:
        try:
            track_voice_state_update(guild.id, member.id, before.channel, after.channel)
        except Exception as e:
            print(f"Stat voice tracking error: {e}")

    embed = None
    log_id = get_next_log_id("VOICE")

    if before.channel is None and after.channel is not None:
        embed = discord.Embed(title="🔊 VOICE JOIN", color=0x10b981, timestamp=discord.utils.utcnow())
        embed.add_field(name="User", value=f"{member.mention} (`{member.id}`)", inline=True)
        embed.add_field(name="Channel", value=f"`{after.channel.name}`", inline=True)
    elif before.channel is not None and after.channel is None:
        embed = discord.Embed(title="🔇 VOICE LEAVE", color=0xef4444, timestamp=discord.utils.utcnow())
        embed.add_field(name="User", value=f"{member.mention} (`{member.id}`)", inline=True)
        embed.add_field(name="Channel", value=f"`{before.channel.name}`", inline=True)
    elif before.channel != after.channel:
        embed = discord.Embed(title="🔊 VOICE MOVE", color=0x8b5cf6, timestamp=discord.utils.utcnow())
        embed.add_field(name="User", value=f"{member.mention} (`{member.id}`)", inline=True)
        embed.add_field(name="From", value=f"`{before.channel.name}`", inline=True)
        embed.add_field(name="To", value=f"`{after.channel.name}`", inline=True)
    elif before.mute != after.mute:
        action = "Server Muted 🎙️❌" if after.mute else "Server Unmuted 🎙️✅"
        embed = discord.Embed(title=f"🔊 {action}", color=0xf59e0b, timestamp=discord.utils.utcnow())
        embed.add_field(name="User", value=f"{member.mention} (`{member.id}`)", inline=True)
    elif before.deaf != after.deaf:
        action = "Server Deafened 🎧❌" if after.deaf else "Server Undeafened 🎧✅"
        embed = discord.Embed(title=f"🔊 {action}", color=0xf59e0b, timestamp=discord.utils.utcnow())
        embed.add_field(name="User", value=f"{member.mention} (`{member.id}`)", inline=True)

    if embed:
        embed.set_footer(text=f"Log ID: {log_id}")
        await send_log(guild, "voice", embed)

# --- SERVER SETTINGS LOG ---
@bot.event
async def on_guild_update(before: discord.Guild, after: discord.Guild):
    log_id = get_next_log_id("SERV")
    embed = discord.Embed(title="⚙️ SERVER SETTINGS UPDATED", color=0x6366f1, timestamp=discord.utils.utcnow())
    if before.name != after.name:
        embed.add_field(name="Server Name", value=f"`{before.name}` ➔ `{after.name}`", inline=False)
    if before.icon != after.icon:
        embed.add_field(name="Server Icon", value="İkon dəyişdirildi", inline=False)
    if before.verification_level != after.verification_level:
        embed.add_field(name="Verification Level", value=f"`{before.verification_level}` ➔ `{after.verification_level}`", inline=False)
    embed.set_footer(text=f"Log ID: {log_id}")
    await send_log(after, "server", embed)

# --- WEBHOOK LOG ---
@bot.event
async def on_webhooks_update(channel: discord.abc.GuildChannel):
    guild = channel.guild
    moderator = None
    try:
        async for entry in guild.audit_logs(limit=3, action=discord.AuditLogAction.webhook_create):
            moderator = entry.user
            break
    except Exception:
        pass

    log_id = get_next_log_id("HOOK")
    embed = discord.Embed(title="🪝 WEBHOOK UPDATED", color=0x06b6d4, timestamp=discord.utils.utcnow())
    embed.add_field(name="Channel", value=channel.mention, inline=True)
    embed.add_field(name="Executor", value=f"{moderator.mention if moderator else 'Unknown'}", inline=True)
    embed.set_footer(text=f"Log ID: {log_id}")
    await send_log(guild, "webhook", embed)

# --- ON MESSAGE (Stat İzləmə, AFK Yoxlanışı və Komandalar) ---
@bot.event
async def on_message(message: discord.Message):
    if message.author.bot or not message.guild:
        return

    # 1. Rol Etiketleme / Bahsetme Koruması (Role Mention Guard)
    if not is_role_mention_allowed(message):
        try:
            await message.delete()
        except Exception as e:
            print(f"Rol etiketi mesaj silme hatası: {e}")

        try:
            warn_msg = await message.channel.send(
                f"⚠️ {message.author.mention}, bu sunucuda rol etiketlemek yasaktır! Yalnızca yetkili roller ve yöneticiler rol etiketleyebilir."
            )
            asyncio.create_task(auto_delete_message(warn_msg, 4))
        except Exception:
            pass

        log_id = get_next_log_id("SEC")
        embed = discord.Embed(
            title="🛡️ İZİNSİZ ROL ETİKETLEME ENGELLENDİ",
            color=0xf59e0b,
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="Kullanıcı", value=f"{message.author.mention} (`{message.author.id}`)", inline=True)
        embed.add_field(name="Kanal", value=message.channel.mention, inline=True)
        embed.add_field(name="İşlem", value="`Mesaj Silindi ve Uyarıldı`", inline=True)
        embed.add_field(name="Mesaj İçeriği", value=f"```{message.content[:950]}```", inline=False)
        embed.set_footer(text=f"Log ID: {log_id}")
        await send_log(message.guild, "security", embed)
        return

    # 2. Yasaklı Kelimeler Filtresi (.gg, https, /, capulcu, yaz gir)
    if not is_exempt_from_blacklist(message.author):
        matched_trigger = check_blacklisted_content(message.content)
        if matched_trigger:
            try:
                await message.delete()
            except Exception as e:
                print(f"Blacklist mesaj silme hatası: {e}")

            try:
                timeout_until = discord.utils.utcnow() + datetime.timedelta(minutes=1)
                await message.author.timeout(timeout_until, reason=f"Blacklist qadağan söz istifadəsi: {matched_trigger}")
            except Exception as e:
                print(f"Blacklist timeout hatası: {e}")

            try:
                warn_msg = await message.channel.send(
                    f"🚫 {message.author.mention}, yasaklı ifade (`{matched_trigger}`) kullandığınız için mesajınız silindi ve **1 dakika susturuldunuz (mute)**!"
                )
                asyncio.create_task(auto_delete_message(warn_msg, 4))
            except Exception:
                pass

            # Təhlükəsizlik logu göndərmək
            log_id = get_next_log_id("SEC")
            embed = discord.Embed(
                title="🚨 YASAKLI KELİME İHLALİ (OTOMATİK MUTE 1 DK)",
                color=0xef4444,
                timestamp=discord.utils.utcnow()
            )
            embed.add_field(name="İstifadəçi", value=f"{message.author.mention} (`{message.author.id}`)", inline=True)
            embed.add_field(name="Kanal", value=message.channel.mention, inline=True)
            embed.add_field(name="Tespit Edilen Kelime", value=f"`{matched_trigger}`", inline=True)
            embed.add_field(name="Uygulanan Ceza", value="`1 Dakikalık Susturma (Mute)`", inline=True)
            embed.add_field(name="Mesaj İçeriği", value=f"```{message.content[:950]}```", inline=False)
            embed.set_footer(text=f"Log ID: {log_id}")
            await send_log(message.guild, "security", embed)
            return

    # Statbot: Track user message count and active channel
    try:
        record_user_message(message.guild.id, message.author.id, message.channel.id)
    except Exception as e:
        print(f"Stat message tracking error: {e}")

    user_id = str(message.author.id)

    # 1. İstifadəçi özü AFK idisə və mesaj yazdısa, AFK-nı qaldır
    if user_id in db.get("afk", {}) and not message.content.startswith(("a!afk", "!afk")):
        del db["afk"][user_id]
        save_data(db)
        await message.channel.send(f"👋 Hoş geldiniz {message.author.mention}, AFK durumunuz kaldırıldı!")

    # 2. Mesajda AFK olan kimsə etiketlənibsə
    for mentioned in message.mentions:
        m_id = str(mentioned.id)
        if m_id in db.get("afk", {}):
            afk_data = db["afk"][m_id]
            await message.channel.send(
                f"💤 **{mentioned.display_name}** şu anda AFK modunda!\n"
                f"📝 **Sebep:** `{afk_data['reason']}`\n"
                f"⏰ **AFK Giriş Saati:** `{afk_data['time']}`"
            )

    # 3. Otomatik Selam Yanıtlama (SA - AS Sistemi)
    if not message.content.startswith(("!", "a!", "/", ".")):
        clean_text = message.content.strip().lower()
        if clean_text in ["sa", "s.a", "s.a.", "selam", "selamlar", "selamün aleyküm", "selamun aleykum", "slm"]:
            now = time.time()
            last_sa = getattr(bot, "_last_sa_users", {})
            if now - last_sa.get(message.author.id, 0) > 60:
                last_sa[message.author.id] = now
                bot._last_sa_users = last_sa
                try:
                    await message.reply(f"Aleyküm Selam {message.author.mention}, hoş geldin! 👋", mention_author=False)
                except Exception:
                    pass

    await bot.process_commands(message)

# =============================================================================
# BOTU İŞƏ SALMAQ
# =============================================================================
if __name__ == "__main__":
    ENCODED_TOKEN = "TVRVeU5UUTROalF3T0RneE56Y3dOVEE1TUEuR3hsZ1ZJLmZpVzdyVHRZaWtKdGczZHc0VHhpdUZJQ0lSSEt0a0VsY01xVHNz"
    TOKEN = os.getenv("DISCORD_TOKEN") or base64.b64decode(ENCODED_TOKEN).decode("utf-8")

    bot.run(TOKEN)
