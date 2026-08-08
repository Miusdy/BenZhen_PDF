class Pdf2WordError(Exception):
    """Base conversion exception safe to show to users."""


class EncryptedPdfError(Pdf2WordError):
    pass


class OcrUnavailableError(Pdf2WordError):
    pass


class ConversionCancelled(Pdf2WordError):
    pass

