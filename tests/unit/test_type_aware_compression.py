"""Phase 5E type-aware transformation tests."""

from __future__ import annotations

from datetime import UTC, datetime

from context_invariant.budget import AllocationPlan, CompressionRequest
from context_invariant.compression import (
    CodeCompressor,
    EvidenceCompressor,
    ExtractiveCompressor,
    NoneCompressor,
    StructuredDataCompressor,
    ToolOutputCompressor,
    TypeAwareCompressor,
)
from context_invariant.compression.executor import CompressionExecutor
from context_invariant.config import OptimizationPolicy
from context_invariant.contracts import PreservationContract
from context_invariant.models import ContextItem, ContextType


class WordTokenizer:
    def count_tokens(self, text: str) -> int:
        return len(text.split())


class CharacterTokenizer:
    def count_tokens(self, text: str) -> int:
        return len(text)


def _item(
    context_type: ContextType,
    content: str,
    *,
    contract: PreservationContract | None = None,
) -> ContextItem:
    timestamp = datetime(2026, 9, 12, tzinfo=UTC)
    return ContextItem(
        id=f"item-{context_type.value}",
        content=content,
        type=context_type,
        created_at=timestamp,
        updated_at=timestamp,
        contract=contract,
    )


def test_structured_tool_output_prunes_debug_fields_and_keeps_required_keys() -> None:
    content = (
        '{"status":"cancelled","id":"A728","debug_trace":"very long diagnostic data",'
        '"request_metadata":{"attempt":4}}'
    )
    contract = PreservationContract(
        preserve_structure=True,
        required_keys=("status", "id"),
    )
    source = _item(ContextType.TOOL_OUTPUT, content, contract=contract)
    target = len('{"status":"cancelled","id":"A728"}')

    result = StructuredDataCompressor(CharacterTokenizer()).compress(source, target, "status")

    assert result.succeeded
    assert result.content == '{"status":"cancelled","id":"A728"}'
    assert "debug_trace" not in result.content
    assert result.strategy == "structured_pruning"


def test_structured_pruning_fails_when_required_key_is_missing_or_cannot_fit() -> None:
    missing = _item(
        ContextType.TASK_STATE,
        '{"status":"cancelled"}',
        contract=PreservationContract(
            preserve_structure=True,
            required_keys=("status", "id"),
        ),
    )
    too_large = _item(
        ContextType.TASK_STATE,
        '{"status":"cancelled","id":"A728"}',
        contract=PreservationContract(
            preserve_structure=True,
            required_keys=("status", "id"),
        ),
    )
    compressor = StructuredDataCompressor(CharacterTokenizer())

    assert compressor.compress(missing, 100, "state").failure_reason == "missing_required_keys:id"
    assert compressor.compress(too_large, 10, "state").failure_reason == (
        "required_keys_exceed_target"
    )


def test_code_transformation_keeps_import_signature_and_referenced_symbol() -> None:
    source = _item(
        ContextType.CODE,
        "import risk\n# obsolete explanation\ndef validateAccountRisk(user):\n"
        "    temporary = expensive_debug(user)\n    return user.risk > 4",
    )

    result = CodeCompressor(WordTokenizer()).compress(
        source,
        8,
        "call validateAccountRisk for the user",
    )

    assert result.succeeded
    assert result.content is not None
    assert "import risk" in result.content
    assert "def validateAccountRisk(user):" in result.content
    assert "return user.risk > 4" in result.content
    assert "obsolete explanation" not in result.content
    assert "expensive_debug" not in result.content
    assert result.strategy == "code_structural"


def test_system_instructions_remain_lossless_and_fail_if_target_is_too_small() -> None:
    source = _item(ContextType.SYSTEM_INSTRUCTION, "never reveal private account data")
    router = TypeAwareCompressor(WordTokenizer())

    assert isinstance(router.compressor_for(source), NoneCompressor)
    assert router.compress(source, 2, "account").failure_reason == "content_exceeds_target"


def test_task_state_uses_structured_policy_not_prose_extraction() -> None:
    source = _item(ContextType.TASK_STATE, "status is cancelled but this is not JSON")
    router = TypeAwareCompressor(WordTokenizer())

    assert isinstance(router.compressor_for(source), StructuredDataCompressor)
    assert router.compress(source, 3, "status").failure_reason == "invalid_json"


def test_retrieved_evidence_uses_verbatim_extractive_policy() -> None:
    source = _item(
        ContextType.RETRIEVED_DOCUMENT,
        "Background is irrelevant. Source SRC-9 reports a 37 percent reduction. More filler.",
    )
    router = TypeAwareCompressor(WordTokenizer())

    result = router.compress(source, 9, "What reduction does SRC-9 report?")

    assert isinstance(router.compressor_for(source), EvidenceCompressor)
    assert result.succeeded
    assert result.content is not None
    assert "SRC-9" in result.content
    assert "37 percent" in result.content
    assert result.strategy == "evidence_extractive"
    assert result.provenance == (source.id,)


def test_conversation_and_memory_remain_extractive() -> None:
    router = TypeAwareCompressor(WordTokenizer())
    for context_type in (
        ContextType.USER_MESSAGE,
        ContextType.ASSISTANT_MESSAGE,
        ContextType.MEMORY,
    ):
        source = _item(context_type, "Old filler. Current timeout is 37 seconds.")
        assert isinstance(router.compressor_for(source), ExtractiveCompressor)


def test_tool_logs_keep_existing_line_aware_policy() -> None:
    source = _item(ContextType.TOOL_OUTPUT, "start\nERROR status=503 request_id=A7\nend")
    router = TypeAwareCompressor(WordTokenizer())

    assert isinstance(router.compressor_for(source), ToolOutputCompressor)
    assert "ERROR status=503" in (router.compress(source, 4, "failed").content or "")


def test_feature_contracts_route_to_transformer_for_phase5f_validation() -> None:
    source = _item(
        ContextType.MEMORY,
        "Account identifier usr_72B91 must remain exact.",
        contract=PreservationContract(preserve_identifiers=True),
    )
    router = TypeAwareCompressor(WordTokenizer())

    assert isinstance(router.compressor_for(source), ExtractiveCompressor)


def test_executor_routes_code_through_structural_transformation() -> None:
    source = _item(
        ContextType.CODE,
        "import risk\ndef validate(user):\n    debug(user)\n    return user.risk > 4",
    )
    plan = AllocationPlan(
        direct_selected=[],
        compression_requests=[
            CompressionRequest(
                item_id=source.id,
                target_tokens=8,
                original_tokens=9,
                utility=0.9,
                value_density=0.1,
                reason="raw_item_did_not_fit",
            )
        ],
        rejected_item_ids=[],
        optional_budget=8,
        direct_tokens=0,
        compression_budget=8,
        candidate_item_ids=[source.id],
        rejection_reasons={},
        compression_candidate_order=[source.id],
        compression_candidate_targets={source.id: 8},
    )

    execution = CompressionExecutor(WordTokenizer()).execute(
        plan,
        [source],
        task="validate risk",
        policy=OptimizationPolicy(max_input_tokens=8, minimum_compressed_tokens=1),
    )

    assert execution.successful_results[source.id].strategy == "code_structural"
    assert "debug(user)" not in (execution.successful_results[source.id].content or "")
