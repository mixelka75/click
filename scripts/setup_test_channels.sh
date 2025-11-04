#!/bin/bash

# Скрипт для быстрой настройки тестовых Telegram каналов
# Usage: ./scripts/setup_test_channels.sh @your_test_channel

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== CLICK - Настройка тестовых каналов ===${NC}\n"

# Check if .env exists
if [ ! -f .env ]; then
    echo -e "${YELLOW}Файл .env не найден. Создаю из .env.example...${NC}"
    cp .env.example .env
    echo -e "${GREEN}✓ Файл .env создан${NC}\n"
fi

# Get test channel from argument or prompt
if [ -z "$1" ]; then
    echo -e "${YELLOW}Введите username вашего тестового канала (например: @my_test_channel):${NC}"
    read -r TEST_CHANNEL
else
    TEST_CHANNEL=$1
fi

# Validate channel format
if [[ ! $TEST_CHANNEL =~ ^@[a-zA-Z0-9_]+$ ]] && [[ ! $TEST_CHANNEL =~ ^-[0-9]+$ ]]; then
    echo -e "${RED}✗ Неверный формат канала!${NC}"
    echo "Используйте @username для public каналов или -1001234567890 для private"
    exit 1
fi

echo -e "\n${GREEN}Настраиваю канал: ${TEST_CHANNEL}${NC}\n"

# Create backup
BACKUP_FILE=".env.backup.$(date +%Y%m%d_%H%M%S)"
cp .env "$BACKUP_FILE"
echo -e "${GREEN}✓ Создан бэкап: ${BACKUP_FILE}${NC}"

# Replace all vacancy channels
echo -e "${YELLOW}Заменяю каналы для вакансий...${NC}"
sed -i.tmp "s|^CHANNEL_VACANCIES_BARMEN=.*|CHANNEL_VACANCIES_BARMEN=${TEST_CHANNEL}|" .env
sed -i.tmp "s|^CHANNEL_VACANCIES_WAITERS=.*|CHANNEL_VACANCIES_WAITERS=${TEST_CHANNEL}|" .env
sed -i.tmp "s|^CHANNEL_VACANCIES_COOKS=.*|CHANNEL_VACANCIES_COOKS=${TEST_CHANNEL}|" .env
sed -i.tmp "s|^CHANNEL_VACANCIES_BARISTA=.*|CHANNEL_VACANCIES_BARISTA=${TEST_CHANNEL}|" .env
sed -i.tmp "s|^CHANNEL_VACANCIES_ADMIN=.*|CHANNEL_VACANCIES_ADMIN=${TEST_CHANNEL}|" .env
sed -i.tmp "s|^CHANNEL_VACANCIES_SUPPORT=.*|CHANNEL_VACANCIES_SUPPORT=${TEST_CHANNEL}|" .env
sed -i.tmp "s|^CHANNEL_VACANCIES_OTHER=.*|CHANNEL_VACANCIES_OTHER=${TEST_CHANNEL}|" .env
sed -i.tmp "s|^CHANNEL_VACANCIES_GENERAL=.*|CHANNEL_VACANCIES_GENERAL=${TEST_CHANNEL}|" .env
echo -e "${GREEN}✓ Каналы вакансий настроены${NC}"

# Replace all resume channels
echo -e "${YELLOW}Заменяю каналы для резюме...${NC}"
sed -i.tmp "s|^CHANNEL_RESUMES_BARMEN=.*|CHANNEL_RESUMES_BARMEN=${TEST_CHANNEL}|" .env
sed -i.tmp "s|^CHANNEL_RESUMES_WAITERS=.*|CHANNEL_RESUMES_WAITERS=${TEST_CHANNEL}|" .env
sed -i.tmp "s|^CHANNEL_RESUMES_COOKS=.*|CHANNEL_RESUMES_COOKS=${TEST_CHANNEL}|" .env
sed -i.tmp "s|^CHANNEL_RESUMES_BARISTA=.*|CHANNEL_RESUMES_BARISTA=${TEST_CHANNEL}|" .env
sed -i.tmp "s|^CHANNEL_RESUMES_ADMIN=.*|CHANNEL_RESUMES_ADMIN=${TEST_CHANNEL}|" .env
sed -i.tmp "s|^CHANNEL_RESUMES_SUPPORT=.*|CHANNEL_RESUMES_SUPPORT=${TEST_CHANNEL}|" .env
sed -i.tmp "s|^CHANNEL_RESUMES_OTHER=.*|CHANNEL_RESUMES_OTHER=${TEST_CHANNEL}|" .env
sed -i.tmp "s|^CHANNEL_RESUMES_GENERAL=.*|CHANNEL_RESUMES_GENERAL=${TEST_CHANNEL}|" .env
echo -e "${GREEN}✓ Каналы резюме настроены${NC}"

# Remove temp files
rm -f .env.tmp

echo -e "\n${GREEN}=== Настройка завершена! ===${NC}\n"

# Show configured channels
echo -e "${YELLOW}Настроенные каналы:${NC}"
grep "^CHANNEL_" .env | head -8

echo -e "\n${YELLOW}⚠️  ВАЖНО: Убедитесь что:${NC}"
echo "1. Канал ${TEST_CHANNEL} создан в Telegram"
echo "2. Бот добавлен в канал как администратор"
echo "3. У бота есть права на публикацию сообщений"

echo -e "\n${YELLOW}Следующие шаги:${NC}"
echo "1. Перезапустите приложение:"
echo -e "   ${GREEN}docker-compose restart${NC}"
echo "   или"
echo -e "   ${GREEN}docker-compose down && docker-compose up -d${NC}"
echo ""
echo "2. Проверьте публикацию:"
echo "   - Откройте бота в Telegram"
echo "   - Создайте и опубликуйте вакансию/резюме"
echo "   - Проверьте канал ${TEST_CHANNEL}"
echo ""
echo "3. Для возврата к продакшн каналам:"
echo -e "   ${GREEN}./scripts/restore_prod_channels.sh${NC}"
echo "   или восстановите из бэкапа:"
echo -e "   ${GREEN}cp ${BACKUP_FILE} .env${NC}"

echo -e "\n${GREEN}Готово! Можно тестировать 🚀${NC}"
