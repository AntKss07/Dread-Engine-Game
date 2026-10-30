"""Seeded deterministic dice rolling engine."""

import random


class DreadDice:
    """Deterministic random number generator for game mechanics and risky actions."""

    def __init__(self, seed: int):
        self.seed = seed
        self._rng = random.Random(seed)
        self.total_rolls = 0

    def d6(self) -> int:
        """Roll a 6-sided die (1-6)."""
        self.total_rolls += 1
        return self._rng.randint(1, 6)

    def d10(self) -> int:
        """Roll a 10-sided die (1-10)."""
        self.total_rolls += 1
        return self._rng.randint(1, 10)

    def d20(self) -> int:
        """Roll a 20-sided die (1-20)."""
        self.total_rolls += 1
        return self._rng.randint(1, 20)

    def roll(self, sides: int, count: int = 1) -> list[int]:
        """Roll multiple dice of given sides."""
        self.total_rolls += count
        return [self._rng.randint(1, sides) for _ in range(count)]

    def skill_check(self, target: int = 10, bonus: int = 0) -> tuple[bool, int, str]:
        """Perform a d20 skill check against a target difficulty."""
        roll = self.d20()
        total = roll + bonus
        success = total >= target
        outcome = (
            "critical success"
            if roll == 20
            else ("critical failure" if roll == 1 else ("success" if success else "failure"))
        )
        return success, total, outcome

    def choose(self, options: list[str]) -> str:
        """Deterministically choose one option from a list."""
        self.total_rolls += 1
        return self._rng.choice(options)
