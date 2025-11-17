"""
Recommendation service for matching vacancies with resumes.
Optimized version with improved performance and accuracy.
"""

import re
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Set
from loguru import logger
from pydantic import BaseModel, Field

from backend.models import Vacancy, Resume
from shared.constants.positions import PositionCategory


class MatchDetails(BaseModel):
    """Detailed match information between resume and vacancy."""
    position_match: bool = False
    position_match_type: str = "none"  # exact, related, partial, none
    location_match: bool = False
    salary_compatible: bool = False
    salary_difference_percent: Optional[float] = None
    salary_estimated_from_experience: bool = False
    skills_matched: List[str] = Field(default_factory=list)
    skills_missing: List[str] = Field(default_factory=list)
    skills_match_percent: float = 0.0
    experience_sufficient: bool = False
    experience_years_candidate: Optional[int] = None
    experience_years_required: Optional[int] = None
    education_sufficient: bool = False
    work_schedule_match: bool = False
    employment_type_match: bool = False
    languages_matched: List[str] = Field(default_factory=list)
    freshness_score: float = 0.0  # 0-1, newer is better


class RecommendationScore(BaseModel):
    """Breakdown of recommendation score components."""
    total_score: float = Field(default=0.0, ge=0, le=100)
    position_score: float = 0.0
    skills_score: float = 0.0
    location_score: float = 0.0
    salary_score: float = 0.0
    experience_score: float = 0.0
    education_score: float = 0.0
    schedule_score: float = 0.0
    language_score: float = 0.0
    freshness_score: float = 0.0


class VacancyRecommendation(BaseModel):
    """Vacancy recommendation with score and details."""
    vacancy: Vacancy
    score: float = Field(ge=0, le=100)
    score_breakdown: RecommendationScore
    match_details: MatchDetails


class ResumeRecommendation(BaseModel):
    """Resume recommendation with score and details."""
    resume: Resume
    score: float = Field(ge=0, le=100)
    score_breakdown: RecommendationScore
    match_details: MatchDetails


class RecommendationService:
    """
    Service for recommending vacancies and resumes.

    Algorithm weights (totaling 100%):
    - Position match: 25%
    - Skills match: 25%
    - Location match: 15%
    - Salary compatibility: 15%
    - Experience level: 10%
    - Education match: 5%
    - Work schedule: 3%
    - Languages: 2%
    """

    # Category relationships for partial matching
    RELATED_CATEGORIES = {
        PositionCategory.BARMAN: {PositionCategory.BARISTA},
        PositionCategory.BARISTA: {PositionCategory.BARMAN, PositionCategory.COOK},
        PositionCategory.WAITER: {PositionCategory.SUPPORT},
        PositionCategory.SUPPORT: {PositionCategory.WAITER},
        PositionCategory.COOK: {PositionCategory.BARISTA},
    }

    def calculate_match_score(
        self,
        resume: Resume,
        vacancy: Vacancy
    ) -> tuple[float, RecommendationScore, MatchDetails]:
        """
        Calculate comprehensive match score between resume and vacancy.
        Returns: (total_score, score_breakdown, match_details)
        """
        details = MatchDetails()
        breakdown = RecommendationScore()

        # 1. Position category match (25 points)
        breakdown.position_score = self._score_position_match(
            resume.position_category,
            vacancy.position_category,
            details
        )

        # 2. Skills match (25 points)
        breakdown.skills_score = self._score_skills_match(
            resume.skills,
            vacancy.required_skills,
            details
        )

        # 3. Location match (15 points)
        breakdown.location_score = self._score_location_match(
            resume.city,
            vacancy.city,
            resume.ready_to_relocate,
            vacancy.allows_remote_work,
            resume.prefers_remote,
            resume.prefers_office,
            details
        )

        # 4. Salary match (15 points)
        breakdown.salary_score = self._score_salary_match(
            resume.desired_salary,
            vacancy.salary_min,
            vacancy.salary_max,
            resume.total_experience_years,
            details
        )

        # 5. Experience match (10 points)
        breakdown.experience_score = self._score_experience_match(
            resume.total_experience_years,
            vacancy.required_experience,
            details
        )

        # 6. Education match (5 points)
        breakdown.education_score = self._score_education_match(
            resume.education,
            vacancy.required_education,
            details
        )

        # 7. Work schedule match (3 points)
        breakdown.schedule_score = self._score_schedule_match(
            resume.work_schedule,
            vacancy.work_schedule,
            details
        )

        # 8. Language match (2 points)
        breakdown.language_score = self._score_language_match(
            resume.languages,
            vacancy.required_skills,  # Languages might be in skills
            details
        )

        # Calculate total
        total = sum([
            breakdown.position_score,
            breakdown.skills_score,
            breakdown.location_score,
            breakdown.salary_score,
            breakdown.experience_score,
            breakdown.education_score,
            breakdown.schedule_score,
            breakdown.language_score,
        ])

        breakdown.total_score = round(min(total, 100.0), 1)

        return breakdown.total_score, breakdown, details

    def _score_position_match(
        self,
        resume_category: Optional[str],
        vacancy_category: Optional[str],
        details: MatchDetails
    ) -> float:
        """Score position category match (0-25 points)."""
        if not resume_category or not vacancy_category:
            return 0.0

        resume_cat = resume_category.upper()
        vacancy_cat = vacancy_category.upper()

        # Exact match
        if resume_cat == vacancy_cat:
            details.position_match = True
            details.position_match_type = "exact"
            return 25.0

        # Related categories
        try:
            resume_enum = PositionCategory[resume_cat]
            vacancy_enum = PositionCategory[vacancy_cat]

            if vacancy_enum in self.RELATED_CATEGORIES.get(resume_enum, set()):
                details.position_match = True
                details.position_match_type = "related"
                return 15.0
        except (KeyError, AttributeError):
            pass

        details.position_match_type = "none"
        return 0.0

    def _score_skills_match(
        self,
        resume_skills: List[str],
        required_skills: List[str],
        details: MatchDetails
    ) -> float:
        """Score skills match (0-25 points)."""
        if not required_skills:
            return 25.0  # No requirements = full score

        if not resume_skills:
            details.skills_missing = required_skills
            return 0.0

        # Normalize skills to lowercase for comparison
        resume_set = {s.lower().strip() for s in resume_skills}
        required_set = {s.lower().strip() for s in required_skills}

        # Calculate matches
        matched = resume_set.intersection(required_set)
        missing = required_set - matched

        details.skills_matched = sorted(list(matched))
        details.skills_missing = sorted(list(missing))
        details.skills_match_percent = round(
            (len(matched) / len(required_set)) * 100, 1
        ) if required_set else 0.0

        # Score based on percentage of required skills matched
        match_ratio = len(matched) / len(required_set)
        return round(match_ratio * 25.0, 1)

    def _score_location_match(
        self,
        resume_city: Optional[str],
        vacancy_city: Optional[str],
        ready_to_relocate: bool,
        allows_remote: bool,
        prefers_remote: Optional[bool],
        prefers_office: Optional[bool],
        details: MatchDetails
    ) -> float:
        """Score location match (0-15 points)."""
        if not resume_city or not vacancy_city:
            return 0.0

        # Remote work handling - now considering candidate's preferences
        if allows_remote:
            if prefers_remote is True:
                # Perfect match: vacancy is remote AND candidate wants remote
                details.location_match = True
                return 15.0
            elif prefers_remote is False:
                # Mismatch: vacancy is remote BUT candidate prefers office
                details.location_match = False
                return 5.0
            else:
                # Neutral: candidate hasn't specified preference
                details.location_match = True
                return 10.0

        # For office positions: check if candidate explicitly doesn't want office work
        if prefers_remote is True and prefers_office is False:
            # Candidate only wants remote, but vacancy is office-based
            details.location_match = False
            return 0.0

        # Exact city match
        if resume_city.lower().strip() == vacancy_city.lower().strip():
            details.location_match = True
            return 15.0

        # Willing to relocate
        if ready_to_relocate:
            details.location_match = True  # Fixed: should be True when willing to relocate
            return 10.0

        return 0.0

    def _estimate_salary_by_experience(self, experience_years: float) -> tuple[int, int]:
        """
        Estimate expected salary range based on years of experience (for HoReCa).

        Returns:
            Tuple of (min_expected, max_expected) salary in rubles
        """
        if experience_years < 1:
            return (40_000, 55_000)
        elif experience_years < 3:
            return (50_000, 70_000)
        elif experience_years < 5:
            return (65_000, 90_000)
        elif experience_years < 10:
            return (80_000, 120_000)
        else:  # 10+ years
            return (100_000, 180_000)

    def _score_salary_match(
        self,
        desired_salary: Optional[int],
        salary_min: Optional[int],
        salary_max: Optional[int],
        experience_years: Optional[int],
        details: MatchDetails
    ) -> float:
        """Score salary compatibility (0-15 points)."""
        if not salary_min:
            return 7.5  # Neutral score if vacancy doesn't specify salary

        # If candidate didn't specify salary, estimate based on experience
        if not desired_salary:
            if experience_years is not None and experience_years > 0:
                # Estimate expected salary range based on experience
                estimated_min, estimated_max = self._estimate_salary_by_experience(experience_years)
                # Use the middle of estimated range
                desired_salary = (estimated_min + estimated_max) // 2
                details.salary_estimated_from_experience = True
            else:
                # No salary and no experience data - neutral score
                return 7.5

        # Check if desired salary is within range
        if salary_max:
            if salary_min <= desired_salary <= salary_max:
                details.salary_compatible = True
                details.salary_difference_percent = 0.0
                return 15.0

            # Calculate how far off we are
            if desired_salary < salary_min:
                diff_percent = ((salary_min - desired_salary) / salary_min) * 100
            else:
                diff_percent = ((desired_salary - salary_max) / salary_max) * 100

            details.salary_difference_percent = round(diff_percent, 1)

            # Within 10% - good match
            if diff_percent <= 10:
                details.salary_compatible = True
                return 12.0
            # Within 20% - acceptable
            elif diff_percent <= 20:
                return 8.0
            # Within 30% - marginal
            elif diff_percent <= 30:
                return 4.0
            else:
                return 0.0
        else:
            # Only min salary specified
            if desired_salary >= salary_min * 0.8:  # Within 20% below
                if desired_salary <= salary_min * 1.2:  # Within 20% above
                    details.salary_compatible = True
                    return 12.0
                else:
                    return 6.0
            return 0.0

    def _score_experience_match(
        self,
        candidate_years: Optional[int],
        required_experience: Optional[str],
        details: MatchDetails
    ) -> float:
        """Score experience match (0-10 points)."""
        if not required_experience:
            return 10.0

        required_lower = required_experience.lower()
        details.experience_years_candidate = candidate_years

        # No experience required
        if any(phrase in required_lower for phrase in ["без опыта", "no experience", "не требуется"]):
            details.experience_sufficient = True
            return 10.0

        # Extract required years using regex
        req_years = self._extract_years_from_text(required_experience)
        details.experience_years_required = req_years

        if req_years is None:
            return 5.0  # Unknown requirement

        if candidate_years is None:
            return 0.0  # No experience data

        # Calculate match based on experience difference
        if candidate_years >= req_years:
            details.experience_sufficient = True
            return 10.0
        elif candidate_years >= req_years * 0.75:
            details.experience_sufficient = True
            return 7.5
        elif candidate_years >= req_years * 0.5:
            return 5.0
        elif candidate_years >= req_years * 0.25:
            return 2.5
        else:
            # Very low experience compared to requirement
            # Give minimal score but not zero (they could learn)
            return 1.0

    def _extract_years_from_text(self, text: str) -> Optional[int]:
        """
        Extract years of experience from text using regex.
        Handles: "от 3 лет", "3+ года", "3-5 лет", "более 2 лет", etc.
        """
        if not text:
            return None

        # Pattern to find numbers followed by year-related words
        patterns = [
            r'(?:от|более|минимум|не менее)\s*(\d+)',  # "от 3", "более 2"
            r'(\d+)\s*(?:\+|и более)',  # "3+", "2 и более"
            r'(\d+)(?:-\d+)?\s*(?:год|лет|года)',  # "3 года", "1-3 года"
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return int(match.group(1))

        return None

    def _score_education_match(
        self,
        education_list: List,
        required_education: Optional[str],
        details: MatchDetails
    ) -> float:
        """Score education match (0-5 points)."""
        if not required_education:
            return 5.0

        required_lower = required_education.lower()

        # No education requirements
        if any(phrase in required_lower for phrase in ["не важно", "не имеет значения", "not required"]):
            details.education_sufficient = True
            return 5.0

        if not education_list:
            return 0.0

        # Education hierarchy
        education_levels = {
            "начальное": 1,
            "secondary": 1,
            "среднее": 2,
            "vocational": 3,
            "профессиональное": 3,
            "специальное": 3,
            "высшее": 4,
            "higher": 4,
            "specialized": 5,
        }

        # Get highest education from resume
        highest_level = 0
        for edu in education_list:
            edu_dict = edu.dict() if hasattr(edu, 'dict') else edu
            level_str = str(edu_dict.get("level", "")).lower()
            for key, value in education_levels.items():
                if key in level_str:
                    highest_level = max(highest_level, value)

        # Get required level
        required_level = 0
        for key, value in education_levels.items():
            if key in required_lower:
                required_level = max(required_level, value)

        if highest_level >= required_level:
            details.education_sufficient = True
            return 5.0
        elif highest_level >= required_level - 1:
            return 2.5
        else:
            return 0.0

    def _score_schedule_match(
        self,
        resume_schedules: List[str],
        vacancy_schedules: List[str],
        details: MatchDetails
    ) -> float:
        """Score work schedule match (0-3 points)."""
        if not vacancy_schedules:
            return 3.0

        if not resume_schedules:
            return 1.5  # Neutral

        # Normalize schedules
        resume_set = {s.lower().strip() for s in resume_schedules}
        vacancy_set = {s.lower().strip() for s in vacancy_schedules}

        # Check for overlap
        if resume_set.intersection(vacancy_set):
            details.work_schedule_match = True
            return 3.0

        return 0.0

    def _score_language_match(
        self,
        resume_languages: List,
        required_skills: List[str],
        details: MatchDetails
    ) -> float:
        """Score language match (0-2 points)."""
        if not resume_languages:
            return 1.0  # Neutral

        # Extract language names from resume
        resume_langs = set()
        for lang in resume_languages:
            lang_dict = lang.dict() if hasattr(lang, 'dict') else lang
            lang_name = str(lang_dict.get("language", "")).lower()
            resume_langs.add(lang_name)

        # Check if any required skills mention languages
        language_keywords = {
            "английский", "english", "немецкий", "german",
            "французский", "french", "испанский", "spanish",
            "итальянский", "italian", "китайский", "chinese"
        }

        required_langs = set()
        for skill in required_skills:
            skill_lower = skill.lower()
            for lang_keyword in language_keywords:
                if lang_keyword in skill_lower:
                    required_langs.add(lang_keyword)

        if not required_langs:
            return 2.0  # No language requirements

        # Check matches
        matched = []
        for req_lang in required_langs:
            for resume_lang in resume_langs:
                if req_lang in resume_lang or resume_lang in req_lang:
                    matched.append(resume_lang)

        details.languages_matched = list(set(matched))

        if matched:
            return 2.0
        return 0.0

    async def recommend_vacancies_for_resume(
        self,
        resume: Resume,
        limit: int = 10,
        min_score: float = 40.0
    ) -> List[VacancyRecommendation]:
        """
        Get recommended vacancies for a resume.
        Optimized with pre-filtering and smart querying.
        """
        try:
            # Build filter query
            filters = {
                "is_published": True,
                "status": "active"
            }

            # Optional: Pre-filter by category for better performance
            # Only if exact category match, otherwise we might miss related categories
            if resume.position_category:
                # Get related categories
                related = self._get_related_categories(resume.position_category)
                if related:
                    filters["position_category"] = {"$in": list(related)}

            # Fetch vacancies with filters
            vacancies = await Vacancy.find(filters).to_list()

            logger.info(f"Found {len(vacancies)} vacancies for evaluation")

            # Calculate scores
            recommendations: List[VacancyRecommendation] = []
            for vacancy in vacancies:
                score, breakdown, details = self.calculate_match_score(resume, vacancy)

                if score >= min_score:
                    recommendations.append(VacancyRecommendation(
                        vacancy=vacancy,
                        score=score,
                        score_breakdown=breakdown,
                        match_details=details
                    ))

            # Sort by score (descending)
            recommendations.sort(key=lambda x: x.score, reverse=True)

            return recommendations[:limit]

        except Exception as e:
            logger.error(f"Error recommending vacancies: {e}", exc_info=True)
            return []

    async def recommend_resumes_for_vacancy(
        self,
        vacancy: Vacancy,
        limit: int = 10,
        min_score: float = 40.0
    ) -> List[ResumeRecommendation]:
        """
        Get recommended resumes for a vacancy.
        Optimized with pre-filtering and smart querying.
        """
        try:
            # Build filter query
            filters = {
                "is_published": True,
                "status": "active"
            }

            # Optional: Pre-filter by category
            if vacancy.position_category:
                related = self._get_related_categories(vacancy.position_category)
                if related:
                    filters["position_category"] = {"$in": list(related)}

            # Fetch resumes with filters
            resumes = await Resume.find(filters).to_list()

            logger.info(f"Found {len(resumes)} resumes for evaluation")

            # Calculate scores
            recommendations: List[ResumeRecommendation] = []
            for resume in resumes:
                score, breakdown, details = self.calculate_match_score(resume, vacancy)

                if score >= min_score:
                    recommendations.append(ResumeRecommendation(
                        resume=resume,
                        score=score,
                        score_breakdown=breakdown,
                        match_details=details
                    ))

            # Sort by score (descending)
            recommendations.sort(key=lambda x: x.score, reverse=True)

            return recommendations[:limit]

        except Exception as e:
            logger.error(f"Error recommending resumes: {e}", exc_info=True)
            return []

    def _get_related_categories(self, category: str) -> Set[str]:
        """Get list of related categories including the original one."""
        categories = {category.upper()}

        try:
            cat_enum = PositionCategory[category.upper()]
            related = self.RELATED_CATEGORIES.get(cat_enum, set())
            categories.update([c.value for c in related])
        except (KeyError, AttributeError):
            pass

        # Add original category in both forms
        categories.add(category)
        categories.add(category.lower())

        return categories


# Global instance
recommendation_service = RecommendationService()
