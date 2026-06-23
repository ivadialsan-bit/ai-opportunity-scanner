from __future__ import annotations
import json, time, random, urllib.request, urllib.parse, urllib.error, os
from dataclasses import dataclass, field
from datetime import datetime, timezone

@dataclass
class VKLead:
    source: str = "vk"
    city: str = ""
    niche: str = ""
    name: str = ""
    phone: str = ""
    website: str = ""
    address: str = ""
    url: str = ""
    email: str = ""
    last_post_days: int = 0
    members: int = 0
    lead_score: int = 0
    opportunity_flags: list = field(default_factory=list)
    suggested_offer: str = ""
    first_message: str = ""

HEADERS = {"User-Agent": "Mozilla/5.0 Chrome/122.0.0.0 Safari/537.36"}

VK_NICHE_QUERIES = {
    "красота": ["маникюр", "салон красоты", "косметолог", "парикмахер"],
    "сантехника": ["сантехник", "водопровод"],
    "электрика": ["электрик", "электромонтаж"],
    "ремонт": ["ремонт квартир", "отделка"],
    "автосервис": ["автосервис", "шиномонтаж"],
    "фитнес": ["фитнес", "тренажерный зал"],
    "кафе": ["кафе", "доставка еды", "ресторан"],
    "клининг": ["уборка", "клининг"],
    "юрист": ["юрист", "адвокат"],
    "стоматология": ["стоматология", "зубной"],
    "карточки товаров": ["интернет магазин", "товары"],
    "туризм": ["турагентство", "туры"],
}

def _days_since(ts: int) -> int:
    if not ts:
        return 9999
    now = datetime.now(timezone.utc).timestamp()
    return int((now - ts) / 86400)

def _score_vk(lead: VKLead) -> VKLead:
    score = 30
    flags = ["source_vk"]
    if lead.last_post_days > 60:
        score += 30; flags.append("dead_group_hot")
    elif lead.last_post_days > 30:
        score += 20; flags.append("inactive_group")
    if 50 <= lead.members <= 5000:
        score += 20; flags.append("small_business_size")
    elif lead.members > 5000:
        score += 10; flags.append("medium_business")
    if lead.phone:
        score += 10; flags.append("phone_present")
    if not lead.website:
        score += 10; flags.append("no_website")
    lead.lead_score = min(score, 100)
    lead.opportunity_flags = flags
    return lead

def _build_vk_offer(lead: VKLead) -> VKLead:
    days = lead.last_post_days
    name = lead.name or "ваша группа"
    if days > 60:
        lead.suggested_offer = f"Реанимация соцсети — 30 постов за 3 дня"
        lead.first_message = (
            f"Здравствуйте! Нашёл группу «{name}» ВКонтакте — последний пост был {days} дней назад. "
            f"Клиенты проверяют активность перед обращением — видят тишину, уходят к конкурентам. "
            f"Сделаю 30 AI-постов с картинками за 3 дня. От 7 900 ₽. Показать примеры?"
        )
    else:
        lead.suggested_offer = "Усиление контента — AI-посты + Reels"
        lead.first_message = (
            f"Здравствуйте! Вижу группу «{name}» — контент можно усилить AI-картинками и Reels. "
            f"Пакет 30 постов + 5 Reels сценариев за 3 дня. От 9 900 ₽. Интересно?"
        )
    return lead

def scan_vk(city: str, niche: str, limit: int = 20, access_token: str = "") -> tuple[list[VKLead], str]:
    token = access_token or os.getenv("VK_TOKEN", "")
    if not token:
        return [], "VK_TOKEN не задан. Добавь в .env: VK_TOKEN=ваш_токен"

    queries = VK_NICHE_QUERIES.get(niche.lower(), [niche])
    leads: list[VKLead] = []
    seen: set[str] = set()
    note = ""

    for q in queries:
        if len(leads) >= limit:
            break
        params = {
            "q": f"{q} {city}",
            "type": "group",
            "count": "20",
            "sort": "0",
            "v": "5.131",
            "access_token": token,
        }
        url = "https://api.vk.com/method/groups.search?" + urllib.parse.urlencode(params)
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=12) as r:
                data = json.loads(r.read().decode("utf-8"))

            groups = data.get("response", {}).get("items", [])
            for g in groups:
                gid = g.get("id", 0)
                name = (g.get("name") or "").strip()
                if not name or name.lower() in seen:
                    continue
                seen.add(name.lower())

                # проверяем последний пост
                wall_params = {
                    "owner_id": f"-{gid}", "count": "1",
                    "v": "5.131", "access_token": token,
                }
                wall_url = "https://api.vk.com/method/wall.get?" + urllib.parse.urlencode(wall_params)
                last_post_days = 9999
                try:
                    req2 = urllib.request.Request(wall_url, headers=HEADERS)
                    with urllib.request.urlopen(req2, timeout=8) as r2:
                        wall = json.loads(r2.read().decode("utf-8"))
                    items = wall.get("response", {}).get("items", [])
                    if items:
                        last_post_days = _days_since(items[0].get("date", 0))
                except Exception:
                    pass

                # пропускаем активные группы (посты < 14 дней)
                if last_post_days < 14:
                    continue

                phone = (g.get("phone") or "").strip()
                site = (g.get("site") or "").strip()
                if site and not site.startswith("http"):
                    site = "https://" + site

                lead = VKLead(
                    city=city, niche=niche,
                    name=name,
                    phone=phone,
                    website=site,
                    url=f"https://vk.com/club{gid}",
                    members=g.get("members_count", 0),
                    last_post_days=last_post_days,
                )
                lead = _score_vk(lead)
                lead = _build_vk_offer(lead)
                leads.append(lead)
                if len(leads) >= limit:
                    break

                time.sleep(random.uniform(0.2, 0.5))

        except Exception as ex:
            note = f"VK ошибка: {ex}"
            break

    leads.sort(key=lambda x: x.lead_score, reverse=True)
    return leads[:limit], note
