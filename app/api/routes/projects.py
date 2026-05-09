from fastapi import APIRouter, HTTPException, Query

from app.firestore_db import create_project, delete_project, get_project, list_projects
from app.schemas import ProjectCreate, ProjectOut


router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=ProjectOut)
def create_project_api(payload: ProjectCreate) -> ProjectOut:
    return create_project(payload)


@router.get("", response_model=list[ProjectOut])
def list_projects_api(user_id: str | None = Query(default=None)) -> list[ProjectOut]:
    return list_projects(user_id=user_id)


@router.get("/{project_id}", response_model=ProjectOut)
def get_project_api(project_id: str) -> ProjectOut:
    project = get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.delete("/{project_id}")
def delete_project_api(project_id: str) -> dict[str, bool]:
    deleted = delete_project(project_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"deleted": True}
