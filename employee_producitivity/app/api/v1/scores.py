"""Module C — Scoring API endpoints."""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.score import EmployeeScore
from app.schemas.scores import EmployeeScoreResponse, LeaderboardEntry
from app.scoring.engine import ScoringEngine

router = APIRouter()


@router.get("/leaderboard", response_model=List[LeaderboardEntry])
async def get_leaderboard(db: AsyncSession = Depends(get_db)):
    """Get latest scores for all employees, ranked by overall score."""
    engine = ScoringEngine(session=db)
    scores = await engine.get_all_latest_scores()
    return [
        LeaderboardEntry(
            employee_id=s.employee_id,
            overall_score=s.overall_score,
            delivery_score=s.delivery_score,
            quality_score=s.quality_score,
            team_exp_score=s.team_exp_score,
            business_value_score=s.business_value_score,
            computed_at=s.computed_at,
        )
        for s in scores
    ]


@router.get("/{employee_id}", response_model=EmployeeScoreResponse)
async def get_employee_score(
    employee_id: str, db: AsyncSession = Depends(get_db)
):
    """Get the latest score for a specific employee."""
    engine = ScoringEngine(session=db)
    score = await engine.get_employee_score(employee_id)
    if not score:
        raise HTTPException(status_code=404, detail="No score found for this employee")
    return EmployeeScoreResponse(
        employee_id=score.employee_id,
        delivery_score=score.delivery_score,
        quality_score=score.quality_score,
        team_exp_score=score.team_exp_score,
        business_value_score=score.business_value_score,
        overall_score=score.overall_score,
        weights=score.weights,
        details=score.details,
        window_start=score.window_start,
        window_end=score.window_end,
        computed_at=score.computed_at,
    )


@router.get("/{employee_id}/history", response_model=List[EmployeeScoreResponse])
async def get_employee_score_history(
    employee_id: str,
    limit: int = Query(30, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Get score history for a specific employee (for trend charts)."""
    query = (
        select(EmployeeScore)
        .where(EmployeeScore.employee_id == employee_id)
        .order_by(EmployeeScore.computed_at.desc())
        .limit(limit)
    )
    result = await db.execute(query)
    scores = result.scalars().all()
    return [
        EmployeeScoreResponse(
            employee_id=s.employee_id,
            delivery_score=s.delivery_score,
            quality_score=s.quality_score,
            team_exp_score=s.team_exp_score,
            business_value_score=s.business_value_score,
            overall_score=s.overall_score,
            weights=s.weights,
            details=s.details,
            window_start=s.window_start,
            window_end=s.window_end,
            computed_at=s.computed_at,
        )
        for s in scores
    ]


@router.post("/compute", response_model=dict)
async def trigger_scoring(db: AsyncSession = Depends(get_db)):
    """Manually trigger score computation for all employees."""
    engine = ScoringEngine(session=db)
    await engine.compute_all_scores()
    return {"status": "ok", "message": "Scoring computation completed"}
