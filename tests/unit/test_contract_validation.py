"""Phase 5F contract validators, fallbacks, and trace tests."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from contextos import ContextItem, ContextOptimizer, ContextType, OptimizationPolicy
from contextos.budget import AllocationPlan, CompressionRequest
from contextos.compression import CompressionExecutor, CompressionResult
from contextos.contracts import PreservationContract, RetentionPolicy
from contextos.errors import RequiredContextOverflow
from contextos.validation import ContractValidationEngine


class WordTokenizer:
    def count_tokens(self, text: str) -> int:
        return len(text.split())


def _item(
    content: str,
    contract: PreservationContract,
    *,
    item_id: str = "source",
    context_type: ContextType = ContextType.MEMORY,
) -> ContextItem:
    timestamp = datetime(2026, 9, 12, tzinfo=UTC)
    return ContextItem(
        id=item_id,
        content=content,
        type=context_type,
        created_at=timestamp,
        updated_at=timestamp,
        token_count=len(content.split()),
        contract=contract,
    )


@pytest.mark.parametrize(
    ("source_text", "transformed", "contract", "violation"),
    [
        (
            "Amount is $1,947.36 at 4.75%.",
            "Amount is $1,947.36.",
            PreservationContract(preserve_numbers=True),
            "missing_number:4.75%",
        ),
        (
            "Effective date is 2026-09-12.",
            "The policy is effective.",
            PreservationContract(preserve_dates=True),
            "missing_date:2026-09-12",
        ),
        (
            "Use usr_72B91 with validateAccountRisk().",
            "Use validateAccountRisk().",
            PreservationContract(preserve_identifiers=True),
            "missing_identifier:usr_72B91",
        ),
        (
            "Do NOT execute without approval.",
            "Execute with approval.",
            PreservationContract(preserve_negation=True),
            "missing_negation:not",
        ),
        (
            "Evidence SRC-9 is available at https://example.test/evidence.",
            "Evidence is available.",
            PreservationContract(preserve_citations=True),
            "missing_citation:SRC-9",
        ),
    ],
)
def test_feature_validators_report_exact_missing_values(
    source_text: str,
    transformed: str,
    contract: PreservationContract,
    violation: str,
) -> None:
    result = ContractValidationEngine().validate(_item(source_text, contract), transformed)

    assert not result.passed
    assert violation in result.violations
    assert all(outcome.validator for outcome in result.outcomes)


def test_structured_validator_rejects_changed_required_value() -> None:
    contract = PreservationContract(
        preserve_structure=True,
        required_keys=("status", "id"),
    )
    result = ContractValidationEngine().validate(
        _item('{"status":"cancelled","id":"A728"}', contract),
        '{"status":"confirmed","id":"A728"}',
    )

    assert not result.passed
    assert result.violations == ("changed_structured_value:status",)


def test_dependency_reference_validator_is_reusable_without_item_contract() -> None:
    result = ContractValidationEngine().validate(
        _item("operation uses auth token", PreservationContract()),
        "operation is ready",
        required_references=("auth_001X",),
    )

    assert result.violations == ("missing_dependency_reference:auth_001X",)
    assert result.outcomes[0].validator == "DependencyReferenceValidator"


def test_all_configured_features_can_pass_together() -> None:
    content = (
        '{"status":"cancelled","id":"usr_72B91","amount":"$1,947.36",'
        '"date":"2026-09-12","policy":"do NOT execute","citation":"SRC-9"}'
    )
    contract = PreservationContract(
        preserve_numbers=True,
        preserve_dates=True,
        preserve_identifiers=True,
        preserve_citations=True,
        preserve_negation=True,
        preserve_structure=True,
        required_keys=("status", "id", "amount", "date", "policy", "citation"),
    )

    result = ContractValidationEngine().validate(_item(content, contract), content)

    assert result.passed
    assert result.violations == ()
    assert len(result.outcomes) == 6


class IdentifierDroppingCompressor:
    def compress(self, item: ContextItem, target_tokens: int, task: str) -> CompressionResult:
        del target_tokens, task
        return CompressionResult(
            content="Short summary.",
            original_tokens=item.token_count or 0,
            compressed_tokens=2,
            source_item_id=item.id,
            strategy="aggressive_test",
            provenance=(item.id,),
            lossy=True,
        )


def _plan(item: ContextItem, *, target: int, budget: int) -> AllocationPlan:
    return AllocationPlan(
        direct_selected=[],
        compression_requests=[
            CompressionRequest(
                item_id=item.id,
                target_tokens=target,
                original_tokens=item.token_count or 0,
                utility=0.9,
                value_density=0.9 / target,
                reason="raw_item_did_not_fit",
            )
        ],
        rejected_item_ids=[],
        optional_budget=budget,
        direct_tokens=0,
        compression_budget=budget,
        candidate_item_ids=[item.id],
        rejection_reasons={},
        compression_candidate_order=[item.id],
        compression_candidate_targets={item.id: target},
    )


def test_failed_aggressive_transform_falls_back_to_validated_extractive() -> None:
    source = _item(
        "Keep usr_72B91. Irrelevant background words are removable.",
        PreservationContract(preserve_identifiers=True),
    )
    execution = CompressionExecutor(
        WordTokenizer(),
        type_aware=IdentifierDroppingCompressor(),
    ).execute(
        _plan(source, target=3, budget=3),
        [source],
        task="Keep the user identifier",
        policy=OptimizationPolicy(max_input_tokens=3, minimum_compressed_tokens=1),
    )

    result = execution.successful_results[source.id]
    attempt = execution.attempts[0]
    assert result.strategy == "extractive"
    assert result.content == "Keep usr_72B91."
    assert attempt.fallback_path == ("aggressive_test", "extractive")
    assert attempt.transformation_attempts[0].violations == ("missing_identifier:usr_72B91",)
    assert attempt.transformation_attempts[1].succeeded
    assert attempt.final_representation_type == "extractive"


def test_original_representation_is_used_when_it_fits_remaining_budget() -> None:
    source = _item(
        "Keep usr_72B91 in this record.",
        PreservationContract(preserve_identifiers=True),
    )
    execution = CompressionExecutor(
        WordTokenizer(),
        type_aware=IdentifierDroppingCompressor(),
    ).execute(
        _plan(source, target=2, budget=6),
        [source],
        task="record",
        policy=OptimizationPolicy(max_input_tokens=6, minimum_compressed_tokens=1),
    )

    result = execution.successful_results[source.id]
    attempt = execution.attempts[0]
    assert result.strategy == "none"
    assert result.content == source.content
    assert attempt.fallback_path == ("aggressive_test", "extractive", "none")
    assert attempt.final_representation_type == "original"


def test_required_original_that_cannot_fit_fails_explicitly() -> None:
    source = _item(
        "Keep usr_72B91 in this record.",
        PreservationContract(
            retention=RetentionPolicy.REQUIRED,
            preserve_identifiers=True,
        ),
    )

    with pytest.raises(RequiredContextOverflow) as error:
        CompressionExecutor(
            WordTokenizer(),
            type_aware=IdentifierDroppingCompressor(),
        ).execute(
            _plan(source, target=2, budget=2),
            [source],
            task="record",
            policy=OptimizationPolicy(max_input_tokens=2, minimum_compressed_tokens=1),
        )

    assert error.value.required_item_ids == (source.id,)
    assert error.value.required_tokens == source.token_count


def test_required_candidate_fails_explicitly_before_class_maximum_rejection() -> None:
    source = _item(
        "Keep usr_72B91 in this record.",
        PreservationContract(
            retention=RetentionPolicy.REQUIRED,
            preserve_identifiers=True,
        ),
    )

    with pytest.raises(RequiredContextOverflow):
        CompressionExecutor(WordTokenizer()).execute(
            _plan(source, target=2, budget=2),
            [source],
            task="record",
            policy=OptimizationPolicy(
                max_input_tokens=2,
                minimum_compressed_tokens=1,
                class_maximum_tokens={ContextType.MEMORY: 1},
            ),
        )


def test_required_if_referenced_is_not_enforced_without_an_active_reference() -> None:
    source = _item(
        "Keep usr_72B91 in this record.",
        PreservationContract(
            retention=RetentionPolicy.REQUIRED_IF_REFERENCED,
            preserve_identifiers=True,
        ),
    )
    execution = CompressionExecutor(
        WordTokenizer(),
        type_aware=IdentifierDroppingCompressor(),
    ).execute(
        _plan(source, target=2, budget=2),
        [source],
        task="record",
        policy=OptimizationPolicy(max_input_tokens=2, minimum_compressed_tokens=1),
    )

    assert source.id not in execution.successful_results
    assert execution.attempts[0].reason == "contract_validation_failed"


def test_optimizer_trace_records_validator_outcomes_and_representation() -> None:
    source = _item(
        "Keep usr_72B91. filler filler filler filler.",
        PreservationContract(preserve_identifiers=True),
    )
    result = ContextOptimizer(tokenizer=WordTokenizer()).optimize(
        "Keep the user identifier",
        [source],
        OptimizationPolicy(
            max_input_tokens=3,
            compression_target_ratio=0.5,
            minimum_compressed_tokens=1,
        ),
    )

    trace = result.trace.items[0]
    assert trace.transformation_attempts[0].succeeded
    assert trace.transformation_attempts[0].validator_outcomes[0].validator == (
        "IdentifierPreservationValidator"
    )
    assert trace.fallback_path == ["extractive"]
    assert trace.final_representation_type == "extractive"
