// Pages Function → POST /tts (ElevenLabs text→speech). Logic lives in ./_shared.
import { type Env, handleTts, methodNotAllowed, preflightResponse } from "./_shared";

export const onRequestPost: PagesFunction<Env> = (ctx) => handleTts(ctx.request, ctx.env);
export const onRequestOptions: PagesFunction<Env> = (ctx) => preflightResponse(ctx.env);
export const onRequest: PagesFunction<Env> = (ctx) => methodNotAllowed(ctx.env);
