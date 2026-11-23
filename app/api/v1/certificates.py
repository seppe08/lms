from fastapi import APIRouter, status

from app.api.deps import CurrentUser, DbSession
from app.schemas.certificate import CertificateRead, CertificateVerifyRead
from app.services import certificate_service

router = APIRouter(tags=["certificates"])


@router.post(
    "/courses/{course_id}/certificate",
    response_model=CertificateRead,
    status_code=status.HTTP_201_CREATED,
    summary="Claim course completion certificate",
    description=(
        "Generates a verified certificate of completion once a student "
        "has reached 100% course progress."
    ),
)
async def claim_certificate(
    course_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> CertificateRead:
    cert = await certificate_service.generate_certificate(
        db,
        course_id=course_id,
        actor=current_user,
    )
    return CertificateRead.model_validate(cert)


@router.get(
    "/users/me/certificates",
    response_model=list[CertificateRead],
    summary="List current user's certificates",
    description="Returns all certificates earned by the authenticated student.",
)
async def list_my_certificates(
    db: DbSession,
    current_user: CurrentUser,
) -> list[CertificateRead]:
    certs = await certificate_service.list_user_certificates(
        db,
        user_id=current_user.id,
    )
    return [CertificateRead.model_validate(c) for c in certs]


@router.get(
    "/certificates/verify/{certificate_code}",
    response_model=CertificateVerifyRead,
    summary="Verify certificate",
    description="Public endpoint to verify the authenticity of an earned completion certificate.",
)
async def verify_certificate(
    certificate_code: str,
    db: DbSession,
) -> CertificateVerifyRead:
    return await certificate_service.verify_certificate(
        db,
        certificate_code=certificate_code,
    )
