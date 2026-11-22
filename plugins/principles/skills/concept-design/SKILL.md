---
name: concept-design
description: Six moves on the existing concepts of a code base, after Daniel Jackson, each a trade-off (split and merge, unify and specialize, tighten and loosen). Use when a plan or a change weighs a move on an existing concept, or when one concept serves two purposes or two concepts serve one.
---

# Concept design

A concept is a unit of behaviour with a purpose of its own: a name, a purpose, the state
it keeps and the actions on that state. Its behaviour is defined without another concept,
and its benefit can be judged without one. Concepts act together by synchronisation: an
action in one brings about an action in another.

Jackson's concepts are what a user sees of a system. He sets them apart from modules and
from object-oriented classes, and his moves apart from refactoring, which starts once the
observable behaviour is settled. This skill applies them to the concepts of a code base,
the terms that its documentation defines and its types carry: an adaptation, not his
claim. In code, types call one another; what carries over is that a concept's purpose and
state can be stated without another's. No study shows that these moves improve code: use
them to name a trade-off, not to justify one.

## The six moves

Three pairs of duals. Each move favours one quality at the cost of another, and its dual
does the reverse: no move is right in itself.

| Move | What it does | Gains | Costs |
|---|---|---|---|
| Split | one concept into several | flexibility: each part is usable alone | simplicity and directness: a common use now takes two |
| Merge | several concepts into one | simplicity and directness, and behaviour no part had | flexibility: no part is usable alone |
| Unify | variants into one general concept | generality: one name, one implementation | specificity: it fits each case less well |
| Specialize | one concept into variants | specificity: each fits its case | generality: more concepts to learn and keep |
| Tighten | more synchronisation between two | automation: one action does both | control: they no longer act apart |
| Loosen | less synchronisation between two | control: each acts alone | automation: the caller does both |

Jackson's examples, from software:

- Split: full screen in Keynote became a concept of its own, no longer tied to
  presenting.
- Merge: the Yellkey URL shortener fused short URLs with expiry, so that a common word
  can serve as the short URL.
- Unify: MIT's Moira uses one list concept for mailing lists and for the groups that
  administer them; a list owned by a group of external members cannot be edited by
  anyone, which matters little in practice.
- Specialize: Lightroom keeps ratings, flags and colour labels as three concepts for one
  purpose; Jackson finds it unclear that all three are needed, but their cost small, and
  users seem to appreciate the choice.
- Tighten: Hugo's date field also schedules publication; the cost is that pages can go
  live before the pages they link to.
- Loosen: ProCamera gives focus and exposure a point each, rather than one shared point.

## In a code base

A sign suggests a move to weigh, not one to make: whether to make it belongs to the
request, and, where `workflow:plans` is installed, to its step 1. The signs are this
skill's reading for code, not Jackson's list.

- Two names for one concept, with the same state and actions: the candidate is to
  retire one name. That is none of the six moves and trades nothing, though a plan
  declares it as it would any move on a concept, with none as its cost.
- Two concepts that serve one purpose and differ in a few cases are variants: unify is
  the candidate, at the cost of specificity. A shared purpose decides, not a shared
  shape: look-alikes that serve different purposes stay apart, as the guide on
  duplication of `principles:programming-principles` says.
- One type or module that serves two purposes, which change for different reasons, is
  overloaded; Jackson speaks of overloading by piggybacking, a feature put onto a
  concept that is not its own: split is the candidate.
- A general concept whose callers keep testing which case they hold: specialize is the
  candidate.
- Callers that always perform two actions together, or keep an invariant between two
  concepts by hand: tighten is the candidate, or merge if neither concept is used alone.
- A caller that works around a coupling to act on one concept: loosen is the candidate.

Retiring a concept is a merge when another concept takes on its purpose, and a
unification when both were variants. Jackson notes that a unification, as of Apple
Mail's filters or Moira's lists, may instead factor out the shared aspect as a concept of
its own, each concept keeping the rest of its identity.

A move is chosen by the quality that the code's purpose needs, naming the quality it
gives up. A move serves the purposes that the code has now: a split, a specialization or
a loosening for a use still to come is what YAGNI rules out. Where the trade-off is
close, lean towards fewer and sharper concepts: they make every later change cheaper.
That is this skill's stance, not Jackson's.

## In a plan

Name the move, the quality it gains and the one it costs. Where `workflow:plans` is
installed, its step 1 says what else the plan's decision names, and its step 4 how the
move's commits are ordered.

## Limits

Jackson calls the moves an initial proposal: incomplete, for example without the move
that aligns a new concept with a familiar one, and with boundaries he finds blurred,
since whether a split or a loosening applies can depend on where a concept's boundary is
drawn. They are a vocabulary for naming a change and its trade-off, not a procedure that
finds good designs.

Sources: Daniel Jackson, "Concept Design Moves", NASA Formal Methods 2022, LNCS 13260;
*The Essence of Software*, Princeton University Press, 2021.
