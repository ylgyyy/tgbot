#!/usr/bin/env python3
"""
Telegram 双向传话筒机器人 — 杨了个羊小助手
"""

import os
import json
import time
import logging

from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, BotCommand, BotCommandScopeDefault, BotCommandScopeChat
from telegram.ext import Application, MessageHandler, CommandHandler, CallbackQueryHandler, filters, ContextTypes
from telegram.error import TelegramError

# ============================================================
# 配置
# ============================================================
load_dotenv()

BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
_owner_id = os.environ.get("OWNER_ID", "").strip()
OWNER_ID = int(_owner_id) if _owner_id.isdigit() else 0
PROXY_URL = os.environ.get("TG_PROXY", "").strip()
DATA_DIR = os.environ.get("DATA_DIR", os.path.dirname(os.path.abspath(__file__)))
BLACKLIST_FILE = os.path.join(DATA_DIR, "blacklist.json")
SCAMMER_FILE = os.path.join(DATA_DIR, "scammers.json")

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

MSG_MAP: dict[int, int] = {}
ACTIVE_TIMEOUT = 300


# ============================================================
# 辅助函数
# ============================================================
def get_recent_users(context: ContextTypes.DEFAULT_TYPE) -> list[dict]:
    return context.bot_data.get("recent_users", [])

def get_last_msg_times(context: ContextTypes.DEFAULT_TYPE) -> dict[int, float]:
    return context.bot_data.get("last_msg_times", {})

def touch_last_msg_time(context: ContextTypes.DEFAULT_TYPE, user_id: int):
    times = get_last_msg_times(context)
    times[user_id] = time.time()
    context.bot_data["last_msg_times"] = times

def get_active_target(context: ContextTypes.DEFAULT_TYPE) -> int | None:
    target = context.bot_data.get("active_target")
    if target is None:
        return None
    times = get_last_msg_times(context)
    last_time = times.get(target, 0)
    if time.time() - last_time > ACTIVE_TIMEOUT:
        context.bot_data["active_target"] = None
        return None
    return target

def set_active_target(context: ContextTypes.DEFAULT_TYPE, user_id: int):
    context.bot_data["active_target"] = user_id

def add_recent_user(context: ContextTypes.DEFAULT_TYPE, user_id: int, full_name: str):
    recent = get_recent_users(context)
    recent = [u for u in recent if u["id"] != user_id]
    recent.insert(0, {"id": user_id, "name": full_name})
    context.bot_data["recent_users"] = recent[:5]

def get_user_name(context: ContextTypes.DEFAULT_TYPE, user_id: int) -> str:
    for u in get_recent_users(context):
        if u["id"] == user_id:
            return u["name"]
    return str(user_id)


# ============================================================
# 黑名单
# ============================================================
def load_blacklist() -> set[int]:
    if os.path.exists(BLACKLIST_FILE):
        try:
            with open(BLACKLIST_FILE, "r", encoding="utf-8") as f:
                return set(json.load(f).get("blocked", []))
        except (json.JSONDecodeError, KeyError):
            return set()
    return set()

def save_blacklist(blacklist: set[int]):
    with open(BLACKLIST_FILE, "w", encoding="utf-8") as f:
        json.dump({"blocked": list(blacklist)}, f, ensure_ascii=False, indent=2)

def get_blacklist(context: ContextTypes.DEFAULT_TYPE) -> set[int]:
    if "blacklist" not in context.bot_data:
        context.bot_data["blacklist"] = load_blacklist()
    return context.bot_data["blacklist"]

def is_blocked(context: ContextTypes.DEFAULT_TYPE, user_id: int) -> bool:
    return user_id in get_blacklist(context)

def block_user(context: ContextTypes.DEFAULT_TYPE, user_id: int):
    bl = get_blacklist(context)
    bl.add(user_id)
    context.bot_data["blacklist"] = bl
    save_blacklist(bl)
    if get_active_target(context) == user_id:
        context.bot_data["active_target"] = None

def unblock_user(context: ContextTypes.DEFAULT_TYPE, user_id: int):
    bl = get_blacklist(context)
    bl.discard(user_id)
    context.bot_data["blacklist"] = bl
    save_blacklist(bl)


# ============================================================
# 骗子库
# ============================================================
def load_scammers() -> set[int]:
    if os.path.exists(SCAMMER_FILE):
        try:
            with open(SCAMMER_FILE, "r", encoding="utf-8") as f:
                return set(json.load(f).get("scammers", []))
        except (json.JSONDecodeError, KeyError):
            return set()
    return set()

def save_scammers(scammers: set[int]):
    with open(SCAMMER_FILE, "w", encoding="utf-8") as f:
        json.dump({"scammers": list(scammers)}, f, ensure_ascii=False, indent=2)

def get_scammers(context: ContextTypes.DEFAULT_TYPE) -> set[int]:
    if "scammers" not in context.bot_data:
        context.bot_data["scammers"] = load_scammers()
    return context.bot_data["scammers"]

def is_scammer(context: ContextTypes.DEFAULT_TYPE, user_id: int) -> bool:
    return user_id in get_scammers(context)

def add_scammer(context: ContextTypes.DEFAULT_TYPE, user_id: int):
    sc = get_scammers(context)
    sc.add(user_id)
    context.bot_data["scammers"] = sc
    save_scammers(sc)

def del_scammer(context: ContextTypes.DEFAULT_TYPE, user_id: int):
    sc = get_scammers(context)
    sc.discard(user_id)
    context.bot_data["scammers"] = sc
    save_scammers(sc)


def build_switch_success(sender_name: str, sender_id: int) -> tuple[str, InlineKeyboardMarkup]:
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔗 直接私聊", url=f"tg://user?id={sender_id}")],
    ])
    text = (
        f"已切换到聊天目标:【*{sender_name}*】\n"
        f"uid: `{sender_id}`"
    )
    return text, keyboard


# ============================================================
# 管理员底部键盘
# ============================================================
MAIN_KEYBOARD = ReplyKeyboardMarkup([
    [KeyboardButton("🔄 切换"), KeyboardButton("🚫 小黑屋"), KeyboardButton("⚠️ 骗子库")],
], resize_keyboard=True)

BLACKLIST_KEYBOARD = ReplyKeyboardMarkup([
    [KeyboardButton("🚷 拉黑"), KeyboardButton("🔓 解封"), KeyboardButton("📋 黑名单")],
    [KeyboardButton("🔙 返回主菜单")],
], resize_keyboard=True)

SCAM_KEYBOARD = ReplyKeyboardMarkup([
    [KeyboardButton("⚠️ 加骗子"), KeyboardButton("✅ 删骗子"), KeyboardButton("📋 骗子名单")],
    [KeyboardButton("🔙 返回主菜单")],
], resize_keyboard=True)


# ============================================================
# /start
# ============================================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = update.effective_chat.id

    if user_id == OWNER_ID:
        active = get_active_target(context)
        active_str = get_user_name(context, active) if active else "无"
        await update.message.reply_text(
            "✅ 杨了个羊传声筒已就绪\n\n"
            f"当前对话: *{active_str}*\n\n"
            "别人发消息 → 收到新目标卡片\n"
            "直接发消息 → 发给当前对话对象",
            parse_mode="Markdown",
            reply_markup=MAIN_KEYBOARD,
        )
    else:
        await update.message.reply_text(
            "❤️ 您好，这里是杨了个羊小助手。\n"
            "❤️ 可以通过机器人直接和我联系\n"
            "❤️ 请问有何贵干！！！",
        )


# ============================================================
# /help
# ============================================================
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_chat.id
    if user_id == OWNER_ID:
        await update.message.reply_text(
            "📖 *命令帮助*\n\n"
            "直接发消息 → 发给当前对话对象\n"
            "引用回复 → 精确回复那个人\n\n"
            "底部键盘可快速操作：\n"
            "🔄切换 / 🚫拉黑 / 🔓解封\n"
            "⚠️加骗子 / ✅删骗子 / 📋名单",
            parse_mode="Markdown",
            reply_markup=MAIN_KEYBOARD,
        )
    else:
        await update.message.reply_text(
            "❤️ 直接发消息即可和杨了个羊联系。\n"
            "支持文字、图片、视频、语音、贴图等。"
        )


# ============================================================
# /switch
# ============================================================
async def switch_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != OWNER_ID:
        return

    recent = get_recent_users(context)
    if not recent:
        await update.message.reply_text("还没有人给你发过消息。")
        return

    active = get_active_target(context)
    keyboard = []
    for user in recent:
        label = f"{'🟢 ' if user['id'] == active else ''}{user['name']}"
        keyboard.append([
            InlineKeyboardButton(text=label, callback_data=f"sw_{user['id']}")
        ])

    await update.message.reply_text(
        "🔄 *切换对话对象*：",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )


# ============================================================
# /block
# ============================================================
async def block_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != OWNER_ID:
        return

    replied = update.message.reply_to_message
    if replied:
        target_id = MSG_MAP.get(replied.message_id)
        if target_id:
            block_user(context, target_id)
            name = get_user_name(context, target_id)
            await update.message.reply_text(f"🚫 已拉黑 *{name}*", parse_mode="Markdown")
            return
        else:
            await update.message.reply_text("⚠️ 找不到这条消息对应的发送者。")
            return

    recent = get_recent_users(context)
    blacklist = get_blacklist(context)
    candidates = [u for u in recent if u["id"] not in blacklist]
    if not candidates:
        await update.message.reply_text("没有可拉黑的用户。")
        return

    keyboard = [[InlineKeyboardButton(f"🚫 {u['name']}", callback_data=f"blk_{u['id']}")] for u in candidates]
    await update.message.reply_text(
        "🚫 *拉黑用户*（点击拉黑，或回复消息 + /block）：",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )


# ============================================================
# /unblock
# ============================================================
async def unblock_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != OWNER_ID:
        return

    replied = update.message.reply_to_message
    if replied:
        target_id = MSG_MAP.get(replied.message_id)
        if target_id and is_blocked(context, target_id):
            unblock_user(context, target_id)
            await update.message.reply_text(f"✅ 已解除拉黑 *{get_user_name(context, target_id)}*", parse_mode="Markdown")
            return
        elif target_id:
            await update.message.reply_text("该用户不在黑名单中。")
            return
        else:
            await update.message.reply_text("⚠️ 找不到这条消息对应的发送者。")
            return

    blacklist = get_blacklist(context)
    if not blacklist:
        await update.message.reply_text("黑名单是空的。")
        return

    keyboard = [[InlineKeyboardButton(f"✅ {get_user_name(context, uid)}", callback_data=f"ublk_{uid}")] for uid in blacklist]
    await update.message.reply_text(
        "🔓 *解除拉黑*（点击解封，或回复消息 + /unblock）：",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )


# ============================================================
# /blacklist
# ============================================================
async def blacklist_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != OWNER_ID:
        return
    blacklist = get_blacklist(context)
    if not blacklist:
        await update.message.reply_text("📋 黑名单是空的。")
        return
    lines = ["📋 *小黑屋名单*："]
    for uid in blacklist:
        lines.append(f"• {get_user_name(context, uid)} (`{uid}`)")
    lines.append(f"\n共 {len(blacklist)} 人")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


# ============================================================
# /addscam
# ============================================================
async def addscam_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != OWNER_ID:
        return
    replied = update.message.reply_to_message
    if replied:
        target_id = MSG_MAP.get(replied.message_id)
        if target_id:
            add_scammer(context, target_id)
            await update.message.reply_text(f"⚠️ 已标记为骗子: *{get_user_name(context, target_id)}*", parse_mode="Markdown")
            return
        else:
            await update.message.reply_text("⚠️ 找不到这条消息对应的发送者。")
            return

    recent = get_recent_users(context)
    scammers = get_scammers(context)
    candidates = [u for u in recent if u["id"] not in scammers]
    if not candidates:
        await update.message.reply_text("没有可添加的用户。")
        return
    keyboard = [[InlineKeyboardButton(f"⚠️ {u['name']}", callback_data=f"ascam_{u['id']}")] for u in candidates]
    await update.message.reply_text(
        "⚠️ *添加骗子*（点击添加，或回复消息 + /addscam）：",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )


# ============================================================
# /delscam
# ============================================================
async def delscam_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != OWNER_ID:
        return
    replied = update.message.reply_to_message
    if replied:
        target_id = MSG_MAP.get(replied.message_id)
        if target_id and is_scammer(context, target_id):
            del_scammer(context, target_id)
            await update.message.reply_text(f"✅ 已从骗子库移除: *{get_user_name(context, target_id)}*", parse_mode="Markdown")
            return
        elif target_id:
            await update.message.reply_text("该用户不在骗子库中。")
            return
        else:
            await update.message.reply_text("⚠️ 找不到这条消息对应的发送者。")
            return

    scammers = get_scammers(context)
    if not scammers:
        await update.message.reply_text("骗子库是空的。")
        return
    keyboard = [[InlineKeyboardButton(f"✅ {get_user_name(context, uid)}", callback_data=f"dscam_{uid}")] for uid in scammers]
    await update.message.reply_text(
        "🔓 *删除骗子*（点击移除，或回复消息 + /delscam）：",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )


# ============================================================
# /scamlist
# ============================================================
async def scamlist_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != OWNER_ID:
        return
    scammers = get_scammers(context)
    if not scammers:
        await update.message.reply_text("📋 骗子库是空的。")
        return
    lines = ["📋 *骗子库名单*："]
    for uid in scammers:
        lines.append(f"• {get_user_name(context, uid)} (`{uid}`)")
    lines.append(f"\n共 {len(scammers)} 人")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


# ============================================================
# 回调：拉黑 / 解封 / 加骗子 / 删骗子
# ============================================================
async def block_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    try: target_id = int(query.data.split("_")[1])
    except: await query.edit_message_text("⚠️ 选项无效。"); return
    block_user(context, target_id)
    await query.edit_message_text(f"🚫 已拉黑 *{get_user_name(context, target_id)}*", parse_mode="Markdown")

async def unblock_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    try: target_id = int(query.data.split("_")[1])
    except: await query.edit_message_text("⚠️ 选项无效。"); return
    unblock_user(context, target_id)
    await query.edit_message_text(f"✅ 已解除拉黑 *{get_user_name(context, target_id)}*", parse_mode="Markdown")

async def addscam_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    try: target_id = int(query.data.split("_")[1])
    except: await query.edit_message_text("⚠️ 选项无效。"); return
    add_scammer(context, target_id)
    await query.edit_message_text(f"⚠️ 已标记为骗子: *{get_user_name(context, target_id)}*", parse_mode="Markdown")

async def delscam_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    try: target_id = int(query.data.split("_")[1])
    except: await query.edit_message_text("⚠️ 选项无效。"); return
    del_scammer(context, target_id)
    await query.edit_message_text(f"✅ 已从骗子库移除: *{get_user_name(context, target_id)}*", parse_mode="Markdown")


# ============================================================
# 核心：陌生人 → 转发给主人（新版卡片格式）
# ============================================================
async def relay_to_owner(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sender = update.effective_user
    sender_id = update.effective_chat.id
    msg = update.message
    if not msg:
        return

    # 判断是否首次出现
    recent_ids = {u["id"] for u in get_recent_users(context)}
    is_new_contact = sender_id not in recent_ids

    add_recent_user(context, sender_id, sender.full_name)
    touch_last_msg_time(context, sender_id)

    if is_blocked(context, sender_id):
        logger.info(f"[屏蔽] {sender.full_name} ({sender_id})")
        await msg.reply_text("🚫 您已被拉黑，消息无法送达。")
        return

    active = get_active_target(context)

    # 第一个用户 → 自动设为对话对象
    if active is None:
        set_active_target(context, sender_id)
        active = sender_id

    logger.info(f"[→主人] {sender.full_name} ({sender_id}) | 当前: {get_user_name(context, active)}")
    try:
        # 用 Telegram 原生转发（自带 "Forwarded from xxx" 抬头）
        fwd = await msg.forward(chat_id=OWNER_ID)
        MSG_MAP[fwd.message_id] = sender_id

        # 首次联系人 → 发新卡片
        if is_new_contact:
            card_text = f"新的聊天目标:\n{sender.full_name}\nUID: `{sender_id}`"
            if is_scammer(context, sender_id):
                card_text += "\n\n⚠️ 注意：此人是骗子，注意甄别。"
            card_keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("📩 发送信息", callback_data=f"sw_{sender_id}")],
                [InlineKeyboardButton("🔗 直接私聊", url=f"tg://user?id={sender_id}")],
            ])
            card_msg = await context.bot.send_message(
                chat_id=OWNER_ID, text=card_text,
                parse_mode="Markdown", disable_web_page_preview=True,
                reply_markup=card_keyboard,
            )
            MSG_MAP[card_msg.message_id] = sender_id

        # 非当前对话对象 → 发切换按钮
        elif sender_id != active:
            await context.bot.send_message(
                chat_id=OWNER_ID,
                text=f"↩️ 回复给 *{sender.full_name}*？",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton(f"🔄 切换到 {sender.full_name}", callback_data=f"sw_{sender_id}")
                ]]),
            )

    except TelegramError as e:
        logger.error(f"转发失败: {e}")
        await msg.reply_text("⚠️ 发送失败，请稍后再试。")


# ============================================================
# 核心：主人发消息 → 发给当前对话对象
# ============================================================
async def relay_from_owner(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg:
        return

    # 引用回复 → 精确回复
    replied = msg.reply_to_message
    if replied:
        target_id = MSG_MAP.get(replied.message_id)
        if target_id:
            logger.info(f"[←对方] 引用回复 → {target_id}")
            try:
                await msg.copy(chat_id=target_id)
            except TelegramError as e:
                await msg.reply_text(f"⚠️ 发送失败: {e.message}")
            return
        else:
            await msg.reply_text("⚠️ 找不到对应的发送者，可能已过期。")
            return

    # 直接发消息 → 发给当前对话对象
    target_id = get_active_target(context)
    if target_id is None:
        # 带上最近 5 个用户按钮，方便快速切换
        recent = get_recent_users(context)
        keyboard = None
        if recent:
            keyboard = InlineKeyboardMarkup([[
                InlineKeyboardButton(text=u["name"], callback_data=f"sw_{u['id']}")
            ] for u in recent])

        await msg.reply_text(
            "💡 还没有人给你发过消息（或已超过5分钟）。\n"
            "等有人发消息后会自动设为对话对象。",
            reply_markup=keyboard,
        )
        return

    name = get_user_name(context, target_id)
    logger.info(f"[←对方] → {name} ({target_id})")

    try:
        await msg.copy(chat_id=target_id)
    except TelegramError as e:
        await msg.reply_text(f"⚠️ 发送失败: {e.message}")


# ============================================================
# 按钮回调 — 切换 / 发送信息
# ============================================================
async def switch_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    try:
        target_id = int(query.data.split("_")[1])
    except (IndexError, ValueError):
        await query.edit_message_text("⚠️ 选项无效。")
        return

    set_active_target(context, target_id)
    touch_last_msg_time(context, target_id)
    name = get_user_name(context, target_id)

    text, keyboard = build_switch_success(name, target_id)
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=keyboard)
    logger.info(f"[切换] → {name} ({target_id})")


# ============================================================
# 消息路由
# ============================================================
async def router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    if update.effective_chat.id == OWNER_ID:
        # 底部键盘按钮
        text = update.message.text or ""

        # 子键盘命令
        sub_commands = {
            "🚷 拉黑": block_command,
            "🔓 解封": unblock_command,
            "📋 黑名单": blacklist_command,
            "⚠️ 加骗子": addscam_command,
            "✅ 删骗子": delscam_command,
            "📋 骗子名单": scamlist_command,
        }

        if text == "🔄 切换":
            await switch_command(update, context)
        elif text == "🚫 小黑屋":
            await update.message.reply_text("🚫 小黑屋 — 选择操作：", reply_markup=BLACKLIST_KEYBOARD)
        elif text == "⚠️ 骗子库":
            await update.message.reply_text("⚠️ 骗子库 — 选择操作：", reply_markup=SCAM_KEYBOARD)
        elif text == "🔙 返回主菜单":
            await update.message.reply_text("✅ 已返回主菜单", reply_markup=MAIN_KEYBOARD)
        elif text in sub_commands:
            await sub_commands[text](update, context)
        else:
            await relay_from_owner(update, context)
    else:
        await relay_to_owner(update, context)


# ============================================================
# 定期清理
# ============================================================
async def cleanup_map(context: ContextTypes.DEFAULT_TYPE):
    if len(MSG_MAP) > 2000:
        keys = list(MSG_MAP.keys())
        for k in keys[:-1000]:
            del MSG_MAP[k]


# ============================================================
# 错误处理
# ============================================================
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"异常: {context.error}", exc_info=context.error)


# ============================================================
# 启动
# ============================================================
def main():
    if not BOT_TOKEN:
        logger.error("未设置 BOT_TOKEN，请在 .env 文件中配置后重试。")
        return
    if OWNER_ID <= 0:
        logger.error("未设置有效的 OWNER_ID，请在 .env 文件中配置后重试。")
        return

    logger.info("=" * 40)
    logger.info("杨了个羊传声筒启动")
    logger.info(f"主人 ID: {OWNER_ID}")
    logger.info(f"代理: {PROXY_URL}" if PROXY_URL else "代理: 直连")
    logger.info("=" * 40)

    builder = Application.builder().token(BOT_TOKEN)
    if PROXY_URL:
        builder = builder.proxy(PROXY_URL)
    builder = builder.connect_timeout(30).read_timeout(30).write_timeout(30).pool_timeout(30)
    app = builder.build()

    # 命令
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("switch", switch_command))
    app.add_handler(CommandHandler("block", block_command))
    app.add_handler(CommandHandler("unblock", unblock_command))
    app.add_handler(CommandHandler("blacklist", blacklist_command))
    app.add_handler(CommandHandler("addscam", addscam_command))
    app.add_handler(CommandHandler("delscam", delscam_command))
    app.add_handler(CommandHandler("scamlist", scamlist_command))

    # 回调
    app.add_handler(CallbackQueryHandler(switch_callback, pattern=r"^sw_\d+$"))
    app.add_handler(CallbackQueryHandler(block_callback, pattern=r"^blk_\d+$"))
    app.add_handler(CallbackQueryHandler(unblock_callback, pattern=r"^ublk_\d+$"))
    app.add_handler(CallbackQueryHandler(addscam_callback, pattern=r"^ascam_\d+$"))
    app.add_handler(CallbackQueryHandler(delscam_callback, pattern=r"^dscam_\d+$"))

    # 消息
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, router))

    if app.job_queue:
        app.job_queue.run_repeating(cleanup_map, interval=1800)
    app.add_error_handler(error_handler)

    async def set_commands(app):
        # 普通用户
        await app.bot.set_my_commands([
            BotCommand("start", "开始"),
            BotCommand("help", "帮助"),
        ], scope=BotCommandScopeDefault())
        # 管理员
        await app.bot.set_my_commands([
            BotCommand("start", "开始"),
            BotCommand("help", "帮助"),
            BotCommand("switch", "切换对话对象"),
            BotCommand("block", "拉黑用户"),
            BotCommand("unblock", "解除拉黑"),
            BotCommand("blacklist", "查看黑名单"),
            BotCommand("addscam", "添加骗子"),
            BotCommand("delscam", "删除骗子"),
            BotCommand("scamlist", "查看骗子库"),
        ], scope=BotCommandScopeChat(chat_id=OWNER_ID))

    app.post_init = set_commands
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
