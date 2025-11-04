#!/bin/bash

# Скрипт для восстановления продакшн Telegram каналов
# Usage: ./scripts/restore_prod_channels.sh

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== CLICK - Восстановление продакшн каналов ===${NC}\n"

# Check if .env exists
if [ ! -f .env ]; then
    echo -e "${RED}✗ Файл .env не найден!${NC}"
    exit 1
fi

# Create backup
BACKUP_FILE=".env.backup.$(date +%Y%m%d_%H%M%S)"
cp .env "$BACKUP_FILE"
echo -e "${GREEN}✓ Создан бэкап: ${BACKUP_FILE}${NC}\n"

echo -e "${YELLOW}Восстанавливаю продакшн каналы...${NC}\n"

# Restore vacancy channels to production
sed -i.tmp "s|^CHANNEL_VACANCIES_BARMEN=.*|CHANNEL_VACANCIES_BARMEN=@horeca_msk1|" .env
sed -i.tmp "s|^CHANNEL_VACANCIES_WAITERS=.*|CHANNEL_VACANCIES_WAITERS=@horeca_msk2|" .env
sed -i.tmp "s|^CHANNEL_VACANCIES_COOKS=.*|CHANNEL_VACANCIES_COOKS=@horeca_povara1|" .env
sed -i.tmp "s|^CHANNEL_VACANCIES_BARISTA=.*|CHANNEL_VACANCIES_BARISTA=@horeca_barista|" .env
sed -i.tmp "s|^CHANNEL_VACANCIES_ADMIN=.*|CHANNEL_VACANCIES_ADMIN=@horeca_admin_man|" .env
sed -i.tmp "s|^CHANNEL_VACANCIES_SUPPORT=.*|CHANNEL_VACANCIES_SUPPORT=@horeca5|" .env
sed -i.tmp "s|^CHANNEL_VACANCIES_OTHER=.*|CHANNEL_VACANCIES_OTHER=@horeca4|" .env
sed -i.tmp "s|^CHANNEL_VACANCIES_GENERAL=.*|CHANNEL_VACANCIES_GENERAL=@HoReCaMBA|" .env
echo -e "${GREEN}✓ Каналы вакансий восстановлены${NC}"

# Restore resume channels to production
sed -i.tmp "s|^CHANNEL_RESUMES_BARMEN=.*|CHANNEL_RESUMES_BARMEN=@horeca_msk1|" .env
sed -i.tmp "s|^CHANNEL_RESUMES_WAITERS=.*|CHANNEL_RESUMES_WAITERS=@horeca_msk2|" .env
sed -i.tmp "s|^CHANNEL_RESUMES_COOKS=.*|CHANNEL_RESUMES_COOKS=@horeca_povara1|" .env
sed -i.tmp "s|^CHANNEL_RESUMES_BARISTA=.*|CHANNEL_RESUMES_BARISTA=@horeca_barista|" .env
sed -i.tmp "s|^CHANNEL_RESUMES_ADMIN=.*|CHANNEL_RESUMES_ADMIN=@horeca_admin_man|" .env
sed -i.tmp "s|^CHANNEL_RESUMES_SUPPORT=.*|CHANNEL_RESUMES_SUPPORT=@horeca5|" .env
sed -i.tmp "s|^CHANNEL_RESUMES_OTHER=.*|CHANNEL_RESUMES_OTHER=@horeca4|" .env
sed -i.tmp "s|^CHANNEL_RESUMES_GENERAL=.*|CHANNEL_RESUMES_GENERAL=@HoReCaMBA|" .env
echo -e "${GREEN}✓ Каналы резюме восстановлены${NC}"

# Remove temp files
rm -f .env.tmp

echo -e "\n${GREEN}=== Восстановление завершено! ===${NC}\n"

# Show configured channels
echo -e "${YELLOW}Текущие продакшн каналы:${NC}"
echo -e "${GREEN}Вакансии:${NC}"
echo "  - Бармены: @horeca_msk1"
echo "  - Официанты: @horeca_msk2"
echo "  - Повара: @horeca_povara1"
echo "  - Баристы: @horeca_barista"
echo "  - Управление: @horeca_admin_man"
echo "  - Вспомогательный персонал: @horeca5"
echo "  - Прочие: @horeca4"
echo "  - Общий: @HoReCaMBA"

echo -e "\n${GREEN}Резюме:${NC}"
echo "  (те же каналы)"

echo -e "\n${YELLOW}⚠️  ВАЖНО: Убедитесь что:${NC}"
echo "1. Бот добавлен во ВСЕ продакшн каналы как администратор"
echo "2. У бота есть права на публикацию во всех каналах"
echo "3. Вы готовы публиковать в продакшн"

echo -e "\n${YELLOW}Следующие шаги:${NC}"
echo "1. Проверьте права бота в каналах"
echo "2. Перезапустите приложение:"
echo -e "   ${GREEN}docker-compose restart${NC}"
echo "   или"
echo -e "   ${GREEN}docker-compose down && docker-compose up -d${NC}"
echo ""
echo "3. Проверьте публикацию с тестовой вакансией/резюме"

echo -e "\n${YELLOW}Для отмены восстановления:${NC}"
echo -e "   ${GREEN}cp ${BACKUP_FILE} .env${NC}"

echo -e "\n${GREEN}Продакшн каналы восстановлены! ✅${NC}"
