"""
Service for managing expired vacancies and resumes.
Automatically removes expired publications from channels.
"""

import asyncio
from datetime import datetime
from typing import List
from loguru import logger

from backend.models import Vacancy, Resume, Publication
from backend.services.telegram_publisher import telegram_publisher
from shared.constants import VacancyStatus, ResumeStatus


class ExpirationService:
    """Service for handling expired vacancies and resumes."""

    def __init__(self):
        self._task = None
        self._running = False

    async def check_and_remove_expired(self):
        """Check for expired vacancies and resumes and remove them from channels."""
        try:
            now = datetime.utcnow()
            logger.info("Checking for expired publications...")

            # Find expired vacancies
            logger.debug("Querying expired vacancies...")
            expired_vacancies = await Vacancy.find(
                Vacancy.expires_at != None,
                Vacancy.expires_at <= now,
                Vacancy.status != VacancyStatus.ARCHIVED,
                Vacancy.is_published == True
            ).to_list()
            logger.debug(f"Found {len(expired_vacancies)} expired vacancies")

            for vacancy in expired_vacancies:
                logger.info(f"Expiring vacancy {vacancy.id}: {vacancy.position}")

                # Find all publications for this vacancy
                publications = await Publication.find(
                    {"vacancy.$id": vacancy.id},
                    Publication.is_published == True,
                    Publication.is_deleted == False
                ).to_list()

                # Delete from channels
                for pub in publications:
                    try:
                        deleted = await telegram_publisher.delete_publication(pub)
                        if deleted:
                            logger.info(f"Deleted expired vacancy publication {pub.id} from channel {pub.channel_name}")
                    except Exception as e:
                        logger.error(f"Failed to delete publication {pub.id}: {e}")

                # Update vacancy status
                vacancy.status = VacancyStatus.ARCHIVED
                vacancy.is_published = False
                await vacancy.save()
                logger.success(f"Archived expired vacancy {vacancy.id}")

            # Find expired resumes
            logger.debug("Querying expired resumes...")
            expired_resumes = await Resume.find(
                Resume.expires_at != None,
                Resume.expires_at <= now,
                Resume.status != ResumeStatus.ARCHIVED,
                Resume.is_published == True
            ).to_list()
            logger.debug(f"Found {len(expired_resumes)} expired resumes")

            for resume in expired_resumes:
                logger.info(f"Expiring resume {resume.id}: {resume.full_name}")

                # Find all publications for this resume
                publications = await Publication.find(
                    {"resume.$id": resume.id},
                    Publication.is_published == True,
                    Publication.is_deleted == False
                ).to_list()

                # Delete from channels
                for pub in publications:
                    try:
                        deleted = await telegram_publisher.delete_publication(pub)
                        if deleted:
                            logger.info(f"Deleted expired resume publication {pub.id} from channel {pub.channel_name}")
                    except Exception as e:
                        logger.error(f"Failed to delete publication {pub.id}: {e}")

                # Update resume status
                resume.status = ResumeStatus.ARCHIVED
                resume.is_published = False
                await resume.save()
                logger.success(f"Archived expired resume {resume.id}")

            total_expired = len(expired_vacancies) + len(expired_resumes)
            if total_expired > 0:
                logger.success(f"Processed {total_expired} expired publications ({len(expired_vacancies)} vacancies, {len(expired_resumes)} resumes)")
            else:
                logger.info("No expired publications found")

        except Exception as e:
            import traceback
            logger.error(f"Error checking expired publications: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")

    async def _run_periodic_check(self):
        """Run periodic check for expired publications."""
        self._running = True
        logger.info("Starting expiration service (checking every hour)")

        while self._running:
            try:
                await self.check_and_remove_expired()
            except Exception as e:
                logger.error(f"Error in periodic expiration check: {e}")

            # Wait 1 hour before next check
            await asyncio.sleep(3600)  # 3600 seconds = 1 hour

    def start(self):
        """Start the expiration service."""
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._run_periodic_check())
            logger.success("Expiration service started")

    async def stop(self):
        """Stop the expiration service."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Expiration service stopped")


# Global instance
expiration_service = ExpirationService()
