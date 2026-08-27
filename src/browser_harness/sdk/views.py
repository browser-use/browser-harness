"""Typed views for SDK returns. Requires the `sdk` extra (pydantic)."""
try:
    from pydantic import BaseModel, ConfigDict, Field
except ImportError as e:  # pragma: no cover
    raise ImportError(
        "browser_harness.sdk requires pydantic -- install with `pip install browser-harness[sdk]`"
    ) from e


class DialogInfo(BaseModel):
    """Native dialog (alert/confirm/prompt) -- freezes the page's JS thread until handled."""

    model_config = ConfigDict(extra="allow")

    type: str | None = None
    message: str | None = None


class PageInfo(BaseModel):
    """Viewport + scroll + page size; if `dialog` is set the other fields are meaningless."""

    model_config = ConfigDict(populate_by_name=True)

    url: str = ""
    title: str = ""
    viewport_width: float = Field(0, alias="w")
    viewport_height: float = Field(0, alias="h")
    scroll_x: float = Field(0, alias="sx")
    scroll_y: float = Field(0, alias="sy")
    page_width: float = Field(0, alias="pw")
    page_height: float = Field(0, alias="ph")
    dialog: DialogInfo | None = None


class Tab(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    target_id: str = Field(alias="targetId")
    title: str = ""
    url: str = ""


class Rect(BaseModel):
    """Element box in viewport CSS px -- the space Input.dispatchMouseEvent expects."""

    x: float
    y: float
    width: float
    height: float

    @property
    def center(self) -> tuple[float, float]:
        return (self.x + self.width / 2, self.y + self.height / 2)
