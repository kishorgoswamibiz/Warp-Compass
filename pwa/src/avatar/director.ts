/**
 * The bot's director (Phase 12v2) — decides WHAT the bot acts out and when. Purely cosmetic:
 * nothing here touches the runner, the Answer Log, or sync. No AI — a keyword engine whose
 * buckets mirror the ontology's node types (contracts/ontology.json: Problem, System, Role,
 * ApprovalPoint, Event, KPI, Desire…), so the bot visibly "gets" the discovery domain:
 * problems get written down, tools get noted, people get a nod, process words pull it closer.
 *
 * Three channels:
 *  - `reactToAnswer(text)`  — on submit: a gesture + a bubble line ("Noting that down…").
 *  - `glanceAt(text)`       — while typing (throttled at the call site): a quick lean/nod so the
 *                             person sees the bot pick up on what they're saying mid-sentence.
 *  - `useIdleAntics(...)`   — a random scheduler that plays a small antic every ~9–22s of idle
 *                             (tidying its notes, a curious peek, a pod-spin, a nod) so the bot
 *                             never freezes into a template.
 */

import { useEffect, useRef } from "react";
import type { BotGesture } from "./WarpBot";

interface Bucket {
  re: RegExp;
  gesture: BotGesture;
  bubbles: string[];
  /** Chip label for topic hints under the question (reference-UI style). */
  chip?: string;
}

// Order matters: first match wins, so the strongest signals (problems) come first.
const BUCKETS: Bucket[] = [
  {
    // Problem / pain — the ontology's Problem node. The bot writes these down.
    re: /\b(problem|problems|issue|issues|pain|stuck|delay|delayed|delays|block|blocked|bottleneck|manual|manually|error|errors|mistake|fail|fails|failed|slow|frustrat\w*|difficult|hard part|mess|messy|rework|complain\w*|breaks?|broken|waste|wasted)\b/i,
    gesture: "note",
    bubbles: ["Noting that down…", "That sounds painful — writing it down.", "Got it. On the list."],
    chip: "Pain points",
  },
  {
    // Systems / tools — the ontology's System node.
    re: /\b(excel|spreadsheet|sheet|sheets|erp|crm|sap|tally|zoho|salesforce|whatsapp|email|outlook|slack|portal|software|system|systems|tool|tools|app|apps|website|database)\b/i,
    gesture: "note",
    bubbles: ["Adding that tool to my notes…", "Interesting — noting the system."],
    chip: "Tools & systems",
  },
  {
    // Approvals / sign-off — ApprovalPoint.
    re: /\b(approv\w*|sign[- ]?off|authoriz\w*|permission|sanction\w*|clearance)\b/i,
    gesture: "peek",
    bubbles: ["Who signs off on that? Curious…", "An approval step — interesting."],
    chip: "Approvals",
  },
  {
    // People / roles / handoffs — Role, HANDS_OFF_TO, REPORTS_TO.
    re: /\b(manager|boss|team|teammate|colleague|customer|client|vendor|supplier|supervisor|head|lead|director|owner|hand(s|ed)? (it |them )?(over|off)|escalat\w*|reports? to)\b/i,
    gesture: "nod",
    bubbles: ["Mm-hm, I follow.", "Right — good to know who's involved."],
    chip: "People & handoffs",
  },
  {
    // Cadence / triggers — Event node.
    re: /\b(every (day|week|month|morning)|daily|weekly|monthly|quarterly|month[- ]end|deadline|whenever|as soon as|each time)\b/i,
    gesture: "nod",
    bubbles: ["Okay — so that's the rhythm.", "Got the timing."],
    chip: "When it happens",
  },
  {
    // Core process artifacts — Activity/Artifact vocabulary. The bot leans in.
    re: /\b(order|orders|invoice|invoices|quote|quotes|quotation|delivery|dispatch|shipment|payment|payments|purchase|stock|inventory|report|reports|record|entry|entries|ticket|tickets)\b/i,
    gesture: "lean",
    bubbles: ["Tell me more about that…", "Following closely…"],
    chip: "The process",
  },
  {
    // Numbers / metrics — KPI.
    re: /\b(\d+\s*(%|percent|hours?|days?|weeks?|times|units|orders|rupees|lakhs?|crores?)|target|targets|kpi|metric|quota)\b/i,
    gesture: "note",
    bubbles: ["Numbers! Writing those down.", "Noted the figures."],
    chip: "Numbers",
  },
  {
    // Wishes — Desire node.
    re: /\b(wish|hope|would be (great|nice|better)|if only|want(ed)? to|dream|ideally)\b/i,
    gesture: "happy",
    bubbles: ["Ooh, I like where this is going.", "That's a good one to capture."],
    chip: "Wishes",
  },
  {
    // Warmth back for warmth in.
    re: /\b(thanks|thank you|great|awesome|nice|good morning|hello|hi there)\b/i,
    gesture: "happy",
    bubbles: ["Happy to be here!", "😊"],
  },
];

const NEUTRAL_BUBBLES = ["Mm-hm", "Got it", "I see", "Right", "Okay…", "Interesting…"];
let lastNeutral = -1;

const pick = <T,>(arr: T[]): T => arr[Math.floor(Math.random() * arr.length)];

export interface AnswerReaction {
  gesture: BotGesture | null;
  bubble: string;
}

/** On submit: how the bot acknowledges the answer. Long answers impress it; problems worry it. */
export function reactToAnswer(text: string): AnswerReaction {
  const t = text.trim();
  for (const b of BUCKETS) {
    if (b.re.test(t)) return { gesture: b.gesture, bubble: pick(b.bubbles) };
  }
  if (/!\s*$/.test(t)) return { gesture: "happy", bubble: "Oh!" };
  if (/\?\s*$/.test(t)) return { gesture: "peek", bubble: "Hmm…" };
  if (t.length > 220) return { gesture: "note", bubble: "Wow — lots to write down!" };
  let i = Math.floor(Math.random() * NEUTRAL_BUBBLES.length);
  if (i === lastNeutral) i = (i + 1) % NEUTRAL_BUBBLES.length;
  lastNeutral = i;
  return { gesture: "nod", bubble: NEUTRAL_BUBBLES[i] };
}

/** While typing: does the draft contain something worth visibly perking up at? */
export function glanceAt(text: string): BotGesture | null {
  for (const b of BUCKETS) if (b.re.test(text)) return b.gesture === "note" ? "lean" : b.gesture;
  return null;
}

/** Topic chips under the current question, reference-UI style. Falls back to the opener trio. */
export function chipsFor(question: string): string[] {
  const found: string[] = [];
  if (/\b(role|responsible|responsibilit\w*)\b/i.test(question)) found.push("My role");
  if (/\b(day to day|daily|typical day|routine|tasks?)\b/i.test(question)) found.push("Daily tasks");
  for (const b of BUCKETS) {
    if (b.chip && b.re.test(question) && !found.includes(b.chip)) found.push(b.chip);
    if (found.length >= 3) break;
  }
  // Pad to three with the reference trio so the row always feels full.
  for (const d of ["My role", "Daily tasks", "Key responsibilities"]) {
    if (found.length >= 3) break;
    if (!found.includes(d)) found.push(d);
  }
  return found.slice(0, 3);
}

const IDLE_ANTICS: BotGesture[] = ["note", "peek", "spin", "nod", "happy"];

/**
 * Random idle life: while `enabled`, plays a small antic every 9–22s (never the same one twice
 * in a row). `play` receives the gesture; the caller owns showing/clearing it.
 */
export function useIdleAntics(enabled: boolean, play: (g: BotGesture) => void) {
  const playRef = useRef(play);
  playRef.current = play;
  useEffect(() => {
    if (!enabled) return;
    let timer: ReturnType<typeof setTimeout>;
    let last: BotGesture | null = null;
    const schedule = () => {
      timer = setTimeout(() => {
        let g = pick(IDLE_ANTICS);
        if (g === last) g = pick(IDLE_ANTICS);
        last = g;
        if (document.visibilityState === "visible") playRef.current(g);
        schedule();
      }, 9000 + Math.random() * 13000);
    };
    schedule();
    return () => clearTimeout(timer);
  }, [enabled]);
}
