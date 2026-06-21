# 05-broken — тренировка диагностики

Применяй по ОДНОМУ, диагностируй сам, потом читай разбор. Не подсматривай сразу.
Цель — натренировать рефлекс: симптом -> правильная команда -> причина -> починка.

---

## Поломка 1 — битый образ
```bash
kubectl apply -f 01-bad-image.yaml
kubectl get pods -l drill=broken-image          # какой статус?
kubectl describe pod -l drill=broken-image      # читай Events внизу
```
Что увидишь: статус `ErrImagePull` -> `ImagePullBackOff`. В Events — что образ
не скачался. Причина: несуществующий тег `nginx:this-tag-does-not-exist-999`.
Починка: исправить тег на реальный (`nginx:1.27`) и применить заново.
```bash
kubectl delete -f 01-bad-image.yaml
```

## Поломка 2 — CrashLoopBackOff
```bash
kubectl apply -f 02-crashloop.yaml
kubectl get pods -l drill=broken-crash          # смотри Restart Count — растёт
kubectl logs -l drill=broken-crash              # логи ТЕКУЩего запуска
kubectl logs <конкретный-под> --previous        # логи УПАВШего контейнера — вот ключ
kubectl describe pod -l drill=broken-crash      # Last State: Terminated, Exit Code 1
```
Что увидишь: контейнер стартует, падает с exit 1, k8s перезапускает по нарастающей
паузе (back-off). `--previous` показывает, что приложение писало перед смертью.
Причина: команда намеренно делает `exit 1`. В реальности так выглядит падение
приложения на старте (битый конфиг, нет соединения с БД и т.п.).
```bash
kubectl delete -f 02-crashloop.yaml
```

## Поломка 3 — Service не находит поды
```bash
kubectl apply -f 03-bad-selector.yaml
kubectl get pods -l app=real-label              # поды Running и здоровы
kubectl get endpoints broken-svc                # ПУСТО — вот главный признак
kubectl describe svc broken-svc                 # сравни Selector с лейблами подов
```
Что увидишь: поды живые, но у сервиса нет endpoints, значит трафик идти некуда.
Причина: `selector: app=wrong-label` в Service не совпадает с `app=real-label`
у подов. Починка: привести selector сервиса к лейблам подов.
Это очень частый прод-инцидент: "приложение живое, но недоступно".
```bash
kubectl delete -f 03-bad-selector.yaml
```

## Поломка 4 — под не помещается на ноду
```bash
kubectl apply -f 04-unschedulable.yaml
kubectl get pods -l drill=broken-resources      # висит в Pending
kubectl describe pod -l drill=broken-resources  # Events: FailedScheduling
kubectl describe node                           # сколько памяти реально есть
```
Что увидишь: под в `Pending`, в Events — `Insufficient memory`, планировщик не может
найти ноду. Причина: запрошено 500Gi памяти. Починка: выставить адекватный request.
```bash
kubectl delete -f 04-unschedulable.yaml
```

---

## Общий рефлекс диагностики
1. `kubectl get pods` — какой статус? (Pending / ImagePullBackOff / CrashLoop / Running)
2. Статус подсказывает направление:
   - Pending           -> планирование/ресурсы -> describe pod (Events), describe node
   - ImagePullBackOff   -> образ -> describe pod (Events)
   - CrashLoopBackOff   -> приложение падает -> logs --previous
   - Running, но не работает -> сеть/сервис -> get endpoints, describe svc
3. `kubectl describe` — почему (Events, Last State).
4. `kubectl logs [--previous]` — что сказало приложение.
