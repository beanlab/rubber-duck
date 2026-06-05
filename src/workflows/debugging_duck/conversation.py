from dataclasses import dataclass, field


@dataclass(slots=True)
class DebuggingConversation:
    duck_actor: str = "Duck"
    user_actor: str = "User"
    items: list[tuple[str, str]] = field(default_factory=list)

    def append(self, actor: str, content: str) -> tuple[str, str]:
        turn = (str(actor).strip(), str(content).strip())
        self.items.append(turn)
        return turn

    def append_duck(self, content: str) -> tuple[str, str]:
        return self.append(self.duck_actor, content)

    def append_user(self, content: str) -> tuple[str, str]:
        return self.append(self.user_actor, content)

    def __str__(self) -> str:
        return "\n\n".join(
            f"{actor}: {content}"
            for actor, content in self.items
            if content
        )
