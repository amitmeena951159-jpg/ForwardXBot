import os
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InputFile
from aiogram.filters import Command
from loguru import logger

from database import (
    ensure_user, get_user, increment_daily, list_mappings, create_mapping,
    toggle_mapping, delete_mapping, targets_for_source, create_payment,
    set_payment_status, set_premium_days, revoke_premium
)
from keyboards import main_menu, plans_kb, mapping_controls
from utils import upi_qr_path, is_premium_row

router = Router()

ADMIN_ID = int(os.getenv("ADMIN_ID") or "0")
FREE_DAILY_LIMIT = int(os.getenv("FREE_DAILY_LIMIT") or os.getenv("DAILY_LIMIT") or "50")
UPI_ID = os.getenv("UPI_ID") or ""

# ---------- Basics ----------

@router.message(Command("start"))
async def cmd_start(m: Message):
    await ensure_user(m.from_user.id, m.from_user.username)
    await m.answer(
        "👋 Welcome to ForwardXBot 🚀\n\n"
        f"Free: {FREE_DAILY_LIMIT} msgs/day (auto reset 00:00 IST)\n"
        "Premium: Unlimited 💎\n\n"
        "• Map chats: /forward <source_chat_id> <target_chat_id>\n"
        "• Bot ko dono chats me add karke admin banao.\n"
        "• Groups me sab msgs lene ke liye BotFather → /setprivacy → Disable.\n",
        reply_markup=main_menu()
    )

@router.message(Command("help"))
async def cmd_help(m: Message):
    await m.answer(
        "🆘 Help\n\n"
        "/id — apna/user chat ID\n"
        "/status — quota/premium\n"
        "/forward <src> <dst> — mapping banao\n"
        "/mappings — list + controls\n"
        "/pause <id> /resume <id>\n"
        "/upgrade — premium plans\n"
        "Admin: /approve <user_id> <days>, /revoke <user_id>, /reject <payment_id>"
    )

@router.message(Command("id"))
async def cmd_id(m: Message):
    await m.answer(f"👤 Your ID: `{m.from_user.id}`\n💬 This chat ID: `{m.chat.id}`", parse_mode="Markdown")

@router.message(Command("status"))
async def cmd_status(m: Message):
    row = await get_user(m.from_user.id)
    if not row:
        await ensure_user(m.from_user.id, m.from_user.username)
        row = await get_user(m.from_user.id)
    premium = is_premium_row(row)
    used = row[2] or 0
    left = "∞" if premium else max(0, FREE_DAILY_LIMIT - used)
    until = row[3] if row[3] else "—"
    await m.answer(
        f"📊 Status\n"
        f"• Used today: {used}/{FREE_DAILY_LIMIT}\n"
        f"• Remaining: {left}\n"
        f"• Premium until: {until}\n"
    )

# ---------- Mapping ----------

@router.message(Command("forward"))
async def cmd_forward(m: Message):
    await ensure_user(m.from_user.id, m.from_user.username)
    parts = (m.text or "").split()
    if len(parts) != 3:
        return await m.answer("❌ Usage: `/forward <source_chat_id> <target_chat_id>`", parse_mode="Markdown")
    src, dst = parts[1], parts[2]
    if not (src.startswith("-") and dst.startswith("-")):
        return await m.answer("❌ Chat IDs wrong. Channel/Group IDs usually: `-100...`", parse_mode="Markdown")
    mid = await create_mapping(m.from_user.id, src, dst)
    await m.answer(f"✅ Mapping #{mid} created:\n`{src}` → `{dst}`", parse_mode="Markdown")

@router.message(Command("mappings"))
async def cmd_mappings(m: Message):
    rows = await list_mappings(m.from_user.id)
    if not rows:
        return await m.answer("ℹ️ No mappings yet. Use /forward <src> <dst>")
    text = "🗂 Your Mappings:\n\n"
    for (mid, src, dst, active) in rows:
        text += f"#{mid} — `{src}` → `{dst}` — {'✅ active' if active else '⏸ paused'}\n"
    await m.answer(text, parse_mode="Markdown")
    # Latest mapping ke controls
    last = rows[0]
    await m.answer(f"Controls for #{last[0]}", reply_markup=mapping_controls(last[0], last[3]))

@router.message(Command("pause"))
async def cmd_pause(m: Message):
    parts = (m.text or "").split()
    if len(parts) != 2:
        return await m.answer("Usage: /pause <mapping_id>")
    ok = await toggle_mapping(m.from_user.id, int(parts[1]), 0)
    await m.answer("⏸ Paused" if ok else "❌ Not found")

@router.message(Command("resume"))
async def cmd_resume(m: Message):
    parts = (m.text or "").split()
    if len(parts) != 2:
        return await m.answer("Usage: /resume <mapping_id>")
    ok = await toggle_mapping(m.from_user.id, int(parts[1]), 1)
    await m.answer("▶ Resumed" if ok else "❌ Not found")

@router.callback_query(F.data.startswith("map:"))
async def cb_map(q: CallbackQuery):
    _, action, mid = q.data.split(":")
    mid = int(mid)
    if action == "pause":
        ok = await toggle_mapping(q.from_user.id, mid, 0)
        await q.message.edit_reply_markup(reply_markup=mapping_controls(mid, 0) if ok else None)
        await q.answer("Paused" if ok else "Not your mapping")
    elif action == "resume":
        ok = await toggle_mapping(q.from_user.id, mid, 1)
        await q.message.edit_reply_markup(reply_markup=mapping_controls(mid, 1) if ok else None)
        await q.answer("Resumed" if ok else "Not your mapping")
    elif action == "delete":
        ok = await delete_mapping(q.from_user.id, mid)
        if ok:
            await q.message.edit_text(f"🗑 Mapping #{mid} deleted")
        await q.answer("Deleted" if ok else "Not your mapping")

# ---------- Payments / Premium ----------

@router.message(Command("upgrade"))
async def cmd_upgrade(m: Message):
    if not UPI_ID:
        return await m.answer("⚠️ UPI not configured by admin.")
    await m.answer(
        "💎 Upgrade Plans\n"
        f"Pay to UPI: `{UPI_ID}`\n"
        "Then send: `/pay <amount> <txn_id>`\n",
        reply_markup=plans_kb(),
        parse_mode="Markdown",
    )

@router.callback_query(F.data.startswith("plan:"))
async def cb_plan(q: CallbackQuery):
    if not UPI_ID:
        return await q.answer("UPI not configured", show_alert=True)
    _, amount, days = q.data.split(":")
    amount = int(amount)
    days = int(days)
    path = upi_qr_path(UPI_ID, amount, "ForwardX Premium")
    await q.message.answer_photo(
        photo=InputFile(path),
        caption=(
            f"🔶 Plan Selected: ₹{amount}\n"
            f"🗓 Validity: {days} days\n\n"
            f"UPI: `{UPI_ID}`\n"
            f"After payment: `/pay {amount} YOUR_TXN_ID`"
        ),
        parse_mode="Markdown",
    )
    await q.answer("Plan details sent.")

@router.message(Command("pay"))
async def cmd_pay(m: Message):
    parts = (m.text or "").split(maxsplit=2)
    if len(parts) < 3:
        return await m.answer("Usage: /pay <amount> <txn_id>")
    try:
        amount = int(parts[1])
    except Exception:
        return await m.answer("Amount must be a number. Example: /pay 150 ABC123")
    txn_id = parts[2].strip()
    pid = await create_payment(m.from_user.id, amount, txn_id)
    try:
        await m.bot.send_message(
            chat_id=int(ADMIN_ID),
            text=(
                f"🔔 Payment Request\nUser: @{m.from_user.username} ({m.from_user.id})\n"
                f"Amount: ₹{amount}\nTxn: {txn_id}\nPayment ID: {pid}\n\n"
                f"Approve: /approve {m.from_user.id} 30\nReject: /reject {pid}"
            ),
        )
    except Exception as e:
        logger.error(f"Admin notify failed: {e}")
    await m.answer("✅ Payment submitted. Admin will verify & upgrade you soon.")

@router.message(Command("approve"))
async def cmd_approve(m: Message):
    if m.from_user.id != ADMIN_ID:
        return await m.answer("⛔ Not authorized.")
    parts = (m.text or "").split()
    if len(parts) != 3:
        return await m.answer("Usage: /approve <user_id> <days>")
    uid = int(parts[1])
    days = int(parts[2])
    until = await set_premium_days(uid, days)
    try:
        await m.bot.send_message(uid, f"🎉 Premium activated for {days} days!\nValid until: {until.isoformat()}")
    except Exception:
        pass
    await m.answer(f"✅ Approved user {uid} until {until.isoformat()}")

@router.message(Command("reject"))
async def cmd_reject(m: Message):
    if m.from_user.id != ADMIN_ID:
        return await m.answer("⛔ Not authorized.")
    parts = (m.text or "").split()
    if len(parts) != 2:
        return await m.answer("Usage: /reject <payment_id>")
    pid = int(parts[1])
    await set_payment_status(pid, "rejected")
    await m.answer(f"❌ Payment {pid} rejected.")

@router.message(Command("revoke"))
async def cmd_revoke(m: Message):
    if m.from_user.id != ADMIN_ID:
        return await m.answer("⛔ Not authorized.")
    parts = (m.text or "").split()
    if len(parts) != 2:
        return await m.answer("Usage: /revoke <user_id>")
    uid = int(parts[1])
    await revoke_premium(uid)
    await m.answer(f"⛔ Premium revoked for {uid}")

# ---------- Forwarder (groups + channels) ----------

async def _process_forward(m: Message):
    rows = await targets_for_source(m.chat.id)
    if not rows:
        return
    counted_owners = set()
    for owner_id, mapping_id, target_chat in rows:
        row = await get_user(owner_id)
        if not row:
            continue
        premium = is_premium_row(row)
        used = row[2] or 0
        # daily limit per owner
        if (not premium) and (owner_id not in counted_owners) and used >= FREE_DAILY_LIMIT:
            continue
        try:
            await m.bot.copy_message(
                chat_id=int(target_chat),
                from_chat_id=m.chat.id,
                message_id=m.message_id,
            )
            if not premium and owner_id not in counted_owners:
                await increment_daily(owner_id)
                counted_owners.add(owner_id)
        except Exception as e:
            logger.error(f"copy_message failed map#{mapping_id} -> {target_chat}: {e}")

@router.message()
async def forwarder_message(m: Message):
    # generic messages in groups
    await _process_forward(m)

@router.channel_post()
async def forwarder_channel(m: Message):
    # channel posts
    await _process_forward(m)
