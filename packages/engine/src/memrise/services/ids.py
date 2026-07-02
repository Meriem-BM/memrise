from uuid import uuid4


class UuidGenerator:
    def new_id(self, prefix: str) -> str:
        return f"{prefix}_{uuid4().hex}"
