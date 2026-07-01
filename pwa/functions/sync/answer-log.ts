// Pages Function → POST /sync/answer-log (forward the Answer Log to the Drive-sync Web App).
import { type Env, methodNotAllowed, preflightResponse } from "../_shared";
import { handleSyncPush } from "../_sync";

export const onRequestPost: PagesFunction<Env> = (ctx) => handleSyncPush(ctx.request, ctx.env);
export const onRequestOptions: PagesFunction<Env> = (ctx) => preflightResponse(ctx.env);
export const onRequest: PagesFunction<Env> = (ctx) => methodNotAllowed(ctx.env);
