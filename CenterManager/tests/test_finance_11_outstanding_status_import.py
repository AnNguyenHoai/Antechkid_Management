from centermanager.services.outstanding_service import OutstandingService
from centermanager.dto.outstanding_dto import OUTSTANDING_STATUS_NO_TUITION_CONFIGURED


def test_service_exposes_no_tuition_configured_status():
    assert (
        OutstandingService.NO_TUITION_CONFIGURED_STATUS
        == OUTSTANDING_STATUS_NO_TUITION_CONFIGURED
    )
