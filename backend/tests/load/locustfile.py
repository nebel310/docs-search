import os
import random
from urllib.parse import urlencode

from locust import FastHttpUser, between, task


BASE_URL = os.environ.get("LOAD_BASE_URL", "http://localhost:8000")
TOTAL_DOCUMENTS = int(os.environ.get("LOAD_TOTAL_DOCUMENTS", "1500"))

HIT_QUERIES = [
    "информации",
    "BTS",
    "Мерседес",
    "музыка",
    "Спринтер",
    "новый год",
    "конкурс",
    "модель",
]

MISS_QUERIES = [
    "asdfghjkl",
    "qwertyuiop",
    "zzzzzzzzz",
    "нетакогослова",
    "unmatched-query-1234",
]


def random_query() -> str:
    """Возвращает запрос из хит- или мисс-набора"""
    if random.random() < 0.8:
        return random.choice(HIT_QUERIES)
    return random.choice(MISS_QUERIES)


def random_doc_id() -> int:
    """Возвращает случайный id документа из загруженного диапазона"""
    return random.randint(1, TOTAL_DOCUMENTS)


class SearchUser(FastHttpUser):
    """Нагрузка на поисковый эндпоинт"""

    host = BASE_URL
    weight = 8
    wait_time = between(0.01, 0.05)
    network_timeout = 10.0
    connection_timeout = 10.0

    @task(9)
    def search(self) -> None:
        """Ищет документы по случайному запросу"""
        params = urlencode({"q": random_query()})
        self.client.get(f"/search?{params}", name="/search")

    @task(1)
    def search_with_limit(self) -> None:
        """Ищет документы с ограничением выдачи"""
        params = urlencode({"q": random_query(), "limit": 5})
        self.client.get(f"/search?{params}", name="/search?limit=5")


class DocumentUser(FastHttpUser):
    """Нагрузка на получение документа по id"""

    host = BASE_URL
    weight = 2
    wait_time = between(0.01, 0.05)
    network_timeout = 10.0
    connection_timeout = 10.0

    @task
    def get_document(self) -> None:
        """Запрашивает документ по случайному id"""
        self.client.get(
            f"/documents/{random_doc_id()}",
            name="/documents/[id]",
        )