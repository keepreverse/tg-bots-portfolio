"""Quiz engine: load the quiz tree from JSON, validate it, calculate price ranges.

Pure logic, no I/O beyond reading the JSON file. Everything else is unit-tested.

Pricing model
-------------
For each question the user picks exactly one option. Each option can declare:

* ``weight_min`` / ``weight_max`` — per-unit contribution (default 0).
* ``flat_min``   / ``flat_max``   — flat addition that is NOT multiplied (default 0).
* ``multiplier`` — multiplied into the final result (default 1.0).

The total price range is:

    weighted_min = sum(weight_min)  * product(multiplier)
    weighted_max = sum(weight_max)  * product(multiplier)
    total_min    = round(weighted_min + sum(flat_min))
    total_max    = round(weighted_max + sum(flat_max))

The product/sum semantics make it natural to model both:

* «ремонт» — per-m² base × area + flat add-ons (kitchen / bathroom).
* «репетитор» — per-hour rate × hours-per-month × format multiplier.

If the model is ever insufficient, extend by adding new keys to options — the
loader will keep ignoring unknown keys defensively.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


class QuizConfigError(ValueError):
    """Raised when the quiz JSON is malformed or missing required fields."""


@dataclass(frozen=True)
class Option:
    key: str
    label: str
    weight_min: int = 0
    weight_max: int = 0
    flat_min: int = 0
    flat_max: int = 0
    multiplier: float = 1.0


@dataclass(frozen=True)
class Question:
    key: str
    title: str
    options: tuple[Option, ...]

    def option_by_key(self, key: str) -> Option | None:
        for o in self.options:
            if o.key == key:
                return o
        return None


@dataclass(frozen=True)
class Category:
    key: str
    emoji: str
    title: str
    subtitle: str
    intro: str
    price_unit_label: str
    warmup_after_index: int | None
    warmup_template: str
    questions: tuple[Question, ...]

    @property
    def total_steps(self) -> int:
        return len(self.questions)

    def question_at(self, index: int) -> Question | None:
        if 0 <= index < len(self.questions):
            return self.questions[index]
        return None

    def question_by_key(self, key: str) -> Question | None:
        for q in self.questions:
            if q.key == key:
                return q
        return None


@dataclass(frozen=True)
class QuizConfig:
    version: int
    currency_label: str
    categories: tuple[Category, ...]

    def category_by_key(self, key: str) -> Category | None:
        for c in self.categories:
            if c.key == key:
                return c
        return None


@dataclass(frozen=True)
class PriceRange:
    """Final calculated range of the quiz. `min_total <= max_total` is enforced."""

    min_total: int
    max_total: int


@dataclass(frozen=True)
class QuizProgress:
    """In-memory snapshot of a user's quiz pass — what they've answered so far."""

    category_key: str
    answers: tuple[tuple[str, str], ...] = field(default_factory=tuple)

    def with_answer(self, question_key: str, option_key: str) -> QuizProgress:
        """Return a new progress with the answer to `question_key` set/overwritten."""
        kept = tuple((q, o) for q, o in self.answers if q != question_key)
        return QuizProgress(category_key=self.category_key, answers=(*kept, (question_key, option_key)))

    def without_last(self) -> QuizProgress:
        """Pop the most-recently-added answer (used by the ◀ Назад button)."""
        if not self.answers:
            return self
        return QuizProgress(category_key=self.category_key, answers=self.answers[:-1])

    def answer_for(self, question_key: str) -> str | None:
        for q, o in self.answers:
            if q == question_key:
                return o
        return None


# ---------------------------------------------------------------------------
# Loader & validator
# ---------------------------------------------------------------------------


def load_quiz_config(path: Path) -> QuizConfig:
    """Load and validate the quiz config from `path` (a JSON file).

    Raises `QuizConfigError` on any structural issue.
    """
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise QuizConfigError(f"Quiz config not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise QuizConfigError(f"Quiz config is not valid JSON: {exc}") from exc

    return parse_quiz_config(raw)


def parse_quiz_config(raw: dict) -> QuizConfig:
    if not isinstance(raw, dict):
        raise QuizConfigError("Quiz config must be a JSON object.")
    version = int(raw.get("version", 1))
    currency_label = str(raw.get("currency_label", "₽"))
    categories_raw = raw.get("categories")
    if not isinstance(categories_raw, list) or not categories_raw:
        raise QuizConfigError("Quiz config must contain a non-empty 'categories' list.")
    categories: list[Category] = []
    seen_cat_keys: set[str] = set()
    for c in categories_raw:
        cat = _parse_category(c)
        if cat.key in seen_cat_keys:
            raise QuizConfigError(f"Duplicate category key: '{cat.key}'.")
        seen_cat_keys.add(cat.key)
        categories.append(cat)
    return QuizConfig(
        version=version,
        currency_label=currency_label,
        categories=tuple(categories),
    )


def _parse_category(raw: dict) -> Category:
    if not isinstance(raw, dict):
        raise QuizConfigError("Category must be a JSON object.")
    key = _required_str(raw, "key", "category")
    title = _required_str(raw, "title", f"category '{key}'")
    questions_raw = raw.get("questions")
    if not isinstance(questions_raw, list) or not questions_raw:
        raise QuizConfigError(f"Category '{key}' must have a non-empty 'questions' list.")
    questions: list[Question] = []
    seen_q_keys: set[str] = set()
    for q in questions_raw:
        question = _parse_question(q, category_key=key)
        if question.key in seen_q_keys:
            raise QuizConfigError(f"Duplicate question key '{question.key}' in category '{key}'.")
        seen_q_keys.add(question.key)
        questions.append(question)
    warmup_after_index = raw.get("warmup_after_index")
    if warmup_after_index is not None:
        try:
            warmup_after_index = int(warmup_after_index)
        except (TypeError, ValueError) as exc:
            raise QuizConfigError(
                f"Category '{key}': warmup_after_index must be an integer.",
            ) from exc
        if not 0 <= warmup_after_index < len(questions):
            raise QuizConfigError(
                f"Category '{key}': warmup_after_index out of range "
                f"(got {warmup_after_index}, must be in 0..{len(questions) - 1}).",
            )
    return Category(
        key=key,
        emoji=str(raw.get("emoji", "")),
        title=title,
        subtitle=str(raw.get("subtitle", "")),
        intro=str(raw.get("intro", "")),
        price_unit_label=str(raw.get("price_unit_label", "")),
        warmup_after_index=warmup_after_index,
        warmup_template=str(raw.get("warmup_template", "")),
        questions=tuple(questions),
    )


def _parse_question(raw: dict, *, category_key: str) -> Question:
    if not isinstance(raw, dict):
        raise QuizConfigError(f"Question in '{category_key}' must be a JSON object.")
    key = _required_str(raw, "key", f"question in category '{category_key}'")
    title = _required_str(raw, "title", f"question '{key}' in '{category_key}'")
    options_raw = raw.get("options")
    if not isinstance(options_raw, list) or not options_raw:
        raise QuizConfigError(
            f"Question '{key}' in '{category_key}' must have a non-empty 'options' list.",
        )
    options: list[Option] = []
    seen_opt_keys: set[str] = set()
    for o in options_raw:
        option = _parse_option(o, question_key=key, category_key=category_key)
        if option.key in seen_opt_keys:
            raise QuizConfigError(
                f"Duplicate option key '{option.key}' in question '{key}' "
                f"of category '{category_key}'.",
            )
        seen_opt_keys.add(option.key)
        options.append(option)
    return Question(key=key, title=title, options=tuple(options))


def _parse_option(raw: dict, *, question_key: str, category_key: str) -> Option:
    if not isinstance(raw, dict):
        raise QuizConfigError(
            f"Option in '{category_key}/{question_key}' must be a JSON object.",
        )
    where = f"option in '{category_key}/{question_key}'"
    key = _required_str(raw, "key", where)
    label = _required_str(raw, "label", f"option '{key}' in '{category_key}/{question_key}'")
    weight_min = _opt_int(raw, "weight_min", 0, where=where)
    weight_max = _opt_int(raw, "weight_max", weight_min, where=where)
    flat_min = _opt_int(raw, "flat_min", 0, where=where)
    flat_max = _opt_int(raw, "flat_max", flat_min, where=where)
    multiplier = _opt_float(raw, "multiplier", 1.0, where=where)
    if weight_max < weight_min:
        raise QuizConfigError(
            f"{where}: weight_max ({weight_max}) < weight_min ({weight_min}).",
        )
    if flat_max < flat_min:
        raise QuizConfigError(
            f"{where}: flat_max ({flat_max}) < flat_min ({flat_min}).",
        )
    if multiplier <= 0:
        raise QuizConfigError(f"{where}: multiplier must be > 0 (got {multiplier}).")
    return Option(
        key=key,
        label=label,
        weight_min=weight_min,
        weight_max=weight_max,
        flat_min=flat_min,
        flat_max=flat_max,
        multiplier=multiplier,
    )


def _required_str(raw: dict, field_name: str, where: str) -> str:
    v = raw.get(field_name)
    if not isinstance(v, str) or not v.strip():
        raise QuizConfigError(f"{where}: missing or empty '{field_name}'.")
    return v


def _opt_int(raw: dict, field_name: str, default: int, *, where: str) -> int:
    if field_name not in raw:
        return default
    v = raw[field_name]
    try:
        return int(v)
    except (TypeError, ValueError) as exc:
        raise QuizConfigError(
            f"{where}: '{field_name}' must be an integer (got {v!r}).",
        ) from exc


def _opt_float(raw: dict, field_name: str, default: float, *, where: str) -> float:
    if field_name not in raw:
        return default
    v = raw[field_name]
    try:
        return float(v)
    except (TypeError, ValueError) as exc:
        raise QuizConfigError(
            f"{where}: '{field_name}' must be a number (got {v!r}).",
        ) from exc


# ---------------------------------------------------------------------------
# Price calculation
# ---------------------------------------------------------------------------


def calculate_price(category: Category, progress: QuizProgress) -> PriceRange:
    """Calculate the price range for the answers collected so far.

    Unanswered questions contribute nothing, so this can be called both for
    a partial pass (the warm-up screen) and for the final pass.
    """
    sum_weight_min = 0
    sum_weight_max = 0
    sum_flat_min = 0
    sum_flat_max = 0
    product_mult = 1.0

    for q in category.questions:
        opt_key = progress.answer_for(q.key)
        if opt_key is None:
            continue
        opt = q.option_by_key(opt_key)
        if opt is None:
            # Unknown option key for a known question — defensively ignore.
            continue
        sum_weight_min += opt.weight_min
        sum_weight_max += opt.weight_max
        sum_flat_min += opt.flat_min
        sum_flat_max += opt.flat_max
        product_mult *= opt.multiplier

    weighted_min = sum_weight_min * product_mult
    weighted_max = sum_weight_max * product_mult
    total_min = round(weighted_min + sum_flat_min)
    total_max = round(weighted_max + sum_flat_max)
    # Sanity: min must not exceed max even if the user picked weird ordering.
    if total_min > total_max:
        total_min, total_max = total_max, total_min
    return PriceRange(min_total=total_min, max_total=total_max)
