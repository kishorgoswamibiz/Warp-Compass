/**
 * Micro-reactions the avatar makes the moment the person finishes an answer — the "mm-hm, I'm
 * listening" beat that makes the exchange feel alive. Purely cosmetic (never enters the Answer
 * Log): a cheap heuristic on the answer text picks the flavour, with light variety so back-to-back
 * answers don't get the same nod twice in a row.
 */

const NEUTRAL = ["Mm-hm", "Got it", "I see", "Right", "Okay…", "Interesting…"];
let lastIdx = -1;

export function pickReaction(answer: string): string {
  const t = answer.trim();
  if (/!{1,}$/.test(t)) return "Oh!";
  if (/\?\s*$/.test(t)) return "Hmm…";
  if (/\b(problem|issue|stuck|delay|pain|manual|error|fail)/i.test(t)) return "Oh no…";
  if (t.length > 220) return "Wow, okay!";
  let i = Math.floor(Math.random() * NEUTRAL.length);
  if (i === lastIdx) i = (i + 1) % NEUTRAL.length;
  lastIdx = i;
  return NEUTRAL[i];
}
