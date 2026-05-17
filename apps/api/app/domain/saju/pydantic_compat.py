"""Compatibility helpers for Pydantic v1 and v2 model APIs."""

from __future__ import annotations

from typing import Any, TypeVar


ModelT = TypeVar("ModelT")


def model_to_dict(model: Any, *, mode: str | None = None, **kwargs: Any) -> dict[str, Any]:
    if hasattr(model, "model_dump"):
        if mode is not None:
            kwargs.setdefault("mode", mode)
        return model.model_dump(**kwargs)
    return model.dict(**kwargs)


def model_from_json(model_class: type[ModelT], json_text: str) -> ModelT:
    if hasattr(model_class, "model_validate_json"):
        return model_class.model_validate_json(json_text)
    return model_class.parse_raw(json_text)


def model_validate_compat(model_class: type[ModelT], data: Any) -> ModelT:
    if hasattr(model_class, "model_validate"):
        return model_class.model_validate(data)
    return model_class.parse_obj(data)


def model_copy_compat(
    model: ModelT,
    *,
    deep: bool = False,
    update: dict[str, Any] | None = None,
) -> ModelT:
    kwargs: dict[str, Any] = {"deep": deep}
    if update is not None:
        kwargs["update"] = update

    if hasattr(model, "model_copy"):
        return model.model_copy(**kwargs)
    return model.copy(**kwargs)
