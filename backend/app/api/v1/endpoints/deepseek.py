"""
API endpoints para DeepSeek Decisions
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from typing import Optional

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.deepseek_decision import DeepSeekDecision
from app.schemas.deepseek import DeepSeekDecisionResponse, DeepSeekDecisionListResponse

router = APIRouter()


@router.get("/decisions", response_model=DeepSeekDecisionListResponse)
async def get_deepseek_decisions(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    executed_only: bool = Query(False, description="Solo decisiones que resultaron en trades ejecutados"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Obtener decisiones de DeepSeek del usuario"""
    
    query = select(DeepSeekDecision).where(
        DeepSeekDecision.user_id == current_user.id
    )
    
    if executed_only:
        query = query.where(DeepSeekDecision.was_executed == True)
    
    query = query.order_by(desc(DeepSeekDecision.created_at)).limit(limit).offset(offset)
    
    result = await db.execute(query)
    decisions = result.scalars().all()
    
    # Contar total
    count_query = select(DeepSeekDecision).where(
        DeepSeekDecision.user_id == current_user.id
    )
    if executed_only:
        count_query = count_query.where(DeepSeekDecision.was_executed == True)
    
    total_result = await db.execute(select(DeepSeekDecision).where(DeepSeekDecision.user_id == current_user.id))
    total = len(total_result.scalars().all())
    
    return DeepSeekDecisionListResponse(
        decisions=[DeepSeekDecisionResponse.from_orm(d) for d in decisions],
        total=total
    )


@router.get("/decisions/{decision_id}", response_model=DeepSeekDecisionResponse)
async def get_deepseek_decision(
    decision_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Obtener una decisión específica de DeepSeek"""
    
    result = await db.execute(
        select(DeepSeekDecision).where(
            DeepSeekDecision.id == decision_id,
            DeepSeekDecision.user_id == current_user.id
        )
    )
    decision = result.scalar_one_or_none()
    
    if not decision:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Decision not found"
        )
    
    return DeepSeekDecisionResponse.from_orm(decision)

