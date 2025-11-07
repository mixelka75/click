"""
Favorites API routes.
"""

from fastapi import APIRouter, HTTPException, status
from loguru import logger
from beanie import PydanticObjectId

from backend.models import User, Favorite, Vacancy, Resume

router = APIRouter(prefix="/favorites", tags=["favorites"])


@router.post("", status_code=status.HTTP_201_CREATED)
async def add_to_favorites(
    user_telegram_id: int,
    entity_id: str,
    entity_type: str  # "vacancy" or "resume"
):
    """Add vacancy or resume to favorites."""
    try:
        # Get user
        user = await User.find_one(User.telegram_id == user_telegram_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        # Check if already in favorites
        existing = await Favorite.find_one(
            Favorite.user.id == user.id,
            Favorite.entity_id == entity_id,
            Favorite.entity_type == entity_type
        )

        if existing:
            return {"message": "Already in favorites", "favorite_id": str(existing.id)}

        # Create favorite
        favorite = Favorite(
            user=user,
            entity_id=entity_id,
            entity_type=entity_type
        )
        await favorite.insert()

        return {"message": "Added to favorites", "favorite_id": str(favorite.id)}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding to favorites: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to add to favorites"
        )


@router.delete("/{entity_id}/{entity_type}")
async def remove_from_favorites(
    user_telegram_id: int,
    entity_id: str,
    entity_type: str
):
    """Remove from favorites."""
    try:
        user = await User.find_one(User.telegram_id == user_telegram_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        favorite = await Favorite.find_one(
            Favorite.user.id == user.id,
            Favorite.entity_id == entity_id,
            Favorite.entity_type == entity_type
        )

        if not favorite:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Not in favorites"
            )

        await favorite.delete()

        return {"message": "Removed from favorites"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing from favorites: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to remove from favorites"
        )


@router.get("/my")
async def get_my_favorites(user_telegram_id: int):
    """Get user's favorites."""
    try:
        user = await User.find_one(User.telegram_id == user_telegram_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        favorites = await Favorite.find(Favorite.user.id == user.id).to_list()

        # Separate by type
        vacancy_ids = [f.entity_id for f in favorites if f.entity_type == "vacancy"]
        resume_ids = [f.entity_id for f in favorites if f.entity_type == "resume"]

        # Fetch actual entities
        vacancies = []
        resumes = []

        for vid in vacancy_ids:
            try:
                vacancy = await Vacancy.get(vid)
                if vacancy:
                    vacancies.append({
                        "id": str(vacancy.id),
                        "position": vacancy.position,
                        "company_name": vacancy.company_name,
                        "city": vacancy.city,
                        "salary_min": vacancy.salary_min,
                        "salary_max": vacancy.salary_max,
                    })
            except:
                continue

        for rid in resume_ids:
            try:
                resume = await Resume.get(rid)
                if resume:
                    resumes.append({
                        "id": str(resume.id),
                        "full_name": resume.full_name,
                        "desired_position": resume.desired_position,
                        "city": resume.city,
                        "desired_salary": resume.desired_salary,
                    })
            except:
                continue

        return {
            "vacancies": vacancies,
            "resumes": resumes,
            "total": len(vacancies) + len(resumes)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting favorites: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get favorites"
        )


@router.get("/check/{entity_id}/{entity_type}")
async def check_in_favorites(
    user_telegram_id: int,
    entity_id: str,
    entity_type: str
):
    """Check if entity is in favorites."""
    try:
        user = await User.find_one(User.telegram_id == user_telegram_id)
        if not user:
            return {"in_favorites": False}

        favorite = await Favorite.find_one(
            Favorite.user.id == user.id,
            Favorite.entity_id == entity_id,
            Favorite.entity_type == entity_type
        )

        return {"in_favorites": favorite is not None}

    except Exception as e:
        logger.error(f"Error checking favorites: {e}")
        return {"in_favorites": False}
