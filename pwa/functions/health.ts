// Pages Function → GET /health (liveness check). Logic lives in ./_shared.
import { type Env, healthResponse, preflightResponse } from "./_shared";

export const onRequest: PagesFunction<Env> = (ctx) =>
  ctx.request.method === "OPTIONS" ? preflightResponse(ctx.env) : healthResponse(ctx.env);
