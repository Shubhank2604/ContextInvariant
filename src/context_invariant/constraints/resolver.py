"""Cycle-safe directed enforcement of hard context relations."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from math import inf, isfinite

from context_invariant.constraints.models import (
    ConflictPolicy,
    ConstraintResolution,
    ValidatedRepresentation,
)
from context_invariant.contracts import RetentionPolicy
from context_invariant.errors import (
    ConstraintUnsatisfiable,
    RequiredContextOverflow,
    UnknownDependencyReference,
    UnresolvedConflict,
)
from context_invariant.models import (
    ContextEdge,
    ContextItem,
    DependencyRelation,
    validate_unique_item_ids,
)

ConflictPair = tuple[str, str]


def _pair(left: str, right: str) -> ConflictPair:
    return (left, right) if left <= right else (right, left)


def _numeric_metadata(item: ContextItem, key: str) -> float:
    value = item.metadata.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return -inf
    numeric = float(value)
    return numeric if isfinite(numeric) else -inf


def _authority_rank(item: ContextItem) -> tuple[float, float, float, float, float]:
    return (
        1.0 if item.metadata.get("canonical") is True else 0.0,
        _numeric_metadata(item, "authority_rank"),
        _numeric_metadata(item, "version"),
        _numeric_metadata(item, "source_priority"),
        item.updated_at.timestamp(),
    )


class ContextConstraintGraph:
    """Resolve legal model-visible selections without changing soft graph behavior."""

    def __init__(self, items: Sequence[ContextItem], edges: Sequence[ContextEdge]) -> None:
        validate_unique_item_ids(items)
        self._items = {item.id: item for item in items}
        self._item_order = tuple(item.id for item in items)
        self._edges = tuple(
            sorted(
                edges,
                key=lambda edge: (
                    edge.source_id,
                    edge.target_id,
                    edge.relation.value,
                    edge.weight,
                ),
            )
        )
        for edge in self._edges:
            unknown = sorted({edge.source_id, edge.target_id} - self._items.keys())
            if unknown:
                raise UnknownDependencyReference(
                    "constraint references unknown item IDs: " + ", ".join(unknown)
                )
        self._requires = tuple(
            edge for edge in self._edges if edge.relation is DependencyRelation.REQUIRES
        )
        self._supersedes = tuple(
            edge for edge in self._edges if edge.relation is DependencyRelation.SUPERSEDES
        )
        self._contradicts = tuple(
            edge for edge in self._edges if edge.relation is DependencyRelation.CONTRADICTS
        )

    def requirement_groups(self) -> tuple[tuple[str, ...], ...]:
        """Return cyclic REQUIRES components that must behave atomically."""
        return self._directed_cycles(self._requires)

    def _directed_cycles(
        self,
        edges: Sequence[ContextEdge],
    ) -> tuple[tuple[str, ...], ...]:
        """Return deterministic strongly connected groups for directed relations."""
        adjacency: dict[str, list[str]] = defaultdict(list)
        reverse_adjacency: dict[str, list[str]] = defaultdict(list)
        self_loops: set[str] = set()
        for edge in edges:
            adjacency[edge.source_id].append(edge.target_id)
            reverse_adjacency[edge.target_id].append(edge.source_id)
            if edge.source_id == edge.target_id:
                self_loops.add(edge.source_id)
        for values in adjacency.values():
            values.sort()
        for values in reverse_adjacency.values():
            values.sort()

        visited: set[str] = set()
        finish_order: list[str] = []
        for start in sorted(self._items):
            if start in visited:
                continue
            stack: list[tuple[str, bool]] = [(start, False)]
            while stack:
                item_id, expanded = stack.pop()
                if expanded:
                    finish_order.append(item_id)
                    continue
                if item_id in visited:
                    continue
                visited.add(item_id)
                stack.append((item_id, True))
                stack.extend(
                    (target_id, False)
                    for target_id in reversed(adjacency.get(item_id, ()))
                    if target_id not in visited
                )

        assigned: set[str] = set()
        groups: list[tuple[str, ...]] = []
        for start in reversed(finish_order):
            if start in assigned:
                continue
            component: list[str] = []
            pending = [start]
            assigned.add(start)
            while pending:
                item_id = pending.pop()
                component.append(item_id)
                for source_id in reversed(reverse_adjacency.get(item_id, ())):
                    if source_id not in assigned:
                        assigned.add(source_id)
                        pending.append(source_id)
            ordered = tuple(sorted(component))
            if len(ordered) > 1 or ordered[0] in self_loops:
                groups.append(ordered)
        return tuple(sorted(groups))

    def resolve(
        self,
        selected_item_ids: Sequence[str],
        *,
        effective_budget: int | None = None,
        representations: Sequence[ValidatedRepresentation] = (),
        conflict_policy: ConflictPolicy = ConflictPolicy.ERROR,
        conflict_winners: Mapping[ConflictPair, str] | None = None,
        retain_superseded: bool = False,
    ) -> ConstraintResolution:
        """Return a legal directed closure or raise an explicit typed failure."""
        supersession_cycles = self._directed_cycles(self._supersedes)
        if supersession_cycles:
            raise ConstraintUnsatisfiable(
                violations=tuple(
                    "supersession_cycle:" + "->".join((*group, group[0]))
                    for group in supersession_cycles
                )
            )
        selected = set(selected_item_ids)
        unknown_selected = sorted(selected - self._items.keys())
        if unknown_selected:
            raise UnknownDependencyReference(
                "selected constraint IDs are unknown: " + ", ".join(unknown_selected)
            )
        initially_selected = set(selected)
        representation_map = self._validate_representations(representations)
        initially_represented = set(selected) | {
            source_id
            for source_id, representation_id in representation_map.items()
            if representation_id in selected
        }
        required_roots = {
            item.id
            for item in self._items.values()
            if item.id not in initially_represented
            and (
                item.mandatory
                or (
                    item.contract is not None
                    and item.contract.retention is RetentionPolicy.REQUIRED
                )
            )
        }
        required_selections = {
            representation_map.get(item_id, item_id) for item_id in required_roots
        }
        selected.update(required_selections)
        added_required: set[str] = required_selections - initially_selected
        removed_superseded: set[str] = set()
        removed_conflicting: set[str] = set()
        unresolved: set[ConflictPair] = set()
        winners = {_pair(*pair): winner for pair, winner in (conflict_winners or {}).items()}
        self._validate_conflict_winners(winners)

        max_iterations = max(1, len(self._items) + len(self._edges))
        for _ in range(max_iterations):
            before = set(selected)
            represented = set(selected) | {
                source_id
                for source_id, representation_id in representation_map.items()
                if representation_id in selected
            }
            for edge in self._requires:
                if edge.source_id not in represented or edge.target_id in represented:
                    continue
                required_selection = representation_map.get(edge.target_id, edge.target_id)
                selected.add(required_selection)
                added_required.add(required_selection)

            represented = set(selected) | {
                source_id
                for source_id, representation_id in representation_map.items()
                if representation_id in selected
            }

            if not retain_superseded:
                for edge in self._supersedes:
                    newer, older = edge.source_id, edge.target_id
                    if older not in represented:
                        continue
                    self._reject_protected_removal(older, represented, "superseded")
                    selected.discard(representation_map.get(older, older))
                    if newer not in represented:
                        selected.add(representation_map.get(newer, newer))
                    removed_superseded.add(older)

            for edge in self._contradicts:
                pair = _pair(edge.source_id, edge.target_id)
                represented = set(selected) | {
                    source_id
                    for source_id, representation_id in representation_map.items()
                    if representation_id in selected
                }
                if not represented.intersection(pair):
                    continue
                winner = winners.get(pair) or self._deterministic_winner(*pair)
                if winner is None:
                    if conflict_policy is ConflictPolicy.RETAIN_BOTH:
                        selected.update(item_id for item_id in pair if item_id not in represented)
                        unresolved.add(pair)
                        continue
                    raise UnresolvedConflict(conflicts=(pair,))
                if winner not in pair:
                    raise ConstraintUnsatisfiable(
                        violations=(f"invalid_conflict_winner:{pair[0]}:{pair[1]}:{winner}",)
                    )
                loser = pair[0] if winner == pair[1] else pair[1]
                if loser in represented:
                    self._reject_protected_removal(loser, represented, "conflict")
                    selected.discard(representation_map.get(loser, loser))
                    removed_conflicting.add(loser)
                if winner not in represented:
                    selected.add(representation_map.get(winner, winner))

            if selected == before:
                break
        else:
            raise ConstraintUnsatisfiable(violations=("constraint_resolution_did_not_converge",))

        represented = set(selected) | {
            source_id
            for source_id, representation_id in representation_map.items()
            if representation_id in selected
        }
        missing = sorted(
            f"missing_requirement:{edge.source_id}->{edge.target_id}"
            for edge in self._requires
            if edge.source_id in represented and edge.target_id not in represented
        )
        if missing:
            raise ConstraintUnsatisfiable(violations=tuple(missing))

        total_tokens = self._total_tokens(selected)
        if effective_budget is not None and total_tokens > effective_budget:
            raise RequiredContextOverflow(
                required_item_ids=self._ordered(selected),
                required_tokens=total_tokens,
                effective_budget=effective_budget,
            )
        derivations = tuple(
            edge
            for edge in self._edges
            if edge.relation is DependencyRelation.DERIVED_FROM and edge.source_id in represented
        )
        return ConstraintResolution(
            selected_item_ids=self._ordered(selected),
            represented_item_ids=self._ordered(represented),
            added_required_item_ids=self._ordered(added_required - initially_selected),
            removed_superseded_item_ids=self._ordered(removed_superseded),
            removed_conflicting_item_ids=self._ordered(removed_conflicting),
            requirement_groups=self.requirement_groups(),
            unresolved_conflicts=tuple(sorted(unresolved)),
            derivation_relations=derivations,
            total_tokens=total_tokens,
        )

    def _validate_representations(
        self,
        representations: Sequence[ValidatedRepresentation],
    ) -> dict[str, str]:
        mapped: dict[str, str] = {}
        violations: list[str] = []
        for representation in representations:
            unknown = sorted(
                {
                    representation.source_item_id,
                    representation.representation_item_id,
                }
                - self._items.keys()
            )
            if unknown:
                raise UnknownDependencyReference(
                    "representation references unknown item IDs: " + ", ".join(unknown)
                )
            previous = mapped.get(representation.source_item_id)
            if previous is not None and previous != representation.representation_item_id:
                violations.append(f"multiple_representations:{representation.source_item_id}")
            mapped[representation.source_item_id] = representation.representation_item_id
        if violations:
            raise ConstraintUnsatisfiable(violations=tuple(sorted(set(violations))))
        return mapped

    def _validate_conflict_winners(self, winners: Mapping[ConflictPair, str]) -> None:
        known_pairs = {_pair(edge.source_id, edge.target_id) for edge in self._contradicts}
        for pair, winner in winners.items():
            unknown = sorted({*pair, winner} - self._items.keys())
            if unknown:
                raise UnknownDependencyReference(
                    "conflict override references unknown item IDs: " + ", ".join(unknown)
                )
            if pair not in known_pairs:
                raise ConstraintUnsatisfiable(
                    violations=(f"conflict_override_has_no_relation:{pair[0]}:{pair[1]}",)
                )
            if winner not in pair:
                raise ConstraintUnsatisfiable(
                    violations=(f"invalid_conflict_winner:{pair[0]}:{pair[1]}:{winner}",)
                )

    def _reject_protected_removal(
        self,
        item_id: str,
        selected: set[str],
        reason: str,
    ) -> None:
        item = self._items[item_id]
        required_by = sorted(
            edge.source_id
            for edge in self._requires
            if edge.target_id == item_id and edge.source_id in selected
        )
        contract_required = (
            item.contract is not None and item.contract.retention is RetentionPolicy.REQUIRED
        )
        if item.mandatory or contract_required or required_by:
            details = ",".join(required_by) if required_by else "retention_contract"
            raise ConstraintUnsatisfiable(
                violations=(f"{reason}_item_is_required:{item_id}:{details}",)
            )

    def _deterministic_winner(self, left_id: str, right_id: str) -> str | None:
        left_rank = _authority_rank(self._items[left_id])
        right_rank = _authority_rank(self._items[right_id])
        if left_rank == right_rank:
            return None
        return left_id if left_rank > right_rank else right_id

    def _total_tokens(self, selected: set[str]) -> int:
        missing = sorted(
            item_id for item_id in selected if self._items[item_id].token_count is None
        )
        if missing:
            raise ConstraintUnsatisfiable(
                violations=tuple(f"missing_token_count:{item_id}" for item_id in missing)
            )
        return sum(self._items[item_id].token_count or 0 for item_id in selected)

    def _ordered(self, item_ids: set[str]) -> tuple[str, ...]:
        return tuple(item_id for item_id in self._item_order if item_id in item_ids)
