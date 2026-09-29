"""Phase 5C preservation-contract tests."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from contextos import (
    ContextItem,
    ContextOptimizer,
    ContextType,
    OptimizationPolicy,
    PreservationContract,
    RetentionPolicy,
)
from contextos.errors import MandatoryContextOverflow


class WordTokenizer:
    """Predictable tokenizer for retention-path verification."""

    def count_tokens(self, text: str) -> int:
        return len(text.split())


def _item(**changes: object) -> ContextItem:
    timestamp = datetime(2026, 9, 12, tzinfo=UTC)
    values: dict[str, object] = {
        "id": "state",
        "content": '{"status":"cancelled","id":"usr_72B91","amount":1947.36}',
        "type": ContextType.TASK_STATE,
        "created_at": timestamp,
        "updated_at": timestamp,
    }
    values.update(changes)
    return ContextItem.model_validate(values)


def _strict_contract() -> PreservationContract:
    return PreservationContract(
        retention=RetentionPolicy.REQUIRED,
        preserve_numbers=True,
        preserve_dates=True,
        preserve_identifiers=True,
        preserve_citations=True,
        preserve_negation=True,
        preserve_structure=True,
        required_keys=("status", "id", "amount"),
    )


def test_required_contract_uses_legacy_non_evictable_retention() -> None:
    item = _item(contract=_strict_contract())

    assert item.mandatory is True
    assert item.evictable is False


def test_required_item_and_values_survive_optimization_unchanged() -> None:
    content = (
        '{"status":"cancelled","id":"usr_72B91","amount":1947.36,'
        '"date":"2026-09-12","citation":"SRC-9","policy":"do NOT execute"}'
    )
    required = _item(content=content, contract=_strict_contract())
    optional = _item(
        id="optional",
        content="recent high priority optional context that cannot fit",
        importance=1.0,
    )
    required_tokens = WordTokenizer().count_tokens(content)
    result = ContextOptimizer(tokenizer=WordTokenizer()).optimize(
        "report current state",
        [required, optional],
        OptimizationPolicy(
            max_input_tokens=required_tokens + 1,
            reserve_output_tokens=1,
            compression_enabled=False,
        ),
    )

    assert [item.id for item in result.selected_items] == ["state"]
    assert result.selected_items[0].content == required.content
    assert result.selected_items[0].contract == required.contract
    assert result.trace.items[0].decision_reason == "mandatory"
    for required_value in (
        "1947.36",
        "2026-09-12",
        "usr_72B91",
        "SRC-9",
        "NOT",
        "status",
        "id",
        "amount",
    ):
        assert required_value in result.selected_items[0].content


def test_required_contract_overflow_fails_instead_of_evicting() -> None:
    required = _item(content="two words", contract=_strict_contract())

    with pytest.raises(MandatoryContextOverflow):
        ContextOptimizer(tokenizer=WordTokenizer()).optimize(
            "report current state",
            [required],
            OptimizationPolicy(max_input_tokens=2, reserve_output_tokens=1),
        )


@pytest.mark.parametrize(
    "contract",
    [
        {"preserve_structure": True},
        {"required_keys": ["status"]},
        {"preserve_structure": True, "required_keys": [""]},
        {"preserve_structure": True, "required_keys": [" status"]},
        {"preserve_structure": True, "required_keys": ["status", "status"]},
        {"unknown_option": True},
    ],
)
def test_invalid_contract_configuration_is_rejected(contract: object) -> None:
    with pytest.raises(ValidationError):
        PreservationContract.model_validate(contract)


@pytest.mark.parametrize(
    ("legacy", "message"),
    [
        ({"mandatory": False}, "mandatory=False"),
        ({"evictable": True}, "evictable=True"),
    ],
)
def test_required_contract_rejects_conflicting_legacy_flags(
    legacy: dict[str, object],
    message: str,
) -> None:
    with pytest.raises(ValidationError, match=message):
        _item(contract=_strict_contract(), **legacy)


def test_required_contract_assignment_cannot_weaken_retention() -> None:
    item = _item(contract=_strict_contract())

    with pytest.raises(ValueError, match="remain mandatory"):
        item.mandatory = False
    with pytest.raises(ValueError, match="mandatory context"):
        item.evictable = True

    assert item.mandatory is True
    assert item.evictable is False


def test_required_if_referenced_is_representable_without_premature_enforcement() -> None:
    item = _item(contract=PreservationContract(retention=RetentionPolicy.REQUIRED_IF_REFERENCED))

    assert item.mandatory is False
    assert item.evictable is True


def test_legacy_context_item_behavior_remains_valid() -> None:
    item = _item(mandatory=True, evictable=False)

    assert item.contract is None
    assert item.mandatory is True
    assert item.evictable is False


def test_contract_serialization_round_trip_is_stable() -> None:
    item = _item(contract=_strict_contract())
    serialized = item.model_dump_json()
    restored = ContextItem.model_validate_json(serialized)

    assert restored == item
    assert restored.model_dump_json() == serialized
