// Pages Function → GET /sync/brief?participant_id=… (fetch the participant's latest Session Brief).
import { type Env, methodNotAllowed, preflightResponse } from "../_shared";
import { handleSyncPull } from "../_sync";

export const onRequestGet: PagesFunction<Env> = (ctx) => handleSyncPull(ctx.request, ctx.env);
export const onRequestOptions: PagesFunction<Env> = (ctx) => preflightResponse(ctx.env);
export const onRequest: PagesFunction<Env> = (ctx) => methodNotAllowed(ctx.env);
