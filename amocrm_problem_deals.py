import time
import requests

SUBDOMAIN = "example"                # example.amocrm.ru
TOKEN = "LONG_LIVED_TOKEN"           # долгосрочный токен приватной интеграции
BASE = f"https://{SUBDOMAIN}.amocrm.ru/api/v4"
HEADERS = {"Authorization": f"Bearer {TOKEN}"}
CLOSED_STATUSES = {142, 143}         # «Успешно реализовано», «Закрыто и не реализовано»

def fetch_all(endpoint: str, key: str, params: dict) -> list[dict]:
    """Забирает все страницы (по 250 записей), не превышая лимит ~7 запросов/сек."""
    items, page = [], 1
    while True:
        resp = requests.get(f"{BASE}/{endpoint}", headers=HEADERS, timeout=30,
                            params={**params, "page": page, "limit": 250})
        if resp.status_code == 204:  # пустой результат amoCRM отдаёт без тела
            break
        resp.raise_for_status()
        data = resp.json()
        items += data.get("_embedded", {}).get(key, [])
        if "next" not in data.get("_links", {}):  # последняя страница
            break
        page += 1
        time.sleep(0.15)             # пауза под лимит API
    return items

def problem_deals() -> list[dict]:
    """Возвращает открытые сделки без задач или с просроченной ближайшей задачей."""
    now = int(time.time())
    leads = [l for l in fetch_all("leads", "leads", {})          # только открытые сделки
             if l["status_id"] not in CLOSED_STATUSES]
    tasks = fetch_all("tasks", "tasks",                           # незавершённые задачи по сделкам
                      {"filter[entity_type]": "leads", "filter[is_completed]": 0})
    nearest_due = {}                 # id сделки -> срок ближайшей открытой задачи
    for t in tasks:
        lead_id, due = t["entity_id"], t["complete_till"]
        nearest_due[lead_id] = min(due, nearest_due.get(lead_id, due))
    result = []
    for lead in leads:               # отбираем сделки без задач или с просрочкой
        due = nearest_due.get(lead["id"])
        if due is None or due < now:
            result.append({"id": lead["id"], "name": lead["name"],
                           "manager_id": lead["responsible_user_id"],
                           "problem": "нет задач" if due is None else "просрочена"})
    return result

if __name__ == "__main__":           # запуск из консоли: печатает список проблемных сделок
    for d in problem_deals():
        print(f'{d["id"]:>10}  {d["problem"]:<10}  {d["name"]}')
