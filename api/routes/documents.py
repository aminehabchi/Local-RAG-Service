from fastapi import APIRouter

router = APIRouter()



@router.get("/documents")
def documents_hnadler():
    return {"message": "documents handler"}