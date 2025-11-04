"""
Analytics service for vacancies and resumes.
"""

from typing import Dict, List, Optional
from datetime import datetime, timedelta
from loguru import logger

from backend.models import User, Vacancy, Resume, Response
from shared.constants import ResponseStatus


class AnalyticsService:
    """Service for calculating analytics and statistics."""

    async def get_vacancy_analytics(self, vacancy: Vacancy) -> Dict:
        """Get detailed analytics for a vacancy."""
        try:
            # Calculate days active
            days_active = 0
            if vacancy.published_at:
                days_active = (datetime.utcnow() - vacancy.published_at).days

            # Get responses breakdown
            responses = await Response.find(
                Response.vacancy.id == vacancy.id
            ).to_list()

            responses_by_status = {
                "pending": 0,
                "viewed": 0,
                "invited": 0,
                "accepted": 0,
                "rejected": 0
            }

            for response in responses:
                status = response.status.value if hasattr(response.status, 'value') else response.status
                if status in responses_by_status:
                    responses_by_status[status] += 1

            # Calculate conversion rate
            conversion_rate = 0
            if vacancy.views_count > 0:
                conversion_rate = (vacancy.responses_count / vacancy.views_count) * 100

            # Calculate response rate (accepted / total responses)
            response_rate = 0
            if vacancy.responses_count > 0:
                response_rate = (responses_by_status["accepted"] / vacancy.responses_count) * 100

            # Average time to first response
            avg_response_time = None
            if responses and vacancy.published_at:
                response_times = []
                for r in responses:
                    if r.created_at:
                        time_diff = (r.created_at - vacancy.published_at).total_seconds() / 3600  # hours
                        response_times.append(time_diff)

                if response_times:
                    avg_response_time = sum(response_times) / len(response_times)

            return {
                "vacancy_id": str(vacancy.id),
                "position": vacancy.position,
                "status": vacancy.status,
                "days_active": days_active,
                "views_count": vacancy.views_count,
                "responses_count": vacancy.responses_count,
                "conversion_rate": round(conversion_rate, 2),
                "response_rate": round(response_rate, 2),
                "responses_by_status": responses_by_status,
                "avg_response_time_hours": round(avg_response_time, 1) if avg_response_time else None,
                "expires_at": vacancy.expires_at,
                "published_at": vacancy.published_at
            }

        except Exception as e:
            logger.error(f"Error calculating vacancy analytics: {e}")
            return {}

    async def get_resume_analytics(self, resume: Resume) -> Dict:
        """Get detailed analytics for a resume."""
        try:
            # Calculate days active
            days_active = 0
            if resume.published_at:
                days_active = (datetime.utcnow() - resume.published_at).days

            # Get responses (both applications and invitations)
            responses = await Response.find(
                Response.resume.id == resume.id
            ).to_list()

            # Separate applications and invitations
            applications = [r for r in responses if not r.is_invitation]
            invitations = [r for r in responses if r.is_invitation]

            responses_by_status = {
                "pending": 0,
                "viewed": 0,
                "invited": 0,
                "accepted": 0,
                "rejected": 0
            }

            for response in responses:
                status = response.status.value if hasattr(response.status, 'value') else response.status
                if status in responses_by_status:
                    responses_by_status[status] += 1

            # Calculate view-to-invitation rate
            invitation_rate = 0
            if resume.views_count > 0:
                invitation_rate = (len(invitations) / resume.views_count) * 100

            # Calculate success rate (accepted / total responses)
            success_rate = 0
            if len(responses) > 0:
                success_rate = (responses_by_status["accepted"] / len(responses)) * 100

            return {
                "resume_id": str(resume.id),
                "position": resume.desired_position,
                "status": resume.status,
                "days_active": days_active,
                "views_count": resume.views_count,
                "responses_count": resume.responses_count,
                "applications_count": len(applications),
                "invitations_count": len(invitations),
                "invitation_rate": round(invitation_rate, 2),
                "success_rate": round(success_rate, 2),
                "responses_by_status": responses_by_status,
                "published_at": resume.published_at
            }

        except Exception as e:
            logger.error(f"Error calculating resume analytics: {e}")
            return {}

    async def get_user_statistics(self, user: User) -> Dict:
        """Get overall statistics for a user."""
        try:
            from shared.constants import UserRole

            if user.role == UserRole.APPLICANT:
                return await self._get_applicant_statistics(user)
            elif user.role == UserRole.EMPLOYER:
                return await self._get_employer_statistics(user)
            else:
                return {}

        except Exception as e:
            logger.error(f"Error calculating user statistics: {e}")
            return {}

    async def _get_applicant_statistics(self, user: User) -> Dict:
        """Get statistics for applicant."""
        # Get all resumes
        resumes = await Resume.find(Resume.user.id == user.id).to_list()

        # Get all responses
        responses = await Response.find(Response.applicant.id == user.id).to_list()

        total_views = sum(r.views_count for r in resumes)
        total_responses = len(responses)

        applications = [r for r in responses if not r.is_invitation]
        invitations = [r for r in responses if r.is_invitation]

        # Count by status
        accepted_count = len([r for r in responses if r.status == ResponseStatus.ACCEPTED])
        invited_count = len([r for r in responses if r.status == ResponseStatus.INVITED])
        rejected_count = len([r for r in responses if r.status == ResponseStatus.REJECTED])

        # Success rate
        success_rate = 0
        if total_responses > 0:
            success_rate = (accepted_count / total_responses) * 100

        return {
            "role": "applicant",
            "resumes_count": len(resumes),
            "published_resumes": len([r for r in resumes if r.is_published]),
            "total_views": total_views,
            "total_responses": total_responses,
            "applications_sent": len(applications),
            "invitations_received": len(invitations),
            "accepted_count": accepted_count,
            "invited_count": invited_count,
            "rejected_count": rejected_count,
            "success_rate": round(success_rate, 2),
            "avg_views_per_resume": round(total_views / len(resumes), 1) if resumes else 0
        }

    async def _get_employer_statistics(self, user: User) -> Dict:
        """Get statistics for employer."""
        # Get all vacancies
        vacancies = await Vacancy.find(Vacancy.user.id == user.id).to_list()

        # Get all responses
        responses = await Response.find(Response.employer.id == user.id).to_list()

        total_views = sum(v.views_count for v in vacancies)
        total_responses = len(responses)

        # Count by status
        pending_count = len([r for r in responses if r.status == ResponseStatus.PENDING])
        accepted_count = len([r for r in responses if r.status == ResponseStatus.ACCEPTED])
        invited_count = len([r for r in responses if r.status == ResponseStatus.INVITED])
        rejected_count = len([r for r in responses if r.status == ResponseStatus.REJECTED])

        # Conversion rate
        conversion_rate = 0
        if total_views > 0:
            conversion_rate = (total_responses / total_views) * 100

        # Response rate
        response_rate = 0
        if total_responses > 0:
            response_rate = (accepted_count / total_responses) * 100

        return {
            "role": "employer",
            "vacancies_count": len(vacancies),
            "published_vacancies": len([v for v in vacancies if v.is_published]),
            "active_vacancies": len([v for v in vacancies if v.status == "active"]),
            "total_views": total_views,
            "total_responses": total_responses,
            "pending_responses": pending_count,
            "accepted_count": accepted_count,
            "invited_count": invited_count,
            "rejected_count": rejected_count,
            "conversion_rate": round(conversion_rate, 2),
            "response_rate": round(response_rate, 2),
            "avg_views_per_vacancy": round(total_views / len(vacancies), 1) if vacancies else 0,
            "avg_responses_per_vacancy": round(total_responses / len(vacancies), 1) if vacancies else 0
        }

    async def get_trending_positions(self, limit: int = 10) -> List[Dict]:
        """Get trending positions based on recent activity."""
        try:
            # Get all active vacancies from last 30 days
            thirty_days_ago = datetime.utcnow() - timedelta(days=30)

            vacancies = await Vacancy.find(
                Vacancy.created_at >= thirty_days_ago,
                Vacancy.is_published == True
            ).to_list()

            # Count by position
            position_stats = {}
            for vacancy in vacancies:
                pos = vacancy.position
                if pos not in position_stats:
                    position_stats[pos] = {
                        "position": pos,
                        "count": 0,
                        "total_views": 0,
                        "total_responses": 0
                    }

                position_stats[pos]["count"] += 1
                position_stats[pos]["total_views"] += vacancy.views_count
                position_stats[pos]["total_responses"] += vacancy.responses_count

            # Sort by count
            trending = sorted(
                position_stats.values(),
                key=lambda x: x["count"],
                reverse=True
            )[:limit]

            return trending

        except Exception as e:
            logger.error(f"Error getting trending positions: {e}")
            return []


# Global instance
analytics_service = AnalyticsService()
