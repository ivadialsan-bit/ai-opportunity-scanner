from __future__ import annotations
"""
Квалификационный движок — определяет что продавать конкретному лиду
на основе цифровых сигналов + ответов на квалификационные вопросы.
"""

PRODUCTS = {
    "landing": {
        "name": "Лендинг + форма заявки",
        "price_test": "4 900 ₽",
        "price_full": "9 900 ₽",
        "price_pro": "19 900 ₽",
        "delivery": "48 часов",
        "desc": "Одностраничный сайт с описанием услуг, формой заявки и уведомлением в Telegram",
        "who_buys": "Любой бизнес без сайта",
    },
    "bot": {
        "name": "Telegram-бот под ключ",
        "price_test": "9 900 ₽",
        "price_full": "24 900 ₽",
        "price_pro": "49 900 ₽",
        "delivery": "3–5 дней",
        "desc": "Бот для записи / заказов / CRM / уведомлений. Любой сценарий.",
        "who_buys": "Салоны, кафе, фитнес, врачи, тренеры",
    },
    "content_pack": {
        "name": "AI-контент пакет 30 постов",
        "price_test": "5 900 ₽",
        "price_full": "9 900 ₽",
        "price_pro": "19 900 ₽",
        "delivery": "3 дня",
        "desc": "30 постов с AI-картинками + 5 Reels сценариев + шапка профиля",
        "who_buys": "Любой бизнес с соцсетями или без",
    },
    "logo": {
        "name": "Логотип + фирменный стиль",
        "price_test": "2 900 ₽",
        "price_full": "7 900 ₽",
        "price_pro": "14 900 ₽",
        "delivery": "24 часа",
        "desc": "3–5 вариантов логотипа, цветовая палитра, шрифт, визитка, фавикон",
        "who_buys": "Новый бизнес, ИП, ребрендинг",
    },
    "product_cards": {
        "name": "Карточки товаров (WB/Ozon)",
        "price_test": "990 ₽/карточка",
        "price_full": "700 ₽/карточка (от 10)",
        "price_pro": "500 ₽/карточка (от 30)",
        "delivery": "24–48 часов",
        "desc": "Фото-обработка фона + AI-описание + SEO-заголовок + инфографика",
        "who_buys": "Продавцы маркетплейсов WB/Ozon",
    },
    "promo_video": {
        "name": "Рекламный ролик 15–60 сек",
        "price_test": "4 900 ₽",
        "price_full": "9 900 ₽",
        "price_pro": "19 900 ₽",
        "delivery": "48 часов",
        "desc": "Скрипт + AI-видео Kling + озвучка Silero + монтаж. Для VK/TG/Avito.",
        "who_buys": "Любой бизнес для рекламы",
    },
    "seo_texts": {
        "name": "SEO-тексты пакетом",
        "price_test": "4 900 ₽ (10 текстов)",
        "price_full": "9 900 ₽ (30 текстов)",
        "price_pro": "19 900 ₽ (100 текстов)",
        "delivery": "24–48 часов",
        "desc": "Статьи, описания услуг, FAQ страницы — оптимизированные под SEO",
        "who_buys": "Сайты, блоги, агентства, интернет-магазины",
    },
    "translation": {
        "name": "Перевод + локализация",
        "price_test": "2 900 ₽",
        "price_full": "7 900 ₽",
        "price_pro": "19 900 ₽",
        "delivery": "24 часа",
        "desc": "RU↔EN↔DE↔FR. Сайт, документы, описания товаров, инструкции.",
        "who_buys": "Экспортёры, IT-компании, e-commerce",
    },
    "price_menu": {
        "name": "Прайс-лист / меню с дизайном",
        "price_test": "2 900 ₽",
        "price_full": "4 900 ₽",
        "price_pro": "7 900 ₽",
        "delivery": "24 часа",
        "desc": "Дизайн прайса с AI-картинками, PDF для печати + онлайн-версия для мессенджеров",
        "who_buys": "Кафе, салоны, мастера услуг, рестораны",
    },
    "reputation": {
        "name": "Управление репутацией",
        "price_test": "4 900 ₽",
        "price_full": "9 900 ₽",
        "price_pro": "19 900 ₽",
        "delivery": "3 дня",
        "desc": "Шаблоны ответов на отзывы + работа с негативом + стратегия рейтинга",
        "who_buys": "Бизнес с рейтингом ниже 4.0 на картах",
    },
    "travel_content": {
        "name": "Тревел-контент пакет",
        "price_test": "4 900 ₽",
        "price_full": "9 900 ₽",
        "price_pro": "19 900 ₽",
        "delivery": "3 дня",
        "desc": "Описания туров, маршруты, посты для TG/VK, AI-картинки локаций",
        "who_buys": "Турагентства, гостиницы, экскурсоводы",
    },
    "audit": {
        "name": "AI-аудит бизнеса",
        "price_test": "2 900 ₽",
        "price_full": "4 900 ₽",
        "price_pro": "9 900 ₽",
        "delivery": "24 часа",
        "desc": "PDF-отчёт: цифровые дыры + анализ конкурентов + план действий на 30 дней",
        "who_buys": "Владельцы которые хотят понять что делать",
    },
}

QUALIFICATION_QUESTIONS = [
    {"id": "q_source", "text": "Как сейчас приходят клиенты?", "options": ["Сарафан/знакомые", "Карты (2ГИС/Яндекс)", "Соцсети", "Сайт", "Авито/объявления"]},
    {"id": "q_online", "text": "Что есть онлайн?", "options": ["Ничего", "Только карты", "Соцсети", "Сайт", "Сайт + соцсети"]},
    {"id": "q_problem", "text": "Главная боль?", "options": ["Мало клиентов", "Теряем заявки", "Нет времени на маркетинг", "Плохой имидж", "Хотим автоматизацию"]},
    {"id": "q_budget", "text": "Готовы инвестировать?", "options": ["До 5 000 ₽", "5–15 000 ₽", "15–50 000 ₽", "50 000+ ₽", "Не знаю"]},
    {"id": "q_urgency", "text": "Когда нужен результат?", "options": ["Срочно (сегодня-завтра)", "На этой неделе", "В этом месяце", "Просто смотрим"]},
]

def qualify(
    has_website: bool,
    has_socials: bool,
    has_bot: bool,
    niche: str,
    rating: float = 0.0,
    source: str = "",
    q_answers: dict = None,
) -> list[dict]:
    """
    Возвращает список рекомендуемых продуктов, отсортированных по приоритету.
    """
    n = niche.lower()
    answers = q_answers or {}
    recs = []

    is_beauty = any(x in n for x in ["маникюр","салон","парикмахер","брови","косметол","массаж","эпиляц","тату"])
    is_food = any(x in n for x in ["кафе","доставка","ресторан","торты","кейтер"])
    is_fitness = any(x in n for x in ["фитнес","тренажер","тренер","йога"])
    is_marketplace = any(x in n for x in ["карточки","маркетплейс","wb","ozon","товар"])
    is_travel = any(x in n for x in ["тур","турагент","гостин","хостел","экскурс"])
    is_b2b = any(x in n for x in ["юрист","бухгалтер","реклама","печать","дизайн"])
    is_new = source in ("hh",) or (not has_website and not has_socials)

    # Нет сайта — лендинг в первую очередь
    if not has_website:
        recs.append({"product": PRODUCTS["landing"], "priority": 10, "reason": "Нет сайта — клиенты не могут оставить заявку"})

    # Нет соцсетей или мёртвые (VK source)
    if not has_socials or source == "vk":
        recs.append({"product": PRODUCTS["content_pack"], "priority": 9 if source == "vk" else 7, "reason": "Нет активных соцсетей — клиенты уходят к активным конкурентам"})

    # Нет бота — для подходящих ниш
    if not has_bot and (is_beauty or is_food or is_fitness):
        recs.append({"product": PRODUCTS["bot"], "priority": 8, "reason": f"Ниша {niche}: онлайн-запись критична для конверсии"})

    # Маркетплейс — карточки
    if is_marketplace:
        recs.append({"product": PRODUCTS["product_cards"], "priority": 10, "reason": "Карточки товаров напрямую влияют на продажи"})

    # Новый бизнес — логотип
    if is_new:
        recs.append({"product": PRODUCTS["logo"], "priority": 9, "reason": "Новый бизнес без фирменного стиля = нет доверия"})

    # Плохой рейтинг — репутация
    if rating > 0 and rating < 4.0:
        recs.append({"product": PRODUCTS["reputation"], "priority": 9, "reason": f"Рейтинг {rating} — клиенты видят и уходят"})

    # Туризм
    if is_travel:
        recs.append({"product": PRODUCTS["travel_content"], "priority": 8, "reason": "Тревел-контент увеличивает доверие и конверсию"})

    # HH source — контент вместо найма
    if source == "hh":
        recs.append({"product": PRODUCTS["content_pack"], "priority": 10, "reason": "Ищут SMM/дизайнера = хотят контент. Аутсорс дешевле найма."})

    # Видеоролик — если нет ни сайта ни соцсетей
    if not has_website and not has_socials:
        recs.append({"product": PRODUCTS["promo_video"], "priority": 6, "reason": "Видео для Avito/2GIS повышает доверие без сайта"})

    # Аудит — если ничего не знаем
    if not recs or answers.get("q_problem") == "Мало клиентов":
        recs.append({"product": PRODUCTS["audit"], "priority": 5, "reason": "Начать с аудита чтобы понять где теряются клиенты"})

    # Уникальные продукты по умолчанию
    if is_b2b:
        recs.append({"product": PRODUCTS["seo_texts"], "priority": 6, "reason": "B2B покупают через поиск — нужны SEO-тексты"})

    # Сортируем по приоритету
    recs.sort(key=lambda x: x["priority"], reverse=True)

    # Убираем дубли
    seen = set()
    unique = []
    for r in recs:
        key = r["product"]["name"]
        if key not in seen:
            seen.add(key)
            unique.append(r)

    return unique[:4]  # топ-4 продукта


def calc_deal(products_selected: list[str], tiers: dict[str, str] = None) -> dict:
    """Считает стоимость сделки."""
    tiers = tiers or {}
    total = 0
    lines = []
    for pid in products_selected:
        p = PRODUCTS.get(pid)
        if not p:
            continue
        tier = tiers.get(pid, "full")
        price_str = p.get(f"price_{tier}", p["price_full"])
        try:
            amount = int(price_str.replace("₽", "").replace(" ", "").replace("\u202f", "").split("/")[0].split("(")[0].strip())
            total += amount
            lines.append({"name": p["name"], "price": price_str, "amount": amount})
        except Exception:
            lines.append({"name": p["name"], "price": price_str, "amount": 0})
    return {"lines": lines, "total": total, "total_fmt": f"{total:,} ₽".replace(",", " ")}
