"""Typed errors shared by ContextInvariant components."""


class ContextInvariantError(Exception):
    """Base exception for ContextInvariant failures."""


class TokenizerError(ContextInvariantError):
    """Raised when text cannot be tokenized safely."""


class EmbeddingProviderError(ContextInvariantError):
    """Raised when an embedding provider is unavailable or fails."""


class LLMProviderError(ContextInvariantError):
    """Raised when an optional language-model provider is unavailable or fails."""


class InvalidEmbeddingOutput(EmbeddingProviderError):
    """Raised when a provider returns malformed or unsafe embeddings."""


class UnknownDependencyReference(ContextInvariantError):
    """Raised when an edge references an item outside the validated collection."""


class InvalidScore(ContextInvariantError):
    """Raised when a scoring component is missing or outside its contract."""


class DuplicateContextItemError(ContextInvariantError):
    """Raised when a collection contains duplicate context item IDs."""


class ContextItemNotFoundError(ContextInvariantError):
    """Raised when a requested context item is not present in a store."""


class CorruptedStoreError(ContextInvariantError):
    """Raised when persisted data cannot be opened or decoded safely."""


class StoreMigrationError(ContextInvariantError):
    """Raised when a store schema cannot be migrated by this runtime."""


class LifecycleError(ContextInvariantError):
    """Raised when lifecycle instructions or timestamps are invalid."""


class InvalidOptimizationPolicy(ContextInvariantError):
    """Raised before work begins when a token-budget policy is invalid."""


class MandatoryContextOverflow(ContextInvariantError):
    """Raised when mandatory context alone exceeds the effective budget."""

    def __init__(self, *, mandatory_tokens: int, effective_budget: int) -> None:
        self.mandatory_tokens = mandatory_tokens
        self.effective_budget = effective_budget
        super().__init__(
            f"mandatory context requires {mandatory_tokens} tokens but the effective budget is "
            f"{effective_budget}"
        )


class ContextualBudgetInfeasible(ContextInvariantError):
    """Raised when applicable optional class minima exceed optional budget."""

    def __init__(self, *, applicable_minima: int, optional_budget: int) -> None:
        self.applicable_minima = applicable_minima
        self.optional_budget = optional_budget
        super().__init__(
            f"applicable class minima require {applicable_minima} tokens but the optional budget "
            f"is {optional_budget}"
        )


class AllocationError(ContextInvariantError):
    """Raised when tokenized allocation inputs violate the allocation contract."""


class CompressionError(ContextInvariantError):
    """Raised when a compressor violates the compression contract."""


class ContextBudgetOverflow(ContextInvariantError):
    """Raised when a strategy cannot represent its result within budget."""

    def __init__(self, *, strategy: str, required_tokens: int, effective_budget: int) -> None:
        self.strategy = strategy
        self.required_tokens = required_tokens
        self.effective_budget = effective_budget
        super().__init__(
            f"{strategy} requires {required_tokens} input tokens but the effective budget is "
            f"{effective_budget}"
        )


class ConstraintUnsatisfiable(ContextInvariantError):
    """Raised when no model-visible selection can satisfy declared hard relations."""

    def __init__(self, *, violations: tuple[str, ...]) -> None:
        self.violations = violations
        super().__init__("context constraints are unsatisfiable: " + "; ".join(violations))


class RequiredContextOverflow(ContextInvariantError):
    """Raised when a legal directed closure exceeds the effective token budget."""

    def __init__(
        self,
        *,
        required_item_ids: tuple[str, ...],
        required_tokens: int,
        effective_budget: int,
    ) -> None:
        self.required_item_ids = required_item_ids
        self.required_tokens = required_tokens
        self.effective_budget = effective_budget
        super().__init__(
            f"constraint closure requires {required_tokens} tokens but the effective budget is "
            f"{effective_budget}: {', '.join(required_item_ids)}"
        )


class UnresolvedConflict(ContextInvariantError):
    """Raised when contradictory items lack a deterministic or caller-supplied winner."""

    def __init__(self, *, conflicts: tuple[tuple[str, str], ...]) -> None:
        self.conflicts = conflicts
        formatted = ", ".join(f"{left}<->{right}" for left, right in conflicts)
        super().__init__(f"unresolved context conflict: {formatted}")
