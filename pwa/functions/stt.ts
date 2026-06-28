// Pages Function → POST /stt (ElevenLabs Scribe speech→text). Logic lives in ./_shared.
import { type Env, handleStt, methodNotAllowed, preflightResponse } from "./_shared";

export const onRequestPost: PagesFunction<Env> = (ctx) => handleStt(ctx.request, ctx.env);
export const onRequestOptions: PagesFunction<Env> = (ctx) => preflightResponse(ctx.env);
export const onRequest: PagesFunction<Env> = (ctx) => methodNotAllowed(ctx.env);
