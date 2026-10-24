from dataclasses import dataclass


class BudgetExhausted(RuntimeError):
    pass


class ProviderError(RuntimeError):
    def __init__(self, message, status=0, retry_after=0):
        super().__init__(message)
        self.status = status
        self.retry_after = retry_after


@dataclass
class Reply:
    text: str
    tokens_in: int = 0
    tokens_out: int = 0


class Provider:
    def generate(self, system, prompt, schema, model, generation):
        raise NotImplementedError
