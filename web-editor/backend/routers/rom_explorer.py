"""
Generic ROM Explorer API: one endpoint, all 27 extractable structures.

GET /api/rom/structures             → list of {name, entries_count, columns}
GET /api/rom/structures/{name}      → all entries (limit/offset pagination)
GET /api/rom/structures/{name}/{idx} → single entry by index

Read-only — these tables mirror ROM bytes and shouldn't be hand-edited.
If a structure needs editing, do it via its dedicated CRUD router
(dialogues/units/skills/etc.) + patch generator.
"""

from fastapi import APIRouter, HTTPException, Query, Depends
from typing import Optional

from database import get_db_connection
from rom_models import EXTRACTABLE, get_entries, get_fields, table_name
from routers.auth import get_current_user, User

router = APIRouter(prefix='/api/rom', tags=['rom'])


@router.get('/structures')
def list_structures(_: User = Depends(get_current_user)):
    """List all extractable structures with metadata."""
    out = []
    for structure in EXTRACTABLE:
        fields = get_fields(structure)
        entries = get_entries(structure)
        # Real row count from DB (not bank.json) — that's what's queryable
        try:
            conn = get_db_connection()
            cur = conn.execute(f'SELECT COUNT(*) FROM {table_name(structure)}')
            db_count = cur.fetchone()[0]
        except Exception:
            db_count = 0
        finally:
            if 'conn' in locals():
                conn.close()
        out.append({
            'name': structure,
            'table': table_name(structure),
            'entries_in_db': db_count,
            'entries_in_bank': len(entries),
            'fields': [
                {'name': f['name'], 'type': f.get('type', '?'), 'size': f.get('size', 0), 'offset': f.get('offset', 0)}
                for f in fields
            ],
        })
    return out


@router.get('/structures/{name}')
def get_structure_entries(
    name: str,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    _: User = Depends(get_current_user),
):
    if name not in EXTRACTABLE:
        raise HTTPException(404, f'Unknown structure: {name}. Valid: {EXTRACTABLE}')
    conn = get_db_connection()
    try:
        tbl = table_name(name)
        cur = conn.execute(f'SELECT COUNT(*) FROM {tbl}')
        total = cur.fetchone()[0]
        cur = conn.execute(f'SELECT * FROM {tbl} ORDER BY _idx LIMIT ? OFFSET ?', (limit, offset))
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description]
        return {
            'structure': name,
            'total': total,
            'limit': limit,
            'offset': offset,
            'rows': [dict(zip(cols, row)) for row in rows],
        }
    finally:
        conn.close()


@router.get('/structures/{name}/{idx}')
def get_structure_entry(name: str, idx: int, _: User = Depends(get_current_user)):
    if name not in EXTRACTABLE:
        raise HTTPException(404, f'Unknown structure: {name}')
    conn = get_db_connection()
    try:
        tbl = table_name(name)
        cur = conn.execute(f'SELECT * FROM {tbl} WHERE _idx = ?', (idx,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, f'No entry {name}[{idx}]')
        cols = [d[0] for d in cur.description]
        return dict(zip(cols, row))
    finally:
        conn.close()