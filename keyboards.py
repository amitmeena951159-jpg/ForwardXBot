from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder

def main_menu():
    kb = ReplyKeyboardBuilder()
    kb.button(text="➕ Add Source")
    kb.button(text="➕ Add Target")
    kb.button(text="/forward")
    kb.button(text="📊 Status")
    kb.button(text="🗂 Mappings")
    kb.button(text="▶ Resume")
    kb.button(text="⏸ Pause")
    kb.button(text="💎 Upgrade")
    kb.adjust(2)
    return kb.as_markup(resize_keyboard=True)

def plans_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="₹150 — 1 Month", callback_data="plan:150:30")
    kb.button(text="₹400 — 3 Months", callback_data="plan:400:90")
    kb.button(text="₹1200 — Lifetime", callback_data="plan:1200:36500")
    kb.adjust(1)
    return kb.as_markup()

def mapping_controls(mapping_id: int, active: int):
    kb = InlineKeyboardBuilder()
    if active:
        kb.button(text="⏸ Pause", callback_data=f"map:pause:{mapping_id}")
    else:
        kb.button(text="▶ Resume", callback_data=f"map:resume:{mapping_id}")
    kb.button(text="🗑 Delete", callback_data=f"map:delete:{mapping_id}")
    kb.adjust(2)
    return kb.as_markup()
