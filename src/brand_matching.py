"""Brand matching module with fuzzy matching."""
from typing import List, Dict, Any, Optional, Tuple
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
    
    # Query only unique brand names from the database (more efficient)
    from sqlalchemy import select, func
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


async def get_all_brand_aliases(
    canonical_name: str,
    db_session: Session = None
) -> List[BrandAlias]:
    """Get all aliases for a canonical brand name."""
    if not db_session:
        return []

    return await crud.BrandAliasCRUD.get_all_aliases(db_session, canonical_name)


async def find_canonical_brand(
    brand_name: str,
    db_session: Session = None
) -> Optional[str]:
    """Find canonical brand name for a given brand name."""
    if not db_session:
        return None

    normalized = normalize_brand_name(brand_name)

    brand_alias = await crud.BrandAliasCRUD.get_by_alias(db_session, normalized)

    if brand_alias:
        return brand_alias.canonical_name

    matches = await match_brand(brand_name, threshold=0.9, db_session=db_session)

    if matches and matches[0]["confidence"] >= 0.9:
        return matches[0]["brand_name"]

    return None


async def suggest_brand_name(
    partial_name: str,
    db_session: Session = None
) -> List[str]:
    """Suggest brand names based on partial match."""
    if not db_session:
        return []

    existing_brands = await crud.EarningCRUD.search(
        db=db_session,
        brand_name=partial_name,
        limit=10
    )
    
    brand_names = list(set([e.brand_name for e in existing_brands]))
    
    if not brand_names:
        return []
    
    suggestions = process.extract(
        normalize_brand_name(partial_name),
        [normalize_brand_name(b) for b in brand_names],
        limit=5,
        scorer=fuzz.partial_ratio
    )
    
    results = []
    for matched_name, score in suggestions:
        if score >= 60:
            original_name = brand_names[
                [normalize_brand_name(b) for b in brand_names].index(matched_name)
            ]
            results.append(original_name)
    
    return results
