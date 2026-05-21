from sdk.base import BasePlugin, tool


class Plugin(BasePlugin):
    name = "example_echo"
    description = "Example plugin that echoes user input"

    @tool(description="Echo text back to the user")
    def echo(self, text: str) -> str:
        return text

    @tool(description="Build a short greeting")
    def greet(self, name: str) -> str:
        return f"Hello, {name}."
