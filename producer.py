#!/usr/bin/env python3
"""
Учебный продюсер. Шлёт события "заказов" в топик orders.
Запуск:  python3 producer.py
Останов: Ctrl+C

Что здесь важно для инженера:
- acks="all" — продюсер ждёт подтверждения от всех ISR. Это про надёжность
  (durability). На собесе/в проде часто спрашивают разницу acks=0/1/all.
- callback на success/failure — так ты видишь, что происходит при поломке брокера.
- ключ сообщения (key) определяет партицию: одинаковый key -> одна партиция -> порядок.
"""

import json
import time
import random
from kafka import KafkaProducer
from kafka.errors import KafkaError

BOOTSTRAP = "localhost:9092,localhost:9095,localhost:9096"
TOPIC = "orders"

producer = KafkaProducer(
    bootstrap_servers=BOOTSTRAP.split(","),
    value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    key_serializer=lambda k: k.encode("utf-8"),
    acks="all",          # ждём подтверждения от всех in-sync реплик
    retries=5,           # ретраи при временных сбоях
    linger_ms=10,        # небольшая батчинг-задержка
)

def on_success(meta):
    print(f"  OK   -> partition={meta.partition} offset={meta.offset}")

def on_error(exc):
    print(f"  FAIL -> {exc}")

def main():
    i = 0
    cities = ["tyumen", "moscow", "kazan", "spb"]
    print(f"Шлю в топик '{TOPIC}'. Ctrl+C для остановки.")
    try:
        while True:
            i += 1
            city = random.choice(cities)
            event = {
                "order_id": i,
                "city": city,
                "amount": round(random.uniform(100, 5000), 2),
                "ts": time.time(),
            }
            # ключ = city -> заказы одного города идут в одну партицию (сохраняется порядок)
            future = producer.send(TOPIC, key=city, value=event)
            future.add_callback(on_success).add_errback(on_error)
            print(f"send #{i} city={city}")
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nflush & close...")
        producer.flush()
        producer.close()

if __name__ == "__main__":
    main()
