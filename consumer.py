#!/usr/bin/env python3
"""
Учебный консьюмер. Читает из топика orders в составе consumer group.
Запуск:  python3 consumer.py            (группа orders-workers)
Запуск второй копии в другом терминале -> увидишь ребаланс и распределение партиций.

Что важно для инженера:
- group_id — несколько консьюмеров с одним group_id делят партиции между собой.
  Это и есть горизонтальное масштабирование обработки.
- enable_auto_commit=False + ручной commit — так ты контролируешь "ровно/хотя бы раз".
  Если упасть до commit — сообщение прочитается заново (at-least-once).
- auto_offset_reset="earliest" — с какого места читать, если offset группы неизвестен.
- consumer lag (отставание) — главная метрика мониторинга. Растёт lag = консьюмеры
  не успевают за продюсером. Это то, на что ты будешь смотреть в банке каждый день.
"""

import json
from kafka import KafkaConsumer

BOOTSTRAP = "localhost:9092,localhost:9095,localhost:9096"
TOPIC = "orders"
GROUP = "orders-workers"

consumer = KafkaConsumer(
    TOPIC,
    bootstrap_servers=BOOTSTRAP.split(","),
    group_id=GROUP,
    value_deserializer=lambda v: json.loads(v.decode("utf-8")),
    key_deserializer=lambda k: k.decode("utf-8") if k else None,
    enable_auto_commit=False,       # коммитим вручную
    auto_offset_reset="earliest",
)

def main():
    print(f"Читаю '{TOPIC}' в группе '{GROUP}'. Ctrl+C для остановки.")
    try:
        for msg in consumer:
            print(
                f"recv part={msg.partition} off={msg.offset} "
                f"key={msg.key} amount={msg.value.get('amount')}"
            )
            # здесь была бы "обработка"; после успешной обработки коммитим offset
            consumer.commit()
    except KeyboardInterrupt:
        print("\nclose...")
        consumer.close()

if __name__ == "__main__":
    main()
