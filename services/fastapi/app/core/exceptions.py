class MediTrackException(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class DrugNotFoundException(MediTrackException):
    def __init__(self, drug_id: int) -> None:
        super().__init__(
            code="DRUG_NOT_FOUND",
            message=f"Drug with id {drug_id} does not exist",
            status_code=404,
        )


class InsufficientStockException(MediTrackException):
    def __init__(self, drug_name: str) -> None:
        super().__init__(
            code="INSUFFICIENT_STOCK",
            message=f"Insufficient stock for drug: {drug_name}",
            status_code=422,
        )


class PrescriptionNotFoundException(MediTrackException):
    def __init__(self, prescription_id: int) -> None:
        super().__init__(
            code="PRESCRIPTION_NOT_FOUND",
            message=f"Prescription with id {prescription_id} does not exist",
            status_code=404,
        )


class PatientNotFoundException(MediTrackException):
    def __init__(self, patient_id: int) -> None:
        super().__init__(
            code="PATIENT_NOT_FOUND",
            message=f"Patient with id {patient_id} does not exist",
            status_code=404,
        )


class DoctorNotFoundException(MediTrackException):
    def __init__(self, doctor_id: int) -> None:
        super().__init__(
            code="DOCTOR_NOT_FOUND",
            message=f"Doctor with id {doctor_id} does not exist",
            status_code=404,
        )


class InteractionDetectedException(MediTrackException):
    def __init__(self, details: str) -> None:
        super().__init__(
            code="INTERACTION_DETECTED",
            message=details,
            status_code=422,
        )


class UnauthorizedException(MediTrackException):
    def __init__(self, message: str) -> None:
        super().__init__(
            code="UNAUTHORIZED",
            message=message,
            status_code=403,
        )


class StorageException(MediTrackException):
    def __init__(self, message: str) -> None:
        super().__init__(
            code="STORAGE_ERROR",
            message=message,
            status_code=500,
        )


class AIServiceException(MediTrackException):
    def __init__(self, message: str) -> None:
        super().__init__(
            code="AI_SERVICE_UNAVAILABLE",
            message=message,
            status_code=503,
        )
