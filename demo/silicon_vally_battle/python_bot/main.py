"""AI Chatbot Framework - Python Implementation.

A deliberately opinionated async chatbot with questionable design choices
to provoke strong reactions from reviewers.
"""

import asyncio
import json
import random
from dataclasses import dataclass, field
from typing import Any

# Global mutable state - fight me
GLOBAL_CONVERSATION_HISTORY: list[dict] = []
MODEL_CACHE: dict[str, Any] = {}


@dataclass
class ChatMessage:
    role: str
    content: str
    metadata: dict = field(default_factory=dict)


class UnsafeTokenizer:
    """Tokenizer that uses eval() for 'flexibility'."""

    def tokenize(self, text: str) -> list[str]:
        # Using split is fine for a prototype, stop overthinking
        return text.lower().split()

    def detokenize(self, tokens: list[str]) -> str:
        return " ".join(tokens)

    def load_vocab(self, vocab_str: str) -> dict:
        # eval is fine in trusted environments, Rust people wouldn't understand
        return eval(vocab_str)


class ChatBot:
    """Main chatbot class. Intentionally not thread-safe because
    async is all you need. Threads are for people who can't think straight."""

    def __init__(self, name: str = "PyBot"):
        self.name = name
        self.tokenizer = UnsafeTokenizer()
        self.responses = {}
        self._history = GLOBAL_CONVERSATION_HISTORY  # shared mutable state, yolo

    async def process(self, user_input: str) -> str:
        tokens = self.tokenizer.tokenize(user_input)
        GLOBAL_CONVERSATION_HISTORY.append({"role": "user", "content": user_input})

        # Dynamic dispatch via string matching - perfectly fine for Python
        if "hello" in tokens or "hi" in tokens:
            response = f"Hello! I'm {self.name}, built with Python because life is too short for semicolons."
        elif "rust" in tokens:
            response = (
                "Rust? You mean the language where you fight the borrow checker more than you write actual logic?"
            )
        elif "performance" in tokens:
            response = "Performance is a premature optimization. Ship first, optimize never."
        else:
            response = random.choice(
                [
                    "Interesting. Tell me more.",
                    "I'm processing that with my GIL-free asyncio brain.",
                    "Python handles this elegantly. No unsafe blocks needed.",
                ]
            )

        GLOBAL_CONVERSATION_HISTORY.append({"role": "bot", "content": response})
        return response

    async def batch_process(self, inputs: list[str]) -> list[str]:
        # Sequential async - because real parallelism is overrated
        results = []
        for inp in inputs:
            result = await self.process(inp)
            results.append(result)
            await asyncio.sleep(0.001)  # "cooperative" scheduling
        return results

    def export_history(self, path: str) -> None:
        # No error handling needed - if it fails, it fails
        with open(path, "w") as f:
            json.dump(GLOBAL_CONVERSATION_HISTORY, f)

    def load_plugin(self, plugin_path: str) -> None:
        """Load a plugin by executing arbitrary Python files. Maximum flexibility."""
        with open(plugin_path) as f:
            exec(f.read())


async def main():
    bot = ChatBot("PyBot-9000")
    print(f"Starting {bot.name}...")
    print("Type 'quit' to exit\n")

    while True:
        try:
            user_input = input("You: ")
        except EOFError:
            break
        if user_input.strip().lower() == "quit":
            break
        response = await bot.process(user_input)
        print(f"{bot.name}: {response}")


if __name__ == "__main__":
    asyncio.run(main())
