# Kafka Lab — полный проход за 2-3 часа

Держи этот файл открытым рядом с терминалом. Идёшь сверху вниз.
Все команды `kafka-*.sh` запускаются **внутри контейнера** — поэтому везде префикс
`docker exec`. Это нормально: в проде ты так же заходишь на хост/под и запускаешь CLI.

Удобный алиас (вставь в терминал один раз за сессию):

```bash
alias kt='docker exec kafka-1 kafka-topics.sh --bootstrap-server kafka-1:9094'
alias kg='docker exec kafka-1 kafka-consumer-groups.sh --bootstrap-server kafka-1:9094'
```

---

## Фаза 0 — Поднять кластер (5 мин)

```bash
cd kafka-lab
docker compose up -d
docker compose ps          # все 4 контейнера должны быть Up
docker compose logs -f kafka-1   # глянь, что брокер стартовал без ошибок (Ctrl+C для выхода)
```

Открой в браузере ВМ **http://localhost:8080** — это Kafka UI. Там визуально видно
брокеры, топики, партиции, consumer groups и lag. Держи вкладку открытой: после каждой
команды смотри, как меняется картинка. Это резко ускоряет понимание.

Если контейнеры падают/рестартятся — смотри `docker compose logs kafka-1`.
Частая причина на слабой ВМ: не хватает памяти. Дай ВМ 4+ ГБ.

---

## Фаза 1 — Топики, партиции, репликация (30 мин)

### Создать топик
```bash
kt --create --topic orders --partitions 3 --replication-factor 3
kt --list
```

### Посмотреть устройство топика — ГЛАВНАЯ команда для мониторинга
```bash
kt --describe --topic orders
```
Читай вывод построчно. Для каждой партиции ты увидишь:
- **Leader** — какой брокер сейчас обслуживает запись/чтение этой партиции.
- **Replicas** — на каких брокерах лежат копии.
- **Isr** (In-Sync Replicas) — какие реплики синхронны с лидером **прямо сейчас**.

> Запомни намертво: **если Isr меньше Replicas — часть копий отстала или брокер лежит.**
> Это первый признак проблемы, который ты ищешь при инциденте. Когда `min.insync.replicas`
> не набирается, продюсер с `acks=all` начинает получать ошибки — и это уже инцидент с записью.

### Поиграть с конфигом retention
```bash
docker exec kafka-1 kafka-configs.sh --bootstrap-server kafka-1:9094 \
  --entity-type topics --entity-name orders --describe

# поставить retention 1 час (потом данные старше часа удаляются)
docker exec kafka-1 kafka-configs.sh --bootstrap-server kafka-1:9094 \
  --entity-type topics --entity-name orders \
  --alter --add-config retention.ms=3600000
```

### Чек-вопросы себе (ответь вслух)
- Сколько партиций — столько максимум параллельных консьюмеров в одной группе. Почему?
- Что произойдёт с порядком сообщений, если у топика 3 партиции? (порядок только внутри партиции)
- replication-factor=3 на 3 брокерах — сколько брокеров можем потерять без потери данных?

---

## Фаза 2 — Консольный поток (20 мин)

Два терминала рядом.

**Терминал A — продюсер:**
```bash
docker exec -it kafka-1 kafka-console-producer.sh \
  --bootstrap-server kafka-1:9094 --topic orders \
  --property "parse.key=true" --property "key.separator=:"
```
Пиши строки вида `tyumen:hello` и `moscow:test` (ключ:значение), Enter после каждой.

**Терминал B — консьюмер:**
```bash
docker exec -it kafka-1 kafka-console-consumer.sh \
  --bootstrap-server kafka-1:9094 --topic orders \
  --from-beginning --property print.key=true --property print.partition=true
```
Смотри: сообщения с одинаковым ключом всегда падают в одну партицию.

---

## Фаза 3 — Свой сервис на Python (30 мин)

```bash
cd app
# в одном терминале:
python3 consumer.py
# в другом:
python3 producer.py
```

Теперь запусти **второй** консьюмер в третьем терминале (`python3 consumer.py`) —
и наблюдай **ребаланс**: партиции перераспределятся между двумя консьюмерами группы.
В Kafka UI на вкладке Consumers это видно наглядно. Убей один консьюмер (Ctrl+C) —
партиции снова перейдут к выжившему. Это и есть отказоустойчивость обработки.

### Самая важная команда мониторинга — consumer lag
```bash
kg --describe --group orders-workers
```
Колонки: `CURRENT-OFFSET` (докуда прочитали), `LOG-END-OFFSET` (сколько всего есть),
**`LAG`** (разница — отставание). В банке ты будешь алертить именно по растущему lag.

**Сэмулируй рост lag:** останови консьюмер, оставь продюсер работать 30 секунд,
запусти `kg --describe` — увидишь, как LAG растёт. Запусти консьюмер обратно —
смотри, как он догоняет (lag падает к нулю).

---

## Фаза 4 — Поломки и диагностика (40 мин) — самое ценное

Здесь ты тренируешь именно то, за что тебе будут платить. На каждый сценарий:
сначала **сломай**, потом **найди симптом**, потом **почини**.

### Сценарий 1: упал брокер
```bash
docker stop kafka-2
kt --describe --topic orders
```
Симптом: для части партиций Isr сократился, лидерство переехало на живые брокеры
(leader election). В Kafka UI брокер подсветится. Данные доступны — RF=3 спасает.
```bash
docker start kafka-2          # чиним
kt --describe --topic orders  # смотри, как Isr восстанавливается до полного
```
> Вопрос на собес: "что такое under-replicated partitions?" — это и есть Isr < Replicas.

### Сценарий 2: потеря кворума контроллеров
```bash
docker stop kafka-2 kafka-3   # осталась 1 нода из 3 -> нет большинства
kt --list                     # команды зависают/таймаутят
```
Симптом: кластер не принимает метаданные-операции — нет кворума контроллеров (нужно >half).
```bash
docker start kafka-2 kafka-3  # кворум вернулся
```
> Вывод: для контроллеров всегда нечётное число (1,3,5) и нельзя терять большинство.

### Сценарий 3: запись при недостатке ISR
```bash
# поставим жёсткое требование
docker exec kafka-1 kafka-configs.sh --bootstrap-server kafka-1:9094 \
  --entity-type topics --entity-name orders \
  --alter --add-config min.insync.replicas=3
docker stop kafka-3           # теперь ISR=2 < 3
python3 app/producer.py       # с acks=all продюсер ловит ошибки NotEnoughReplicas
```
Симптом: запись валится, чтение работает. Классический инцидент "не пишется в Kafka".
```bash
docker start kafka-3
docker exec kafka-1 kafka-configs.sh --bootstrap-server kafka-1:9094 \
  --entity-type topics --entity-name orders \
  --alter --add-config min.insync.replicas=2
```

### Сценарий 4: "медленный консьюмер" / растущий lag
Останови консьюмер, дай продюсеру набить очередь, смотри `kg --describe`.
В реальности причины: упал консьюмер, тормозит БД-приёмник, не хватает партиций
для параллелизма. Тренируй цепочку: **алерт по lag -> describe group -> найти причину**.

### Сброс offset (бывает нужно при инцидентах)
```bash
# перемотать группу в начало (только когда консьюмеры остановлены)
kg --group orders-workers --topic orders --reset-offsets --to-earliest --execute
```

---

## Что ты должен уметь объяснить к концу (чек-лист)

- [ ] Нарисовать: topic -> partitions -> replicas (leader/follower), где живёт offset.
- [ ] Что такое ISR и under-replicated partitions, почему это первый сигнал инцидента.
- [ ] acks=0/1/all — чем платим за надёжность (latency vs durability).
- [ ] Что такое consumer group, как партиции делятся, что такое ребаланс.
- [ ] Consumer lag: что это, как смотреть, почему по нему алертят.
- [ ] min.insync.replicas: как недостаток ISR ломает запись с acks=all.
- [ ] KRaft-кворум контроллеров: почему нечётное число и нельзя терять большинство.

Когда закрыл чек-лист — `docker compose down` и переходи к k3s.
