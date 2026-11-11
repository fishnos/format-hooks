"""The one record every rule reports, so every hook prints the same shape."""

import dataclasses


@dataclasses.dataclass(frozen=True)
class Problem:
    path: str
    line: int | None
    message: str

    def render(self) -> str:
        if self.line is None:
            return f'{self.path}: {self.message}'

        return f'{self.path}:{self.line}: {self.message}'
