// Pages Function → POST /llm (DeepSeek live forwarder). Logic lives in ./_shared.
import { type Env, handleLlm, methodNotAllowed, preflightResponse } from "./_shared";

export const onRequestPost: PagesFunction<Env> = (ctx) => handleLlm(ctx.request, ctx.env);
export const onRequestOptions: PagesFunction<Env> = (ctx) => preflightResponse(ctx.env);
export const onRequest: PagesFunction<Env> = (ctx) => methodNotAllowed(ctx.env);
