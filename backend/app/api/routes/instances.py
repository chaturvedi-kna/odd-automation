from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from collections import defaultdict

from app.db.deps import get_db
from app.models.dra_instance import DRAInstance
from app.api.deps.auth import get_current_user

router = APIRouter(prefix="/instances", tags=["instances"])


@router.get("/")
async def list_instances(db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    result = await db.execute(select(DRAInstance).where(DRAInstance.is_active == True))
    instances = result.scalars().all()
    return [
        {
            "id": i.id,
            "dra_type": i.dra_type,
            "site": i.site,
            "category": i.category,
            "category_abbrev": i.category_abbrev,
            "instance_label": i.instance_label,
        }
        for i in instances
    ]


@router.get("/tree")
async def instance_tree(db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    """
    Return cascading tree for the instance selector:
    { site: { dra_type: [ {instance_label, id, category} ] } }
    """
    result = await db.execute(
        select(DRAInstance).where(DRAInstance.is_active == True).order_by(
            DRAInstance.site, DRAInstance.dra_type, DRAInstance.instance_label
        )
    )
    instances = result.scalars().all()

    tree: dict = defaultdict(lambda: defaultdict(list))
    for inst in instances:
        tree[inst.site][inst.dra_type].append({
            "id": inst.id,
            "instance_label": inst.instance_label,
            "category": inst.category,
            "category_abbrev": inst.category_abbrev,
        })

    # Convert defaultdicts to regular dicts
    return {site: dict(types) for site, types in tree.items()}
