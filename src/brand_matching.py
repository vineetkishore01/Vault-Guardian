"""Brand matching module with fuzzy matching."""
from typing import List, Dict, Any, Optional
from fuzzywuzzy import fuzz, process
from sqlalchemy.orm import Session

from src.database import crud
from src.database.models import BrandAlias
from src.utils import normalize_brand_name


async def match_brand(
    brand_name: str,
    threshold: float = 0.75,
    db_session: Session = None
) -> List[Dict[str, Any]]:
    """Match brand name to existing brands using fuzzy matching."""
    if not db_session:
        return []

    normalized_name = normalize_brand_name(brand_name)

    from sqlalchemy import select
    from src.database.models import Earning

    stmt = select(Earning.brand_name).distinct()
    result = await db_session.execute(stmt)
    brand_names = [row[0] for row in result.all()]

    if not brand_names:
        return []

    matches = process.extract(
        normalized_name,
        [normalize_brand_name(b) for b in brand_names],
        limit=5,
        scorer=fuzz.token_sort_ratio
    )

    results = []
    for matched_name, score in matches:
        confidence = score / 100.0
        if confidence >= threshold:
            original_name = brand_names[
                [normalize_brand_name(b) for b in brand_names].index(matched_name)
            ]
            results.append({
                "brand_name": original_name,
                "confidence": confidence,
                "normalized_name": matched_name
            })

    results.sort(key=lambda x: x["confidence"], reverse=True)
    return results


async def get_or_create_brand_alias(
    canonical_name: str,
    alias: str,
    confidence_score: float = 1.0,
    is_confirmed: bool = False,
    db_session: Session = None
) -> BrandAlias:
    """Get existing brand alias or create new one."""
    if not db_session:
        return None

    existing = await crud.BrandAliasCRUD.get_by_alias(db_session, alias)
    if existing:
        if confidence_score > existing.confidence_score:
            existing.confidence_score = confidence_score
            existing.is_confirmed = is_confirmed
            await db_session.flush()
        return existing

    return await crud.BrandAliasCRUD.create(
        db=db_session,
        canonical_name=canonical_name,
        alias=alias,
        confidence_score=confidence_score,
        is_confirmed=is_confirmed
    )


async def confirm_brand_mapping(
    canonical_name: str,
    alias: str,
    db_session: Session = None
) -> bool:
    """Confirm a brand mapping."""
    if not db_session:
        return False

    brand_alias = await crud.BrandAliasCRUD.get_by_alias(db_session, alias)
    if brand_alias:
        brand_alias.canonical_name = canonical_name
        brand_alias.confidence_score = 1.0
        brand_alias.is_confirmed = True
        await db_session.flush()
        return True

    await crud.BrandAliasCRUD.create(
        db=db_session,
        canonical_name=canonical_name,
        alias=alias,
        confidence_score=1.0,
        is_confirmed=True
    )
    return True
