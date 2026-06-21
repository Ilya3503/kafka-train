# k8s-train — учебный репозиторий для тренировки kubectl и траблшутинга

Полный набор манифестов для отработки работы с Kubernetes (k3s/minikube).
Разворачивается слоями. Каждый слой — отдельная папка.

## Что внутри
- `01-app/`      — простое приложение (nginx) + Service. Базовый Deployment.
- `02-config/`   — то же приложение, но конфиг вынесен в ConfigMap.
- `03-database/` — PostgreSQL как StatefulSet с персистентным томом (PVC).
- `04-kafka/`    — один брокер Kafka (KRaft) как StatefulSet + Service.
- `05-broken/`   — НАМЕРЕННО сломанные манифесты для тренировки диагностики.

## Порядок запуска

```bash
# 1. Приложение
kubectl apply -f 01-app/
kubectl get all -l app=web

# 2. Конфиг (пересоздаёт web с конфигом из ConfigMap)
kubectl apply -f 02-config/

# 3. База данных
kubectl apply -f 03-database/
kubectl get statefulset,pvc,pods -l app=postgres

# 4. Kafka
kubectl apply -f 04-kafka/
kubectl get statefulset,pods -l app=kafka

# Посмотреть всё разом
kubectl get all
```

## Удаление
```bash
kubectl delete -f 04-kafka/ -f 03-database/ -f 02-config/ -f 01-app/
# тома (PVC) удаляются отдельно, они переживают delete намеренно:
kubectl get pvc
kubectl delete pvc --all
```

## Тренировка диагностики
Папка `05-broken/` — это сломанные манифесты. Применяй по одному, диагностируй
через `kubectl describe` и `kubectl logs`, чини. Подробности в `05-broken/README.md`.

## Базовые команды диагностики (шпаргалка)
```bash
kubectl get pods -o wide              # статус и на какой ноде
kubectl describe pod <pod>            # события (Events!), состояние, пробы
kubectl logs <pod>                    # логи приложения
kubectl logs <pod> --previous         # логи упавшего контейнера (CrashLoop)
kubectl logs <pod> -f                 # следить в реальном времени
kubectl exec -it <pod> -- sh          # зайти внутрь (если есть шелл)
kubectl get events --sort-by=.lastTimestamp   # все события кластера по времени
```
