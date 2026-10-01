"""Deterministic execution of allocator compression reservations."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence

from pydantic import BaseModel, ConfigDict, Field

from contextos.budget import AllocationPlan
from contextos.compression.base import CompressionResult, Compressor
from contextos.compression.extractive import ExtractiveCompressor
from contextos.compression.none import NoneCompressor
from contextos.compression.type_aware import TypeAwareCompressor
from contextos.config import OptimizationPolicy
from contextos.contracts import RetentionPolicy
from contextos.errors import RequiredContextOverflow
from contextos.models import ContextItem, ContextType
from contextos.tokenization import Tokenizer
from contextos.validation import ContractValidationEngine, TransformationAttemptRecord

_SAFE_EXTRACTIVE_TYPES = {
    ContextType.USER_MESSAGE,
    ContextType.ASSISTANT_MESSAGE,
    ContextType.MEMORY,
    ContextType.RETRIEVED_DOCUMENT,
    ContextType.DECISION,
    ContextType.PLAN,
}


class CompressionAttempt(BaseModel):
    """Traceable outcome for one ranked compression candidate."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    item_id: str
    target_tokens: int = Field(gt=0)
    attempted: bool
    result: CompressionResult | None = None
    reason: str | None = None
    transformation_attempts: tuple[TransformationAttemptRecord, ...] = ()
    fallback_path: tuple[str, ...] = ()
    final_representation_type: str | None = None


class CompressionExecution(BaseModel):
    """Complete compression-stage result and accounting."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    attempts: list[CompressionAttempt]
    successful_results: dict[str, CompressionResult]
    used_tokens: int = Field(ge=0)
    returned_tokens: int = Field(ge=0)


class CompressionExecutor:
    """Execute ranked candidates and deterministically reuse returned budget."""

    def __init__(
        self,
        tokenizer: Tokenizer,
        *,
        extractive: Compressor | None = None,
        tool_output: Compressor | None = None,
        none: Compressor | None = None,
        code: Compressor | None = None,
        structured: Compressor | None = None,
        evidence: Compressor | None = None,
        type_aware: Compressor | None = None,
        validator: ContractValidationEngine | None = None,
    ) -> None:
        self._type_aware = type_aware or TypeAwareCompressor(
            tokenizer,
            extractive=extractive,
            tool_output=tool_output,
            none=none,
            code=code,
            structured=structured,
            evidence=evidence,
        )
        self._safe_extractive = ExtractiveCompressor(tokenizer)
        self._none = NoneCompressor(tokenizer)
        self._validator = validator or ContractValidationEngine()

    def execute(
        self,
        plan: AllocationPlan,
        items: Sequence[ContextItem],
        *,
        task: str,
        policy: OptimizationPolicy,
        required_references: Mapping[str, Sequence[str]] | None = None,
    ) -> CompressionExecution:
        """Run every candidate that fits the budget available at its ranked turn."""
        by_id = {item.id: item for item in items}
        direct_by_type: dict[ContextType, int] = defaultdict(int)
        for selection in plan.direct_selected:
            direct_by_type[by_id[selection.item_id].type] += selection.allocated_tokens

        used_by_type = dict(direct_by_type)
        used_tokens = 0
        attempts: list[CompressionAttempt] = []
        successes: dict[str, CompressionResult] = {}
        for item_id in plan.compression_candidate_order:
            item = by_id[item_id]
            target = plan.compression_candidate_targets[item_id]
            available = plan.compression_budget - used_tokens
            original_tokens = item.token_count
            if original_tokens is None:
                original_tokens = self._none.compress(item, max(available, 1), task).original_tokens
            maximum = policy.class_maximum_tokens.get(item.type)
            if target > available:
                self._raise_if_required(item, original_tokens, policy)
                attempts.append(
                    CompressionAttempt(
                        item_id=item_id,
                        target_tokens=target,
                        attempted=False,
                        reason="insufficient_compression_budget",
                    )
                )
                continue
            if maximum is not None and used_by_type.get(item.type, 0) + target > maximum:
                self._raise_if_required(item, original_tokens, policy)
                attempts.append(
                    CompressionAttempt(
                        item_id=item_id,
                        target_tokens=target,
                        attempted=False,
                        reason="class_maximum_exceeded",
                    )
                )
                continue
            references = (required_references or {}).get(item_id, ())
            records: list[TransformationAttemptRecord] = []
            result, record, preferred_reason = self._attempt_transformation(
                self._compressor_for(item),
                item,
                target,
                task,
                required_references=references,
            )
            records.append(record)

            if result is None and item.type in _SAFE_EXTRACTIVE_TYPES:
                preferred_strategy = record.strategy
                if preferred_strategy not in {"extractive", "evidence_extractive"}:
                    result, record, _ = self._attempt_transformation(
                        self._safe_extractive,
                        item,
                        target,
                        task,
                        required_references=references,
                    )
                    records.append(record)

            if result is None:
                fits_maximum = maximum is None or (
                    used_by_type.get(item.type, 0) + original_tokens <= maximum
                )
                if fits_maximum:
                    result, record, _ = self._attempt_transformation(
                        self._none,
                        item,
                        available,
                        task,
                        required_references=references,
                        require_reduction=False,
                    )
                else:
                    result = None
                    record = TransformationAttemptRecord(
                        strategy="none",
                        representation_type="original",
                        succeeded=False,
                        failure_reason="class_maximum_exceeded",
                    )
                records.append(record)

            if result is None:
                self._raise_if_required(item, original_tokens, policy)
                reason = (
                    "contract_validation_failed"
                    if any(record.violations for record in records)
                    else preferred_reason
                )
                attempts.append(
                    CompressionAttempt(
                        item_id=item_id,
                        target_tokens=target,
                        attempted=True,
                        reason=reason,
                        transformation_attempts=tuple(records),
                        fallback_path=tuple(record.strategy for record in records),
                    )
                )
                continue
            successes[item_id] = result
            used_tokens += result.compressed_tokens
            used_by_type[item.type] = used_by_type.get(item.type, 0) + result.compressed_tokens
            attempts.append(
                CompressionAttempt(
                    item_id=item_id,
                    target_tokens=target,
                    attempted=True,
                    result=result,
                    transformation_attempts=tuple(records),
                    fallback_path=tuple(record.strategy for record in records),
                    final_representation_type=self._representation_type(result.strategy),
                )
            )
        return CompressionExecution(
            attempts=attempts,
            successful_results=successes,
            used_tokens=used_tokens,
            returned_tokens=plan.compression_budget - used_tokens,
        )

    def _compressor_for(self, item: ContextItem) -> Compressor:
        return self._type_aware

    @staticmethod
    def _raise_if_required(
        item: ContextItem,
        original_tokens: int,
        policy: OptimizationPolicy,
    ) -> None:
        contract = item.contract
        if contract is None or contract.retention is not RetentionPolicy.REQUIRED:
            return
        raise RequiredContextOverflow(
            required_item_ids=(item.id,),
            required_tokens=original_tokens,
            effective_budget=policy.effective_budget,
        )

    def _attempt_transformation(
        self,
        compressor: Compressor,
        item: ContextItem,
        target_tokens: int,
        task: str,
        *,
        required_references: Sequence[str],
        require_reduction: bool = True,
    ) -> tuple[CompressionResult | None, TransformationAttemptRecord, str]:
        try:
            candidate = compressor.compress(item, target_tokens, task)
        except Exception as exc:  # compressor boundary must not abort optimization
            reason = f"compressor_error:{type(exc).__name__}"
            strategy = type(compressor).__name__
            return (
                None,
                TransformationAttemptRecord(
                    strategy=strategy,
                    representation_type=self._representation_type(strategy),
                    succeeded=False,
                    failure_reason=reason,
                ),
                reason,
            )
        invalid_reason = self._validate_result(
            item,
            target_tokens,
            candidate,
            require_reduction=require_reduction,
        )
        if invalid_reason is not None:
            return (
                None,
                TransformationAttemptRecord(
                    strategy=candidate.strategy,
                    representation_type=self._representation_type(candidate.strategy),
                    succeeded=False,
                    failure_reason=invalid_reason,
                ),
                invalid_reason,
            )
        validation = self._validator.validate(
            item,
            candidate.content or "",
            required_references=required_references,
        )
        if not validation.passed:
            return (
                None,
                TransformationAttemptRecord(
                    strategy=candidate.strategy,
                    representation_type=self._representation_type(candidate.strategy),
                    succeeded=False,
                    validator_outcomes=validation.outcomes,
                    violations=validation.violations,
                    failure_reason="contract_validation_failed",
                ),
                "contract_validation_failed",
            )
        return (
            candidate,
            TransformationAttemptRecord(
                strategy=candidate.strategy,
                representation_type=self._representation_type(candidate.strategy),
                succeeded=True,
                validator_outcomes=validation.outcomes,
            ),
            "",
        )

    @staticmethod
    def _representation_type(strategy: str) -> str:
        return {
            "none": "original",
            "structured_pruning": "structured_pruned",
            "code_structural": "code_excerpt",
            "extractive": "extractive",
            "evidence_extractive": "evidence_excerpt",
            "tool_output": "tool_excerpt",
            "llm_summary": "summary",
        }.get(strategy, "transformed")

    @staticmethod
    def _validate_result(
        item: ContextItem,
        target_tokens: int,
        result: CompressionResult,
        *,
        require_reduction: bool = True,
    ) -> str | None:
        if not result.succeeded:
            return result.failure_reason or "compression_failed"
        if result.source_item_id != item.id or item.id not in result.provenance:
            return "invalid_provenance"
        if result.content is None or not result.content.strip():
            return "empty_result"
        if result.compressed_tokens > target_tokens:
            return "target_overflow"
        if require_reduction and result.compressed_tokens >= result.original_tokens:
            return "compression_not_beneficial"
        return None
