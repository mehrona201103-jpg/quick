import os
import asyncio
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo, LabeledPrice, PreCheckoutQuery, ReplyKeyboardRemove
from dotenv import load_dotenv
from app import db

load_dotenv()
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("quick-trader")
TOKEN = os.getenv("BOT_TOKEN", "")
ADMINS = {int(x.strip()) for x in os.getenv("ADMIN_IDS", "8383354229").split(",") if x.strip().isdigit()}
WEBAPP_URL = os.getenv("WEBAPP_URL", "")
CHANNEL = os.getenv("CHANNEL_USERNAME", "@quick_app_official")
CHANNEL_URL = os.getenv("CHANNEL_URL", "https://t.me/quick_app_official")
REFERRAL_URL = os.getenv("POCKET_OPTION_REFERRAL_URL", "https://pocket-friends.co/r/a2lx2ihvqq")
PROMO_CODE = os.getenv("POCKET_OPTION_PROMO_CODE", "FRIENDA2LX2IHVQQ")
BOT_NAME = "QUICK TRADER AI"
AUTHOR_ID = int(os.getenv("AUTHOR_TELEGRAM_ID", "8383354229"))
CRYPTOPAY_TOKEN = os.getenv("CRYPTOPAY_TOKEN", "")
PLANS = {"m1": (1, "VIP · 1 месяц", 500, 200), "m6": (6, "VIP · 6 месяцев", 1000, 400), "p6": (6, "VIP Premium · 6 месяцев", 2000, 900)}
dp = Dispatcher()
db.init()


def inline(*rows):
    return InlineKeyboardMarkup(inline_keyboard=[list(row) for row in rows])


def subscribe_kb():
    return inline(
        [InlineKeyboardButton(text="↗ Подписаться на канал", url=CHANNEL_URL)],
        [InlineKeyboardButton(text="✓ Проверить подписку", callback_data="check_subscription")],
    )


def broker_kb():
    return inline(
        [InlineKeyboardButton(text="↗ Регистрация Pocket Option", url=REFERRAL_URL)],
        [InlineKeyboardButton(text="✓ Я зарегистрировался", callback_data="registered")],
    )


def open_app_kb():
    if WEBAPP_URL.startswith("https://"):
        return inline([InlineKeyboardButton(text="◈ Открыть QUICK TRADER AI", web_app=WebAppInfo(url=WEBAPP_URL))])
    return inline([InlineKeyboardButton(text="⚙ Настроить WebApp", callback_data="show_setup")])


def plans_kb():
    return inline(
        [InlineKeyboardButton(text="VIP · 1 месяц — $5 / 200 ⭐", callback_data="plan:m1")],
        [InlineKeyboardButton(text="VIP · 6 месяцев — $10 / 400 ⭐", callback_data="plan:m6")],
        [InlineKeyboardButton(text="VIP Premium · 6 месяцев — $20 / 900 ⭐", callback_data="plan:p6")],
        [InlineKeyboardButton(text="🎁 Подарить автору", url=f"tg://user?id={AUTHOR_ID}")],
    )

def account_kb():
    buttons = []
    if WEBAPP_URL.startswith("https://"):
        buttons.append([InlineKeyboardButton(text="◈ Открыть терминал", web_app=WebAppInfo(url=WEBAPP_URL))])
    buttons.extend([
        [InlineKeyboardButton(text="▤ История сигналов", callback_data="history")],
        [InlineKeyboardButton(text="♙ Профиль", callback_data="profile")],
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def is_subscribed(bot: Bot, user_id: int) -> bool:
    try:
        m = await bot.get_chat_member(CHANNEL, user_id)
        return m.status in {"creator", "administrator", "member"} or (m.status == "restricted" and getattr(m, "is_member", False))
    except Exception as exc:
        log.warning("Membership check failed for %s in %s: %s", user_id, CHANNEL, exc)
        raise RuntimeError("Не удалось проверить подписку. Добавьте бота администратором канала и повторите проверку.") from exc


async def show_subscription(message: Message, edit=False):
    db.set_step(message.from_user.id, "subscription")
    text = (f"<b>Добро пожаловать в {BOT_NAME}</b>\n\n"
            "<blockquote>Шаг 1 из 3</blockquote>\n"
            "Сначала подпишитесь на наш Telegram-канал, затем нажмите «Проверить подписку».")
    await message.answer(text, reply_markup=subscribe_kb(), parse_mode="HTML")


async def show_broker_registration(target, user_id: int):
    db.set_step(user_id, "broker")
    text = ("<b>Шаг 2 из 3 · Регистрация</b>\n\n"
            "Откройте Pocket Option по своей ссылке и при регистрации введите промокод:\n\n"
            f"<code>{PROMO_CODE}</code>\n\n"
            "Промокод для бонуса к депозиту до 50% (при выполнении действующих условий брокера). Размер, доступность и условия бонуса определяет Pocket Option — бот не управляет начислением.\n\n"
            "После регистрации нажмите «Я зарегистрировался».")
    await target.answer(text, reply_markup=broker_kb(), parse_mode="HTML")


async def ask_pocket_id(target, user_id: int):
    db.set_step(user_id, "pocket_id")
    await target.answer(
        "<b>Шаг 3 из 3 · Подключение</b>\n\n"
        "Отправьте ваш числовой Pocket Option ID одним сообщением. После сохранения доступ к WebApp откроется автоматически.",
        parse_mode="HTML",
    )


@dp.message(CommandStart())
async def start(m: Message):
    # Remove any legacy persistent reply keyboard from previous bot versions.
    await m.answer("Меню обновлено — используйте кнопки в сообщениях.", reply_markup=ReplyKeyboardRemove())
    db.upsert_user(m.from_user.id, m.from_user.username, m.from_user.first_name)
    u = db.get_user(m.from_user.id)
    if u["blocked"]:
        await m.answer("Доступ к боту ограничен. Обратитесь к администратору.")
        return
    if (m.text or "").strip().startswith("/start plans"):
        await m.answer("<b>Тарифы QUICK TRADER AI</b>\nВыберите VIP-план и способ оплаты.",reply_markup=plans_kb(),parse_mode="HTML")
        return
    if u["approved"] and u["pocket_id"]:
        db.activate_trial(m.from_user.id)
        a=db.access_status(m.from_user.id)
        if not a["allowed"]:
            await m.answer("<b>Пробный доступ завершён</b>\nВыберите тариф, чтобы снова открыть WEBAPP.",reply_markup=plans_kb(),parse_mode="HTML")
        else:
            await m.answer("<b>С возвращением!</b> Аккаунт сохранён. Выберите нужный раздел.", reply_markup=account_kb(), parse_mode="HTML")
        return
    # Verify channel membership on every incomplete registration restart.
    try:
        member = await is_subscribed(m.bot, m.from_user.id)
    except RuntimeError as exc:
        await m.answer(str(exc) + f"\nКанал: {CHANNEL_URL}")
        return
    if not member:
        await show_subscription(m)
        return
    # Continue the last persisted registration step if the user returns later.
    step = db.get_step(m.from_user.id)
    if step == "pocket_id":
        await ask_pocket_id(m, m.from_user.id)
    else:
        await show_broker_registration(m, m.from_user.id)


@dp.callback_query(F.data == "check_subscription")
async def check_subscription(c: CallbackQuery):
    try:
        member = await is_subscribed(c.bot, c.from_user.id)
    except RuntimeError as exc:
        await c.answer("Не удалось проверить подписку", show_alert=True)
        await c.message.answer(str(exc))
        return
    if not member:
        await c.answer("Подписка пока не найдена", show_alert=True)
        await c.message.answer("Подпишитесь на канал и нажмите проверку ещё раз.", reply_markup=subscribe_kb())
        return
    await c.answer("Подписка подтверждена")
    await show_broker_registration(c.message, c.from_user.id)


@dp.callback_query(F.data == "registered")
async def registered(c: CallbackQuery):
    u = db.get_user(c.from_user.id)
    if not u:
        db.upsert_user(c.from_user.id, c.from_user.username, c.from_user.first_name)
    try:
        member = await is_subscribed(c.bot, c.from_user.id)
    except RuntimeError as exc:
        await c.answer("Ошибка проверки подписки", show_alert=True)
        await c.message.answer(str(exc))
        return
    if not member:
        await c.answer("Сначала подпишитесь на канал", show_alert=True)
        await show_subscription(c.message)
        return
    await c.answer()
    await ask_pocket_id(c.message, c.from_user.id)


@dp.message(Command("cancel"))
async def cancel(m: Message):
    db.set_step(m.from_user.id, "subscription")
    await m.answer("Регистрация сброшена. Нажмите /start, чтобы начать заново.")


@dp.message(Command("admin"))
async def admin(m: Message):
    if m.from_user.id not in ADMINS:
        return
    st = db.stats()
    await m.answer(
        f"<b>⚙ Админ-панель QUICK TRADER AI</b>\n\n"
        f"👥 Всего пользователей: <b>{st['users']}</b>\n"
        f"✅ Активный доступ: <b>{st['approved']}</b>\n"
        f"💎 VIP-профилей: <b>{st['vip']}</b>\n"
        f"🚫 Заблокировано: <b>{st['blocked']}</b>\n"
        f"📊 Сигналов всего: <b>{st['signals']}</b>\n\n"
        "<b>Команды управления</b>\n"
        "/users — последние пользователи\n/stats — статистика\n/user ID — профиль пользователя\n"
        "/approve ID — открыть доступ\n/revoke ID — забрать доступ\n"
        "/grantvip ID ДНИ — выдать VIP\n/revokevip ID — забрать VIP\n"
        "/block ID — блокировка\n/unblock ID — снять блокировку\n"
        "/events — последние события", parse_mode="HTML")

@dp.message(Command("stats"))
async def admin_stats_cmd(m: Message):
    if m.from_user.id not in ADMINS: return
    st=db.stats()
    await m.answer(f"📊 <b>Статистика</b>\nПользователи: {st['users']}\nДоступ открыт: {st['approved']}\nVIP: {st['vip']}\nЗаблокированы: {st['blocked']}\nСигналы: {st['signals']}",parse_mode="HTML")

@dp.message(Command("users"))
async def admin_users(m: Message):
    if m.from_user.id not in ADMINS: return
    rows=db.list_users(20,0)
    if not rows: return await m.answer("Пользователей пока нет.")
    lines=[]
    for u in rows:
        name=("@"+u["username"]) if u["username"] else (u["first_name"] or "без имени")
        vip=u["vip_until"] or "нет VIP"
        lines.append(f"• <code>{u['tg_id']}</code> · {name} · доступ:{'да' if u['approved'] and not u['blocked'] else 'нет'} · VIP:{vip}")
    await m.answer("<b>Последние 20 пользователей</b>\n"+"\n".join(lines),parse_mode="HTML")

@dp.message(Command("user"))
async def admin_user(m: Message):
    if m.from_user.id not in ADMINS: return
    a=(m.text or "").split()
    if len(a)!=2 or not a[1].isdigit(): return await m.answer("Использование: /user TELEGRAM_ID")
    u=db.get_user(int(a[1]))
    if not u: return await m.answer("Пользователь не найден.")
    await m.answer(f"<b>Профиль</b>\nID: <code>{u['tg_id']}</code>\nИмя: {u['first_name'] or '—'}\nUsername: @{u['username'] or '—'}\nPocket ID: <code>{u['pocket_id'] or '—'}</code>\nДоступ: {u['approved']}\nБлок: {u['blocked']}\nVIP: {u['vip_plan'] or 'нет'}\nVIP до: {u['vip_until'] or '—'}\nРегистрация: {u['created_at']}",parse_mode="HTML")

@dp.message(Command("revoke"))
async def revoke_access(m: Message):
    if m.from_user.id not in ADMINS: return
    a=(m.text or "").split()
    if len(a)!=2 or not a[1].isdigit(): return await m.answer("Использование: /revoke TELEGRAM_ID")
    db.set_approved(int(a[1]),False); db.log_event(m.from_user.id,f"revoked access for {a[1]}")
    await m.answer("Доступ отключён.")

@dp.message(Command("grantvip"))
async def grant_vip_cmd(m: Message):
    if m.from_user.id not in ADMINS: return
    a=(m.text or "").split()
    if len(a)!=3 or not a[1].isdigit() or not a[2].isdigit() or not 1<=int(a[2])<=3650:
        return await m.answer("Использование: /grantvip TELEGRAM_ID ДНИ (1–3650)")
    from datetime import datetime, timedelta
    u=db.get_user(int(a[1]))
    if not u: return await m.answer("Сначала пользователь должен запустить бота (/start).")
    until=datetime.utcnow()+timedelta(days=int(a[2]))
    db.set_vip_until(int(a[1]),until.isoformat(sep=" "),"VIP · выдан администратором")
    db.log_event(m.from_user.id,f"granted VIP {a[2]} days to {a[1]}")
    await m.answer(f"VIP выдан пользователю {a[1]} на {a[2]} дн., до {until:%Y-%m-%d %H:%M} UTC.")

@dp.message(Command("revokevip"))
async def revoke_vip_cmd(m: Message):
    if m.from_user.id not in ADMINS: return
    a=(m.text or "").split()
    if len(a)!=2 or not a[1].isdigit(): return await m.answer("Использование: /revokevip TELEGRAM_ID")
    if not db.get_user(int(a[1])): return await m.answer("Пользователь не найден.")
    db.revoke_vip(int(a[1])); db.log_event(m.from_user.id,f"revoked VIP from {a[1]}")
    await m.answer("VIP-подписка отозвана.")

@dp.message(Command("events"))
async def admin_events(m: Message):
    if m.from_user.id not in ADMINS: return
    rows=db.recent_events(15)
    await m.answer("<b>Последние действия администратора</b>\n"+("\n".join(f"{x['created_at']} · {x['event']}" for x in rows) if rows else "Событий пока нет."),parse_mode="HTML")


@dp.message(Command("approve"))
async def approve(m: Message):
    if m.from_user.id not in ADMINS:
        return
    a = (m.text or "").split()
    if len(a) == 2 and a[1].isdigit():
        db.set_approved(int(a[1]), True)
        db.log_event(m.from_user.id, f"approved access for {a[1]}")
        await m.answer("Доступ активирован.")
    else:
        await m.answer("Использование: /approve TELEGRAM_ID")


@dp.message(Command("block"))
async def block(m: Message):
    if m.from_user.id not in ADMINS:
        return
    a = (m.text or "").split()
    if len(a) == 2 and a[1].isdigit():
        db.set_blocked(int(a[1]), True)
        db.log_event(m.from_user.id, f"blocked {a[1]}")
        await m.answer("Пользователь заблокирован.")


@dp.message(Command("unblock"))
async def unblock(m: Message):
    if m.from_user.id not in ADMINS:
        return
    a = (m.text or "").split()
    if len(a) == 2 and a[1].isdigit():
        db.set_blocked(int(a[1]), False)
        db.log_event(m.from_user.id, f"unblocked {a[1]}")
        await m.answer("Блокировка снята.")


@dp.callback_query(F.data.startswith("plan:"))
async def choose_plan(c: CallbackQuery):
    key=c.data.split(":",1)[1]
    if key not in PLANS:
        await c.answer("Тариф не найден",show_alert=True); return
    months,title,usd_cents,stars=PLANS[key]
    kb=inline([InlineKeyboardButton(text=f"Оплатить {stars} ⭐",callback_data=f"stars:{key}")],
              [InlineKeyboardButton(text=f"Оплатить ${usd_cents/100:g} через CryptoBot",callback_data=f"crypto:{key}")],
              [InlineKeyboardButton(text="🎁 Подарить автору",url=f"tg://user?id={AUTHOR_ID}")])
    await c.message.answer(f"<b>{title}</b>\nВыберите способ оплаты. VIP включится после подтверждения платежа.",reply_markup=kb,parse_mode="HTML")
    await c.answer()

@dp.callback_query(F.data.startswith("stars:"))
async def stars_payment(c: CallbackQuery):
    key=c.data.split(":",1)[1]
    if key not in PLANS: await c.answer("Тариф не найден",show_alert=True); return
    months,title,usd_cents,stars=PLANS[key]
    await c.bot.send_invoice(chat_id=c.from_user.id,title=title,description=f"Подписка QUICK TRADER AI: {title}",payload=f"qtvip:{key}:{c.from_user.id}",currency="XTR",prices=[LabeledPrice(label=title,amount=stars)])
    await c.answer()

@dp.pre_checkout_query()
async def pre_checkout(q: PreCheckoutQuery):
    bits=q.invoice_payload.split(":")
    ok=len(bits)==3 and bits[0]=="qtvip" and bits[1] in PLANS and bits[2].isdigit() and int(bits[2])==q.from_user.id
    await q.answer(ok=ok,error_message=None if ok else "Платёж не удалось проверить")

@dp.message(F.successful_payment)
async def paid_stars(m: Message):
    payload=m.successful_payment.invoice_payload.split(":")
    if len(payload)!=3 or payload[0]!="qtvip" or payload[1] not in PLANS or int(payload[2])!=m.from_user.id: return
    months,title,_,stars=PLANS[payload[1]]
    db.grant_vip(m.from_user.id,months,payload[1])
    await m.answer(f"✅ Оплата получена. {title} активирован.",reply_markup=account_kb())

@dp.callback_query(F.data.startswith("crypto:"))
async def crypto_payment(c: CallbackQuery):
    import httpx
    key=c.data.split(":",1)[1]
    if key not in PLANS: await c.answer("Тариф не найден",show_alert=True); return
    if not CRYPTOPAY_TOKEN:
        await c.answer("Оплата CryptoBot ещё не настроена",show_alert=True); return
    months,title,usd_cents,stars=PLANS[key]
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r=await client.post("https://pay.crypt.bot/api/createInvoice",headers={"Crypto-Pay-API-Token":CRYPTOPAY_TOKEN},json={"currency_type":"fiat","fiat":"USD","amount":f"{usd_cents/100:.2f}","description":f"QUICK TRADER AI {title}","payload":f"qtvip:{key}:{c.from_user.id}","expires_in":3600})
            data=r.json()
        if not data.get("ok"): raise ValueError(data.get("error",{}).get("name","CryptoBot API error"))
        invoice=data["result"]
        kb=inline([InlineKeyboardButton(text="Оплатить в CryptoBot",url=invoice["pay_url"])],[InlineKeyboardButton(text="Проверить оплату",callback_data=f"cryptocheck:{invoice['invoice_id']}:{key}")])
        await c.message.answer("Счёт создан. После оплаты нажмите «Проверить оплату».",reply_markup=kb)
    except Exception as e:
        log.exception("Crypto invoice creation failed")
        await c.message.answer("Не удалось создать счёт CryptoBot. Попробуйте позже.")
    await c.answer()

@dp.callback_query(F.data.startswith("cryptocheck:"))
async def crypto_check(c: CallbackQuery):
    import httpx
    bits=c.data.split(":")
    if len(bits)!=3 or bits[2] not in PLANS or not CRYPTOPAY_TOKEN: await c.answer("Счёт не найден",show_alert=True); return
    invoice_id,key=bits[1],bits[2]
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r=await client.get("https://pay.crypt.bot/api/getInvoices",headers={"Crypto-Pay-API-Token":CRYPTOPAY_TOKEN},params={"invoice_ids":invoice_id})
            data=r.json()
        rows=data.get("result",{}).get("items",[])
        inv=rows[0] if rows else None
        if not data.get("ok") or not inv or inv.get("status")!="paid" or inv.get("payload")!=f"qtvip:{key}:{c.from_user.id}":
            await c.answer("Оплата пока не подтверждена",show_alert=True); return
        months,title,_,_=PLANS[key]
        db.grant_vip(c.from_user.id,months,key)
        await c.message.answer(f"✅ Оплата подтверждена. {title} активирован.",reply_markup=account_kb())
        await c.answer("VIP активирован")
    except Exception:
        await c.answer("Не удалось проверить платёж",show_alert=True)

@dp.callback_query(F.data == "history")
async def history(c: CallbackQuery):
    rows = db.history(c.from_user.id, 10)
    text = "История пока пуста." if not rows else "<b>Последние сигналы</b>\n\n" + "\n".join(
        f"#{x['id']} · {x['symbol']} · {x['timeframe']} · <b>{x['side']}</b> · {x['created_at']}" for x in rows)
    await c.message.answer(text, reply_markup=account_kb(), parse_mode="HTML")
    await c.answer()


@dp.callback_query(F.data == "profile")
async def profile(c: CallbackQuery):
    u = db.get_user(c.from_user.id)
    if not u:
        await c.answer("Профиль не найден", show_alert=True)
        return
    text = (f"<b>Профиль</b>\nTelegram ID: <code>{u['tg_id']}</code>\n"
            f"Pocket Option ID: <code>{u['pocket_id'] or 'не указан'}</code>\n"
            f"Доступ: {'активен' if u['approved'] and not u['blocked'] else 'не активен'}")
    await c.message.answer(text, reply_markup=account_kb(), parse_mode="HTML")
    await c.answer()


@dp.callback_query(F.data == "show_setup")
async def setup_hint(c: CallbackQuery):
    await c.answer("Укажите WEBAPP_URL с HTTPS в переменных окружения", show_alert=True)


@dp.message(F.text)
async def capture_id(m: Message):
    u = db.get_user(m.from_user.id)
    if not u:
        return
    step = db.get_step(m.from_user.id)
    text = (m.text or "").strip()
    if step != "pocket_id":
        if text.isdigit() and 4 <= len(text) <= 20:
            await m.answer("Чтобы привязать ID, сначала пройдите шаги регистрации через /start.")
        return
    if not text.isdigit() or not 4 <= len(text) <= 20:
        await m.answer("ID должен состоять из 4–20 цифр. Отправьте его ещё раз одним сообщением.")
        return
    db.upsert_user(m.from_user.id, m.from_user.username, m.from_user.first_name)
    db.set_pocket_id(m.from_user.id, text, auto_approve=True)
    for aid in ADMINS:
        try:
            await m.bot.send_message(aid, f"Новый Pocket Option ID: <code>{text}</code>\nTelegram ID: <code>{m.from_user.id}</code>", parse_mode="HTML")
        except Exception:
            log.exception("Could not notify admin %s", aid)
    db.activate_trial(m.from_user.id)
    await m.answer("<b>Готово! Доступ открыт ✅</b>\nАккаунт сохранён. Открывайте WebApp кнопкой ниже.", reply_markup=open_app_kb(), parse_mode="HTML")


async def run_bot():
    if not TOKEN or TOKEN == "replace_me":
        raise RuntimeError("Укажите BOT_TOKEN в переменных окружения")
    async with Bot(TOKEN) as bot:
        await dp.start_polling(bot)
