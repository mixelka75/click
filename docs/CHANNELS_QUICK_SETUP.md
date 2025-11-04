# 🚀 Быстрая настройка Telegram каналов для тестирования

## 3 шага для начала тестирования

### 1️⃣ Создайте тестовый канал (1 минута)
```
Telegram → New Channel → "My Test Channel" → Public → @my_test_click
```
**Важно:** Запомните username (например: `@my_test_click`)

### 2️⃣ Добавьте бота в канал (30 секунд)
```
Канал → Administrators → Add Administrator → [ваш бот]
✅ Post Messages (Публиковать сообщения) - обязательно!
```

### 3️⃣ Обновите .env (1 минута)
```bash
# Откройте .env и замените ВСЕ каналы на ваш тестовый:
CHANNEL_VACANCIES_BARMEN=@my_test_click
CHANNEL_VACANCIES_WAITERS=@my_test_click
CHANNEL_VACANCIES_COOKS=@my_test_click
CHANNEL_VACANCIES_BARISTA=@my_test_click
CHANNEL_VACANCIES_ADMIN=@my_test_click
CHANNEL_VACANCIES_SUPPORT=@my_test_click
CHANNEL_VACANCIES_OTHER=@my_test_click
CHANNEL_VACANCIES_GENERAL=@my_test_click

CHANNEL_RESUMES_BARMEN=@my_test_click
CHANNEL_RESUMES_WAITERS=@my_test_click
CHANNEL_RESUMES_COOKS=@my_test_click
CHANNEL_RESUMES_BARISTA=@my_test_click
CHANNEL_RESUMES_ADMIN=@my_test_click
CHANNEL_RESUMES_SUPPORT=@my_test_click
CHANNEL_RESUMES_OTHER=@my_test_click
CHANNEL_RESUMES_GENERAL=@my_test_click
```

**Быстрая замена через sed (Linux/Mac):**
```bash
# Замените YOUR_TEST_CHANNEL на ваш канал
sed -i 's/@horeca_[a-z0-9_]*/@YOUR_TEST_CHANNEL/g' .env
sed -i 's/@HoReCaMBA/@YOUR_TEST_CHANNEL/g' .env
```

### 4️⃣ Перезапустите и тестируйте
```bash
docker-compose restart
# Или
docker-compose down && docker-compose up -d
```

## ✅ Тест публикации

1. Откройте бота → `/start`
2. Выберите роль (работодатель или соискатель)
3. Создайте вакансию/резюме
4. Нажмите "Опубликовать"
5. **Проверьте ваш канал** - должен появиться пост!

## 🔧 Проблемы?

### Публикация не работает?
```bash
# Проверьте права бота в канале:
# Канал → Administrators → [ваш бот] → должна быть галочка "Post Messages"

# Проверьте логи:
docker-compose logs backend | grep -i "publish"
docker-compose logs bot | grep -i "publish"

# Проверьте переменные окружения:
docker-compose exec backend env | grep CHANNEL
```

### Private канал?
Используйте chat_id вместо @username:
```bash
# Добавьте @getmyid_bot в канал
# Форвардните сообщение из канала боту
# Используйте полученный ID (например: -1001234567890)
CHANNEL_VACANCIES_GENERAL=-1001234567890
```

## 📝 Возврат к продакшн каналам

```bash
# Восстановите каналы из .env.example:
grep CHANNEL .env.example > channels_backup.txt
# Скопируйте значения обратно в .env
```

Или вручную замените на продакшн каналы:
- @horeca_msk1 (Бармены)
- @horeca_msk2 (Официанты)
- @horeca_povara1 (Повара)
- @horeca_barista (Баристы)
- @horeca_admin_man (Управление)
- @horeca5 (Вспомогательный персонал)
- @HoReCaMBA (Общий канал)

## 📚 Полная документация

- [TESTING.md](TESTING.md) - подробная инструкция по тестированию
- [SETUP.md](SETUP.md) - полная документация по настройке
- [.env.example](.env.example) - пример конфигурации

---

**💡 Совет:** Для тестирования достаточно одного канала. Все публикации будут идти туда, и вы сможете проверить форматирование и работу кнопок.
