"""Quiz-engine tests: loader, validator, price calculation, progress helpers."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from quiz_bot.quiz_engine import (
    Category,
    Option,
    QuizConfigError,
    QuizProgress,
    calculate_price,
    load_quiz_config,
    parse_quiz_config,
)

# ---------------------------------------------------------------------------
# Loader / validator
# ---------------------------------------------------------------------------


def test_seed_loads(seed_quiz_path: Path) -> None:
    cfg = load_quiz_config(seed_quiz_path)
    assert cfg.version >= 1
    assert cfg.currency_label == "₽"
    assert len(cfg.categories) == 2
    keys = [c.key for c in cfg.categories]
    assert "renovation" in keys
    assert "tutor" in keys


def test_seed_categories_have_six_questions(seed_quiz_path: Path) -> None:
    cfg = load_quiz_config(seed_quiz_path)
    for c in cfg.categories:
        assert c.total_steps == 6, c.key


def test_seed_warmup_index_in_range(seed_quiz_path: Path) -> None:
    cfg = load_quiz_config(seed_quiz_path)
    for c in cfg.categories:
        assert c.warmup_after_index is not None
        assert 0 <= c.warmup_after_index < c.total_steps


def test_seed_renovation_first_option_weights(seed_quiz_path: Path) -> None:
    cfg = load_quiz_config(seed_quiz_path)
    renovation = cfg.category_by_key("renovation")
    assert renovation is not None
    type_q = renovation.question_by_key("type")
    assert type_q is not None
    cosmetic = type_q.option_by_key("cosmetic")
    assert cosmetic is not None
    assert cosmetic.weight_min == 4500
    assert cosmetic.weight_max == 7000


def test_seed_tutor_frequency_multiplier(seed_quiz_path: Path) -> None:
    cfg = load_quiz_config(seed_quiz_path)
    tutor = cfg.category_by_key("tutor")
    assert tutor is not None
    freq = tutor.question_by_key("frequency")
    assert freq is not None
    twice = freq.option_by_key("2x")
    assert twice is not None
    assert twice.multiplier == pytest.approx(8.0)


def test_parse_minimal_config() -> None:
    raw = {
        "categories": [
            {
                "key": "x",
                "title": "X",
                "questions": [
                    {
                        "key": "q",
                        "title": "?",
                        "options": [{"key": "a", "label": "A"}],
                    },
                ],
            },
        ],
    }
    cfg = parse_quiz_config(raw)
    assert cfg.version == 1
    assert cfg.categories[0].key == "x"
    assert cfg.categories[0].questions[0].options[0].label == "A"


def test_parse_rejects_empty_categories() -> None:
    with pytest.raises(QuizConfigError, match="non-empty 'categories'"):
        parse_quiz_config({"categories": []})


def test_parse_rejects_non_dict() -> None:
    with pytest.raises(QuizConfigError, match="JSON object"):
        parse_quiz_config([])  # type: ignore[arg-type]


def test_parse_rejects_duplicate_category() -> None:
    raw = {
        "categories": [
            {"key": "x", "title": "X", "questions": [
                {"key": "q", "title": "?", "options": [{"key": "a", "label": "A"}]}
            ]},
            {"key": "x", "title": "X2", "questions": [
                {"key": "q", "title": "?", "options": [{"key": "a", "label": "A"}]}
            ]},
        ],
    }
    with pytest.raises(QuizConfigError, match="Duplicate category"):
        parse_quiz_config(raw)


def test_parse_rejects_missing_question_key() -> None:
    raw = {
        "categories": [
            {"key": "x", "title": "X", "questions": [
                {"title": "?", "options": [{"key": "a", "label": "A"}]}
            ]},
        ],
    }
    with pytest.raises(QuizConfigError):
        parse_quiz_config(raw)


def test_parse_rejects_duplicate_option_key() -> None:
    raw = {
        "categories": [
            {"key": "x", "title": "X", "questions": [
                {"key": "q", "title": "?", "options": [
                    {"key": "a", "label": "A"},
                    {"key": "a", "label": "A2"},
                ]}
            ]},
        ],
    }
    with pytest.raises(QuizConfigError, match="Duplicate option"):
        parse_quiz_config(raw)


def test_parse_rejects_weight_max_less_than_min() -> None:
    raw = {
        "categories": [
            {"key": "x", "title": "X", "questions": [
                {"key": "q", "title": "?", "options": [
                    {"key": "a", "label": "A", "weight_min": 100, "weight_max": 10},
                ]}
            ]},
        ],
    }
    with pytest.raises(QuizConfigError, match="weight_max"):
        parse_quiz_config(raw)


def test_parse_rejects_flat_max_less_than_min() -> None:
    raw = {
        "categories": [
            {"key": "x", "title": "X", "questions": [
                {"key": "q", "title": "?", "options": [
                    {"key": "a", "label": "A", "flat_min": 100, "flat_max": 10},
                ]}
            ]},
        ],
    }
    with pytest.raises(QuizConfigError, match="flat_max"):
        parse_quiz_config(raw)


def test_parse_rejects_zero_multiplier() -> None:
    raw = {
        "categories": [
            {"key": "x", "title": "X", "questions": [
                {"key": "q", "title": "?", "options": [
                    {"key": "a", "label": "A", "multiplier": 0},
                ]}
            ]},
        ],
    }
    with pytest.raises(QuizConfigError, match="multiplier"):
        parse_quiz_config(raw)


def test_parse_rejects_warmup_out_of_range() -> None:
    raw = {
        "categories": [
            {
                "key": "x",
                "title": "X",
                "warmup_after_index": 5,
                "questions": [
                    {"key": "q", "title": "?", "options": [{"key": "a", "label": "A"}]},
                ],
            },
        ],
    }
    with pytest.raises(QuizConfigError, match="warmup_after_index"):
        parse_quiz_config(raw)


def test_load_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(QuizConfigError, match="not found"):
        load_quiz_config(tmp_path / "nope.json")


def test_load_invalid_json_raises(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    with pytest.raises(QuizConfigError, match="JSON"):
        load_quiz_config(bad)


def test_required_string_must_be_nonempty() -> None:
    raw = {
        "categories": [
            {"key": "  ", "title": "X", "questions": [
                {"key": "q", "title": "?", "options": [{"key": "a", "label": "A"}]}
            ]},
        ],
    }
    with pytest.raises(QuizConfigError, match="missing or empty 'key'"):
        parse_quiz_config(raw)


# ---------------------------------------------------------------------------
# Progress helpers
# ---------------------------------------------------------------------------


def test_progress_with_answer_appends_in_order() -> None:
    p = QuizProgress(category_key="x")
    p2 = p.with_answer("q1", "a").with_answer("q2", "b")
    assert p2.answers == (("q1", "a"), ("q2", "b"))


def test_progress_with_answer_overwrites_same_key() -> None:
    p = QuizProgress(category_key="x").with_answer("q1", "a").with_answer("q1", "b")
    assert p.answers == (("q1", "b"),)


def test_progress_without_last_pops_tail() -> None:
    p = QuizProgress(category_key="x").with_answer("q1", "a").with_answer("q2", "b")
    p2 = p.without_last()
    assert p2.answers == (("q1", "a"),)


def test_progress_without_last_on_empty_is_noop() -> None:
    p = QuizProgress(category_key="x")
    assert p.without_last().answers == ()


def test_progress_answer_for_returns_value_or_none() -> None:
    p = QuizProgress(category_key="x").with_answer("q1", "a")
    assert p.answer_for("q1") == "a"
    assert p.answer_for("missing") is None


# ---------------------------------------------------------------------------
# Price calculation
# ---------------------------------------------------------------------------


def _build_category(**kwargs) -> Category:
    return Category(
        key=kwargs.get("key", "x"),
        emoji=kwargs.get("emoji", "✨"),
        title=kwargs.get("title", "X"),
        subtitle=kwargs.get("subtitle", ""),
        intro=kwargs.get("intro", ""),
        price_unit_label=kwargs.get("price_unit_label", ""),
        warmup_after_index=kwargs.get("warmup_after_index", None),
        warmup_template=kwargs.get("warmup_template", ""),
        questions=kwargs["questions"],
    )


def test_calculate_price_empty_progress_zero() -> None:
    from quiz_bot.quiz_engine import Question
    cat = _build_category(questions=(
        Question(key="q1", title="?", options=(Option(key="a", label="A", weight_min=10, weight_max=20),)),
    ))
    pr = calculate_price(cat, QuizProgress(category_key="x"))
    assert pr.min_total == 0
    assert pr.max_total == 0


def test_calculate_price_weights_added() -> None:
    from quiz_bot.quiz_engine import Question
    cat = _build_category(questions=(
        Question(key="q1", title="?", options=(
            Option(key="a", label="A", weight_min=100, weight_max=200),
        )),
        Question(key="q2", title="?", options=(
            Option(key="b", label="B", weight_min=50, weight_max=80),
        )),
    ))
    p = QuizProgress(category_key="x").with_answer("q1", "a").with_answer("q2", "b")
    pr = calculate_price(cat, p)
    assert pr.min_total == 150
    assert pr.max_total == 280


def test_calculate_price_flat_not_multiplied() -> None:
    from quiz_bot.quiz_engine import Question
    cat = _build_category(questions=(
        Question(key="q1", title="?", options=(
            Option(key="a", label="A", weight_min=100, weight_max=200),
        )),
        Question(key="q2", title="?", options=(
            Option(key="b", label="B", multiplier=5),
        )),
        Question(key="q3", title="?", options=(
            Option(key="c", label="C", flat_min=1000, flat_max=2000),
        )),
    ))
    p = (
        QuizProgress(category_key="x")
        .with_answer("q1", "a")
        .with_answer("q2", "b")
        .with_answer("q3", "c")
    )
    pr = calculate_price(cat, p)
    # min = 100 * 5 + 1000 = 1500; max = 200 * 5 + 2000 = 3000
    assert pr.min_total == 1500
    assert pr.max_total == 3000


def test_calculate_price_multiplier_product() -> None:
    from quiz_bot.quiz_engine import Question
    cat = _build_category(questions=(
        Question(key="q1", title="?", options=(
            Option(key="a", label="A", weight_min=100, weight_max=200),
        )),
        Question(key="q2", title="?", options=(
            Option(key="b", label="B", multiplier=2.0),
        )),
        Question(key="q3", title="?", options=(
            Option(key="c", label="C", multiplier=1.5),
        )),
    ))
    p = (
        QuizProgress(category_key="x")
        .with_answer("q1", "a")
        .with_answer("q2", "b")
        .with_answer("q3", "c")
    )
    pr = calculate_price(cat, p)
    # min = 100 * 2 * 1.5 = 300; max = 200 * 2 * 1.5 = 600
    assert pr.min_total == 300
    assert pr.max_total == 600


def test_calculate_price_renovation_realistic(seed_quiz_path: Path) -> None:
    """Cosmetic, to-40 m², new condition, no kitchen/bathroom change, asap."""
    cfg = load_quiz_config(seed_quiz_path)
    cat = cfg.category_by_key("renovation")
    assert cat is not None
    p = (
        QuizProgress(category_key=cat.key)
        .with_answer("type", "cosmetic")
        .with_answer("area", "to40")
        .with_answer("condition", "new")
        .with_answer("kitchen", "skip")
        .with_answer("bathroom", "skip")
        .with_answer("timeline", "asap")
    )
    pr = calculate_price(cat, p)
    # 4500 * 35 = 157_500, 7000 * 35 = 245_000
    assert pr.min_total == 157_500
    assert pr.max_total == 245_000


def test_calculate_price_renovation_capital_with_addons(seed_quiz_path: Path) -> None:
    """Capital, 40–60 m², old fond, kitchen full, bathroom full."""
    cfg = load_quiz_config(seed_quiz_path)
    cat = cfg.category_by_key("renovation")
    assert cat is not None
    p = (
        QuizProgress(category_key=cat.key)
        .with_answer("type", "capital")
        .with_answer("area", "40_60")
        .with_answer("condition", "old")
        .with_answer("kitchen", "full")
        .with_answer("bathroom", "full")
        .with_answer("timeline", "month")
    )
    pr = calculate_price(cat, p)
    # min = 11000 * 50 + (200_000 + 200_000 + 200_000) = 550_000 + 600_000 = 1_150_000
    # max = 18000 * 50 + (400_000 + 500_000 + 450_000) = 900_000 + 1_350_000 = 2_250_000
    assert pr.min_total == 1_150_000
    assert pr.max_total == 2_250_000


def test_calculate_price_tutor_english_ege_offline(seed_quiz_path: Path) -> None:
    """English + EGE + 2x/week + offline + 90min."""
    cfg = load_quiz_config(seed_quiz_path)
    cat = cfg.category_by_key("tutor")
    assert cat is not None
    p = (
        QuizProgress(category_key=cat.key)
        .with_answer("subject", "english")
        .with_answer("level", "ege")
        .with_answer("frequency", "2x")
        .with_answer("duration", "90")
        .with_answer("format", "offline")
        .with_answer("start", "soon")
    )
    pr = calculate_price(cat, p)
    # weight_min = 800 + 300 = 1100; weight_max = 1500 + 700 = 2200
    # multiplier = 8 * 1.5 * 1.2 = 14.4
    # min = 1100 * 14.4 = 15_840; max = 2200 * 14.4 = 31_680
    assert pr.min_total == 15_840
    assert pr.max_total == 31_680


def test_calculate_price_unknown_question_ignored() -> None:
    from quiz_bot.quiz_engine import Question
    cat = _build_category(questions=(
        Question(key="q1", title="?", options=(
            Option(key="a", label="A", weight_min=100, weight_max=200),
        )),
    ))
    # Answers reference unknown questions.
    p = QuizProgress(category_key="x").with_answer("q_unknown", "x")
    pr = calculate_price(cat, p)
    assert pr.min_total == 0
    assert pr.max_total == 0


def test_calculate_price_unknown_option_ignored() -> None:
    from quiz_bot.quiz_engine import Question
    cat = _build_category(questions=(
        Question(key="q1", title="?", options=(
            Option(key="a", label="A", weight_min=100, weight_max=200),
        )),
    ))
    p = QuizProgress(category_key="x").with_answer("q1", "z")
    pr = calculate_price(cat, p)
    assert pr.min_total == 0
    assert pr.max_total == 0


def test_calculate_price_partial_progress_works(seed_quiz_path: Path) -> None:
    """Mid-quiz: only first answer collected — calculation must still be valid."""
    cfg = load_quiz_config(seed_quiz_path)
    cat = cfg.category_by_key("renovation")
    assert cat is not None
    p = QuizProgress(category_key=cat.key).with_answer("type", "cosmetic")
    pr = calculate_price(cat, p)
    # area not yet selected → multiplier = 1.0 → weight stays 4500–7000
    assert pr.min_total == 4500
    assert pr.max_total == 7000


def test_calculate_price_min_never_exceeds_max() -> None:
    from quiz_bot.quiz_engine import Question
    # Tricky: a weird option with min > max should still be loaded once we build
    # Option directly (skipping validator), so calculate_price's safety-swap kicks in.
    bad_option = Option(key="a", label="A", weight_min=200, weight_max=100)
    cat = _build_category(questions=(
        Question(key="q1", title="?", options=(bad_option,)),
    ))
    p = QuizProgress(category_key="x").with_answer("q1", "a")
    pr = calculate_price(cat, p)
    assert pr.min_total <= pr.max_total


def test_question_at_out_of_range_returns_none() -> None:
    from quiz_bot.quiz_engine import Question
    cat = _build_category(questions=(
        Question(key="q1", title="?", options=(Option(key="a", label="A"),)),
    ))
    assert cat.question_at(-1) is None
    assert cat.question_at(0) is not None
    assert cat.question_at(1) is None


def test_category_by_key_returns_none_for_missing(seed_quiz_path: Path) -> None:
    cfg = load_quiz_config(seed_quiz_path)
    assert cfg.category_by_key("nope") is None
    assert cfg.category_by_key("renovation") is not None


def test_seed_file_is_strict_json(seed_quiz_path: Path) -> None:
    """Sanity: seed_quiz.json round-trips through `json.loads` with no comments etc."""
    raw = json.loads(seed_quiz_path.read_text(encoding="utf-8"))
    assert "categories" in raw
    assert isinstance(raw["categories"], list)
