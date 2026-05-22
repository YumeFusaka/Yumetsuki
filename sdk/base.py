from __future__ import annotations

from dataclasses import dataclass
from inspect import signature
from typing import Any, Callable, get_type_hints


_TYPE_MAP = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
}


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]
    handler: Callable[..., Any]

    def as_openai_tool(self, qualified_name: str | None = None) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": qualified_name or self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


def tool(description: str = "", params: dict[str, str] | None = None):
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        setattr(func, "_yumetsuki_tool_description", description)
        setattr(func, "_yumetsuki_tool_params", params or {})
        return func

    return decorator


class BasePlugin:
    name = ""
    description = ""

    def tools(self) -> list[ToolSpec]:
        specs: list[ToolSpec] = []
        for attr_name in dir(self):
            member = getattr(self, attr_name)
            description = getattr(member, "_yumetsuki_tool_description", None)
            if description is None:
                continue
            param_descs = getattr(member, "_yumetsuki_tool_params", {})
            specs.append(ToolSpec(
                name=attr_name,
                description=description,
                parameters=_build_parameters(member, param_descs),
                handler=member,
            ))
        return sorted(specs, key=lambda spec: spec.name)

    def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        for spec in self.tools():
            if spec.name == name:
                try:
                    return spec.handler(**arguments)
                except TypeError:
                    valid = list(spec.parameters.get("properties", {}).keys())
                    return f"参数错误：{name} 可用参数为 {valid}，收到了 {list(arguments.keys())}"
        raise ValueError(f"Unknown tool: {name}")


def _build_parameters(func: Callable[..., Any], param_descs: dict[str, str] | None = None) -> dict[str, Any]:
    sig = signature(func)
    hints = get_type_hints(func)
    properties: dict[str, Any] = {}
    required: list[str] = []
    descs = param_descs or {}

    for name, param in sig.parameters.items():
        if name == "self":
            continue
        annotation = hints.get(name, str)
        schema_type = _TYPE_MAP.get(annotation, "string")
        prop: dict[str, Any] = {"type": schema_type}
        if name in descs:
            prop["description"] = descs[name]
        properties[name] = prop
        if param.default is param.empty:
            required.append(name)

    return {
        "type": "object",
        "properties": properties,
        "required": required,
    }
