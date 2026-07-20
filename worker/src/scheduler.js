// FSRS scheduling for the Worker — ts-fsrs (the JS port of py-fsrs). Same
// algorithm; this is the only file that touches the fsrs library. Cards are
// stored as JSON; ts-fsrs uses Date objects, so we revive them on the way in.

import { fsrs, createEmptyCard, Rating } from "ts-fsrs";

const f = fsrs();

const RATING = { 1: Rating.Again, 2: Rating.Hard, 3: Rating.Good, 4: Rating.Easy };

// Fresh FSRS state for a new card -> [fsrsObject, dueIso].
export function newCardState(now = new Date()) {
  const card = createEmptyCard(now);
  return [card, card.due.toISOString()];
}

// ts-fsrs cards serialize to JSON with Date fields as ISO strings; revive them.
function revive(obj) {
  return {
    ...obj,
    due: new Date(obj.due),
    last_review: obj.last_review ? new Date(obj.last_review) : undefined,
  };
}

// Apply a 1-4 rating. Returns [newFsrsObject, dueIso].
export function review(fsrsObj, rating, now = new Date()) {
  const grade = RATING[rating];
  if (!grade) throw new Error(`rating must be 1-4, got ${rating}`);
  const { card } = f.next(revive(fsrsObj), now, grade);
  return [card, card.due.toISOString()];
}
