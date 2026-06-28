/**
 * Phase 7 voice-seam tests. The mic + audio playback need a browser (MediaRecorder / Audio), so
 * they're exercised by hand on a device; here we cover the Worker-routed provider contracts with a
 * stubbed `fetch`:
 *  - STT POSTs the audio bytes and returns the `{ text }` transcript, trimmed;
 *  - STT surfaces HTTP errors and refuses empty audio;
 *  - TTS POSTs `{ text }` and returns the audio blob; it surfaces HTTP errors and refuses empty text.
 */

import { afterEach, describe, expect, it, vi } from "vitest";
import { WorkerSTTProvider } from "./stt";
import { WorkerTTSProvider } from "./tts";
import { VoiceError } from "./types";

afterEach(() => {
  vi.restoreAllMocks();
});

describe("WorkerSTTProvider", () => {
  it("POSTs audio bytes to /stt and returns the trimmed transcript", async () => {
    const fetchMock = vi.fn(async (_url: string, _init: RequestInit) =>
      new Response(JSON.stringify({ text: "  hello there  " }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const stt = new WorkerSTTProvider({ baseUrl: "http://localhost:8787" });
    const text = await stt.transcribe(new Blob(["abc"], { type: "audio/webm" }));

    expect(text).toBe("hello there");
    expect(fetchMock).toHaveBeenCalledOnce();
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("http://localhost:8787/stt");
    expect(init.method).toBe("POST");
    expect((init.headers as Record<string, string>)["Content-Type"]).toBe("audio/webm");
  });

  it("refuses empty audio without calling the network", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    const stt = new WorkerSTTProvider();
    await expect(stt.transcribe(new Blob([]))).rejects.toBeInstanceOf(VoiceError);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("throws a VoiceError on an HTTP error", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response("nope", { status: 502 })),
    );
    const stt = new WorkerSTTProvider();
    await expect(stt.transcribe(new Blob(["x"], { type: "audio/webm" }))).rejects.toBeInstanceOf(
      VoiceError,
    );
  });
});

describe("WorkerTTSProvider", () => {
  it("POSTs the text to /tts and returns the audio blob", async () => {
    const audioBytes = new Uint8Array([1, 2, 3]);
    const fetchMock = vi.fn(async (_url: string, _init: RequestInit) =>
      new Response(audioBytes, { status: 200, headers: { "Content-Type": "audio/mpeg" } }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const tts = new WorkerTTSProvider();
    const blob = await tts.synthesize("speak this");

    expect(blob).toBeInstanceOf(Blob);
    expect(blob.size).toBe(3);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/tts");
    expect(JSON.parse(init.body as string)).toEqual({ text: "speak this" });
  });

  it("refuses empty text without calling the network", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    const tts = new WorkerTTSProvider();
    await expect(tts.synthesize("   ")).rejects.toBeInstanceOf(VoiceError);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("throws a VoiceError on an HTTP error", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response("rate limited", { status: 429 })),
    );
    const tts = new WorkerTTSProvider();
    await expect(tts.synthesize("hi")).rejects.toBeInstanceOf(VoiceError);
  });
});
