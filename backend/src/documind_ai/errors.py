class DocumentError(Exception):
    """An expected input/output failure that the CLI can explain without a traceback."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)
