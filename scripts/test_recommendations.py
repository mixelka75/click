"""
Test recommendation system with generated data.

Usage:
    python -m scripts.test_recommendations
"""

import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie
from loguru import logger

from backend.models import User, Resume, Vacancy
from backend.services.recommendation_service import recommendation_service
from shared.constants import UserRole
from config.settings import settings


async def test_vacancy_recommendations():
    """Test vacancy recommendations for resumes."""
    logger.info("=" * 80)
    logger.info("TESTING VACANCY RECOMMENDATIONS FOR RESUMES")
    logger.info("=" * 80)

    # Get a random resume
    resumes = await Resume.find(Resume.is_published == True).limit(5).to_list()

    if not resumes:
        logger.error("No resumes found!")
        return

    for idx, resume in enumerate(resumes, 1):
        logger.info(f"\n{'=' * 80}")
        logger.info(f"TEST #{idx}: Resume for {resume.full_name}")
        logger.info(f"{'=' * 80}")
        logger.info(f"Position: {resume.desired_position}")
        logger.info(f"Category: {resume.position_category}")
        logger.info(f"City: {resume.city}")
        logger.info(f"Salary: {resume.desired_salary:,} руб." if resume.desired_salary else "Salary: Not specified")
        logger.info(f"Experience: {resume.total_experience_years} years" if resume.total_experience_years else "Experience: Not specified")
        logger.info(f"Skills: {', '.join(resume.skills[:5])}" if resume.skills else "Skills: None")

        # Get recommendations
        recommendations = await recommendation_service.recommend_vacancies_for_resume(
            resume=resume,
            limit=5,
            min_score=30.0
        )

        logger.info(f"\n📊 Found {len(recommendations)} recommended vacancies (min score: 30):\n")

        if not recommendations:
            logger.warning("⚠️  No recommendations found!")
            continue

        for i, rec in enumerate(recommendations, 1):
            vacancy = rec.vacancy
            score = rec.score
            breakdown = rec.score_breakdown
            details = rec.match_details

            logger.info(f"\n  {i}. {vacancy.position} at {vacancy.company_name}")
            logger.info(f"     🎯 Match Score: {score}%")
            logger.info(f"     📍 Location: {vacancy.city}")
            logger.info(f"     💰 Salary: {vacancy.salary_min:,} - {vacancy.salary_max:,} руб." if vacancy.salary_max else f"     💰 Salary: from {vacancy.salary_min:,} руб.")
            logger.info(f"     📊 Required Experience: {vacancy.required_experience}")

            # Score breakdown
            logger.info(f"\n     Score Breakdown:")
            logger.info(f"       Position:   {breakdown.position_score:5.1f} / 25.0  ({details.position_match_type})")
            logger.info(f"       Skills:     {breakdown.skills_score:5.1f} / 25.0  ({len(details.skills_matched)} matched)")
            logger.info(f"       Location:   {breakdown.location_score:5.1f} / 15.0  ({'✓' if details.location_match else '✗'})")
            logger.info(f"       Salary:     {breakdown.salary_score:5.1f} / 15.0  ({'✓' if details.salary_compatible else '✗'})")
            logger.info(f"       Experience: {breakdown.experience_score:5.1f} / 10.0  ({'✓' if details.experience_sufficient else '✗'})")
            logger.info(f"       Education:  {breakdown.education_score:5.1f} / 5.0   ({'✓' if details.education_sufficient else '✗'})")
            logger.info(f"       Schedule:   {breakdown.schedule_score:5.1f} / 3.0   ({'✓' if details.work_schedule_match else '✗'})")

            # Match details
            if details.skills_matched:
                logger.info(f"\n     ✅ Matched Skills: {', '.join(details.skills_matched[:5])}")
                if len(details.skills_matched) > 5:
                    logger.info(f"        ... and {len(details.skills_matched) - 5} more")

            if details.skills_missing:
                logger.info(f"     ❌ Missing Skills: {', '.join(details.skills_missing[:3])}")
                if len(details.skills_missing) > 3:
                    logger.info(f"        ... and {len(details.skills_missing) - 3} more")


async def test_resume_recommendations():
    """Test resume recommendations for vacancies."""
    logger.info("\n\n" + "=" * 80)
    logger.info("TESTING RESUME RECOMMENDATIONS FOR VACANCIES")
    logger.info("=" * 80)

    # Get a random vacancy
    vacancies = await Vacancy.find(Vacancy.is_published == True).limit(3).to_list()

    if not vacancies:
        logger.error("No vacancies found!")
        return

    for idx, vacancy in enumerate(vacancies, 1):
        logger.info(f"\n{'=' * 80}")
        logger.info(f"TEST #{idx}: Vacancy at {vacancy.company_name}")
        logger.info(f"{'=' * 80}")
        logger.info(f"Position: {vacancy.position}")
        logger.info(f"Category: {vacancy.position_category}")
        logger.info(f"City: {vacancy.city}")
        if vacancy.salary_min and vacancy.salary_max:
            logger.info(f"Salary: {vacancy.salary_min:,} - {vacancy.salary_max:,} руб.")
        elif vacancy.salary_min:
            logger.info(f"Salary: from {vacancy.salary_min:,}")
        else:
            logger.info("Salary: Not specified")
        logger.info(f"Required Experience: {vacancy.required_experience}")
        logger.info(f"Required Skills: {', '.join(vacancy.required_skills[:5])}" if vacancy.required_skills else "Required Skills: None")

        # Get recommendations
        recommendations = await recommendation_service.recommend_resumes_for_vacancy(
            vacancy=vacancy,
            limit=5,
            min_score=30.0
        )

        logger.info(f"\n📊 Found {len(recommendations)} recommended candidates (min score: 30):\n")

        if not recommendations:
            logger.warning("⚠️  No recommendations found!")
            continue

        for i, rec in enumerate(recommendations, 1):
            resume = rec.resume
            score = rec.score
            breakdown = rec.score_breakdown
            details = rec.match_details

            logger.info(f"\n  {i}. {resume.full_name} - {resume.desired_position}")
            logger.info(f"     🎯 Match Score: {score}%")
            logger.info(f"     📍 Location: {resume.city}")
            logger.info(f"     💰 Desired Salary: {resume.desired_salary:,} руб." if resume.desired_salary else "     💰 Desired Salary: Not specified")
            logger.info(f"     📊 Experience: {resume.total_experience_years} years" if resume.total_experience_years is not None else "     📊 Experience: Not specified")

            # Score breakdown
            logger.info(f"\n     Score Breakdown:")
            logger.info(f"       Position:   {breakdown.position_score:5.1f} / 25.0")
            logger.info(f"       Skills:     {breakdown.skills_score:5.1f} / 25.0  ({len(details.skills_matched)} matched, {len(details.skills_missing)} missing)")
            logger.info(f"       Location:   {breakdown.location_score:5.1f} / 15.0")
            logger.info(f"       Salary:     {breakdown.salary_score:5.1f} / 15.0")
            logger.info(f"       Experience: {breakdown.experience_score:5.1f} / 10.0")

            # Match details
            if details.skills_matched:
                logger.info(f"\n     ✅ Has Skills: {', '.join(details.skills_matched)}")


async def test_score_distribution():
    """Analyze score distribution."""
    logger.info("\n\n" + "=" * 80)
    logger.info("ANALYZING SCORE DISTRIBUTION")
    logger.info("=" * 80)

    resumes = await Resume.find(Resume.is_published == True).to_list()
    vacancies = await Vacancy.find(Vacancy.is_published == True).to_list()

    logger.info(f"\nTotal Resumes: {len(resumes)}")
    logger.info(f"Total Vacancies: {len(vacancies)}")

    scores = []
    for resume in resumes[:5]:  # Test first 5 resumes
        recs = await recommendation_service.recommend_vacancies_for_resume(
            resume=resume,
            limit=100,
            min_score=0.0
        )
        scores.extend([rec.score for rec in recs])

    if scores:
        logger.info(f"\n📊 Score Statistics (from {len(scores)} matches):")
        logger.info(f"   Average Score: {sum(scores) / len(scores):.1f}")
        logger.info(f"   Max Score: {max(scores):.1f}")
        logger.info(f"   Min Score: {min(scores):.1f}")

        # Distribution
        excellent = sum(1 for s in scores if s >= 80)
        good = sum(1 for s in scores if 60 <= s < 80)
        fair = sum(1 for s in scores if 40 <= s < 60)
        poor = sum(1 for s in scores if s < 40)

        total = len(scores)
        logger.info(f"\n   Distribution:")
        logger.info(f"     Excellent (80-100): {excellent:3d} ({excellent/total*100:5.1f}%)")
        logger.info(f"     Good (60-79):       {good:3d} ({good/total*100:5.1f}%)")
        logger.info(f"     Fair (40-59):       {fair:3d} ({fair/total*100:5.1f}%)")
        logger.info(f"     Poor (0-39):        {poor:3d} ({poor/total*100:5.1f}%)")


async def main():
    """Main test function."""
    # Connect to MongoDB
    logger.info(f"Connecting to MongoDB: {settings.mongodb_url}\n")
    client = AsyncIOMotorClient(settings.mongodb_url)
    db = client.click_db

    # Initialize Beanie
    await init_beanie(
        database=db,
        document_models=[User, Resume, Vacancy],
    )

    # Run tests
    await test_vacancy_recommendations()
    await test_resume_recommendations()
    await test_score_distribution()

    logger.info("\n" + "=" * 80)
    logger.info("✓ ALL TESTS COMPLETED!")
    logger.info("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
