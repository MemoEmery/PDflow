import "@testing-library/jest-dom/vitest";
import { fetch as ufetch } from "undici";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";
afterEach(cleanup);
const buf = (f: Blob) => new Promise<ArrayBuffer>((res, rej) => { const r = new FileReader(); r.onload = () => res(r.result as ArrayBuffer); r.onerror = rej; r.readAsArrayBuffer(f); });
// monta o multipart "na mão": o FormData do jsdom não é aceito pelo fetch do Node
async function multipart(fd: FormData) {
  const b = "----t" + Math.random().toString(16).slice(2); const parts: Buffer[] = [];
  for (const [k, v] of (fd as any).entries()) {
    if (typeof v === "string") parts.push(Buffer.from(`--${b}\r\nContent-Disposition: form-data; name="${k}"\r\n\r\n${v}\r\n`));
    else parts.push(Buffer.from(`--${b}\r\nContent-Disposition: form-data; name="${k}"; filename="${v.name}"\r\nContent-Type: ${v.type || "application/octet-stream"}\r\n\r\n`), Buffer.from(await buf(v)), Buffer.from("\r\n"));
  }
  parts.push(Buffer.from(`--${b}--\r\n`));
  return { body: Buffer.concat(parts), type: `multipart/form-data; boundary=${b}` };
}
(globalThis as any).fetch = async (input: any, init: any = {}) => {
  const url = typeof input === "string" && input.startsWith("/") ? "http://localhost:8000" + input : input;
  if (init.body && init.body.constructor?.name === "FormData") {
    const m = await multipart(init.body); init = { ...init, body: m.body, headers: { ...(init.headers || {}), "content-type": m.type } };
  }
  return ufetch(url, init);
};
(URL as any).createObjectURL = () => "blob:x";
