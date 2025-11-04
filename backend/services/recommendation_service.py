"""
Recommendation service for matching vacancies with resumes.
"""

from typing import List, Dict, Optional
from loguru import logger

from backend.models import User, Vacancy, Resume
from shared.constants import UserRole


class RecommendationService:
    """Service for recommending vacancies and resumes."""

    def calculate_match_score(
        self,
        resume: Resume,
        vacancy: Vacancy
    ) -> float:
        """
        Calculate match score between resume and vacancy.
        Returns score from 0 to 100.
        """
        score = 0.0
        max_score = 100.0

        # 1. Position category match (30 points)
        if resume.position_category == vacancy.position_category:
            score += 30
        elif resume.position_category and vacancy.position_category:
            # Partial match for related categories
            if self._are_related_categories(resume.position_category, vacancy.position_category):
                score += 15

        # 2. Skills match (25 points)
        if resume.skills and vacancy.required_skills:
            resume_skills_set = set(s.lower() for s in resume.skills)
            required_skills_set = set(s.lower() for s in vacancy.required_skills)

            if required_skills_set:
                matched_skills = resume_skills_set.intersection(required_skills_set)
                skills_match_ratio = len(matched_skills) / len(required_skills_set)
                score += skills_match_ratio * 25

        # 3. Location match (15 points)
        if resume.city and vacancy.city:
            if resume.city.lower() == vacancy.city.lower():
                score += 15
            elif resume.ready_to_relocate:
                score += 10  # Partial score if willing to relocate

        # 4. Salary match (15 points)
        if resume.desired_salary and vacancy.salary_min:
            # Check if expected salary is within range
            if vacancy.salary_max:
                if vacancy.salary_min <= resume.desired_salary <= vacancy.salary_max:
                    score += 15
                elif resume.desired_salary <= vacancy.salary_max * 1.1:  # Within 10%
                    score += 10
            else:
                # Only min salary specified
                if resume.desired_salary <= vacancy.salary_min * 1.2:  # Within 20%
                    score += 10

        # 5. Experience match (10 points)
        if resume.total_experience_years and vacancy.required_experience:
            exp_match = self._match_experience(
                resume.total_experience_years,
                vacancy.required_experience
            )
            score += exp_match * 10

        # 6. Education match (5 points)
        if resume.education and vacancy.required_education:
            if self._match_education(resume.education, vacancy.required_education):
                score += 5

        return min(score, max_score)

    def _are_related_categories(self, cat1: str, cat2: str) -> bool:
        """Check if two categories are related."""
        # Define related category groups
        related_groups = [
            {"barman", "barista"},  # Bar-related
            {"waiter", "support"},  # Service
            {"cook", "barista"},    # Kitchen
        ]

        cat1_lower = cat1.lower()
        cat2_lower = cat2.lower()

        for group in related_groups:
            if cat1_lower in group and cat2_lower in group:
                return True

        return False

    def _match_experience(self, years: int, required: str) -> float:
        """Match experience level. Returns 0-1."""
        required_lower = required.lower()

        if "без опыта" in required_lower or "no_experience" in required_lower:
            return 1.0  # Anyone can apply

        # Extract years from requirement
        if "1" in required_lower:
            req_years = 1
        elif "2" in required_lower:
            req_years = 2
        elif "3" in required_lower:
            req_years = 3
        elif "5" in required_lower:
            req_years = 5
        else:
            return 0.5  # Unknown requirement

        # Calculate match
        if years >= req_years:
            return 1.0
        elif years >= req_years * 0.75:  # Within 75%
            return 0.75
        elif years >= req_years * 0.5:  # Within 50%
            return 0.5
        else:
            return 0.25

    def _match_education(self, education_list: List, required: str) -> bool:
        """Check if education matches requirement."""
        if not education_list:
            return False

        required_lower = required.lower()

        if "не важно" in required_lower or "not_required" in required_lower:
            return True

        # Map education levels
        education_hierarchy = {
            "secondary": 1,
            "vocational": 2,
            "higher": 3,
            "specialized_higher": 4
        }

        # Get highest education from resume
        highest_level = 0
        for edu in education_list:
            level_str = edu.get("level", "").lower()
            for key, value in education_hierarchy.items():
                if key in level_str:
                    highest_level = max(highest_level, value)

        # Get required level
        required_level = 0
        for key, value in education_hierarchy.items():
            if key in required_lower:
                required_level = value

        return highest_level >= required_level

    async def recommend_vacancies_for_resume(
        self,
        resume: Resume,
        limit: int = 10,
        min_score: float = 40.0
    ) -> List[Dict]:
        """Get recommended vacancies for a resume."""
        try:
            # Get all active published vacancies
            vacancies = await Vacancy.find(
                Vacancy.is_published == True,
                Vacancy.status == "active"
            ).to_list()

            # Calculate scores
            recommendations = []
            for vacancy in vacancies:
                score = self.calculate_match_score(resume, vacancy)

                if score >= min_score:
                    recommendations.append({
                        "vacancy": vacancy,
                        "score": round(score, 1),
                        "match_details": self._get_match_details(resume, vacancy)
                    })

            # Sort by score
            recommendations.sort(key=lambda x: x["score"], reverse=True)

            return recommendations[:limit]

        except Exception as e:
            logger.error(f"Error recommending vacancies: {e}")
            return []

    async def recommend_resumes_for_vacancy(
        self,
        vacancy: Vacancy,
        limit: int = 10,
        min_score: float = 40.0
    ) -> List[Dict]:
        """Get recommended resumes for a vacancy."""
        try:
            # Get all active published resumes
            resumes = await Resume.find(
                Resume.is_published == True,
                Resume.status == "active"
            ).to_list()

            # Calculate scores
            recommendations = []
            for resume in resumes:
                score = self.calculate_match_score(resume, vacancy)

                if score >= min_score:
                    recommendations.append({
                        "resume": resume,
                        "score": round(score, 1),
                        "match_details": self._get_match_details(resume, vacancy)
                    })

            # Sort by score
            recommendations.sort(key=lambda x: x["score"], reverse=True)

            return recommendations[:limit]

        except Exception as e:
            logger.error(f"Error recommending resumes: {e}")
            return []

    def _get_match_details(self, resume: Resume, vacancy: Vacancy) -> Dict:
        """Get detailed match information."""
        details = {
            "position_match": resume.position_category == vacancy.position_category,
            "location_match": resume.city and vacancy.city and resume.city.lower() == vacancy.city.lower(),
            "salary_compatible": False,
            "skills_matched": [],
            "experience_sufficient": False
        }

        # Salary compatibility
        if resume.desired_salary and vacancy.salary_min:
            if vacancy.salary_max:
                details["salary_compatible"] = vacancy.salary_min <= resume.desired_salary <= vacancy.salary_max
            else:
                details["salary_compatible"] = resume.desired_salary <= vacancy.salary_min * 1.2

        # Matched skills
        if resume.skills and vacancy.required_skills:
            resume_skills_set = set(s.lower() for s in resume.skills)
            required_skills_set = set(s.lower() for s in vacancy.required_skills)
            matched = resume_skills_set.intersection(required_skills_set)
            details["skills_matched"] = list(matched)

        # Experience
        if resume.total_experience_years and vacancy.required_experience:
            match_score = self._match_experience(
                resume.total_experience_years,
                vacancy.required_experience
            )
            details["experience_sufficient"] = match_score >= 0.75

        return details


# Global instance
recommendation_service = RecommendationService()
