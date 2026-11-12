/** Browser side of the self-hosted proof-of-work bot gate (server:
 * app/pow.py). Solves the registration challenge with WebCrypto — no
 * third-party CAPTCHA, nothing leaves the site. At the default 15 bits this
 * is well under a second on any device; the solver yields between chunks so
 * the form stays responsive, and starts as soon as the register tab opens so
 * the work is usually done before the user finishes typing. */

import { api, type PowChallenge, type PowSolution } from '$lib/api';

const encoder = new TextEncoder();

function leadingZeroBits(bytes: Uint8Array): number {
  let count = 0;
  for (const byte of bytes) {
    if (byte === 0) {
      count += 8;
      continue;
    }
    count += Math.clz32(byte) - 24; // clz32 counts a 32-bit word; bytes use the low 8
    break;
  }
  return count;
}

export async function solveChallenge(
  challenge: PowChallenge,
  onProgress?: (hashes: number) => void
): Promise<PowSolution> {
  const CHUNK = 512;
  for (let number = 0; ; number++) {
    const digest = await crypto.subtle.digest(
      'SHA-256',
      encoder.encode(`${challenge.salt}${number}`)
    );
    if (leadingZeroBits(new Uint8Array(digest)) >= challenge.bits) {
      return { ...challenge, number };
    }
    if (number % CHUNK === CHUNK - 1) {
      onProgress?.(number + 1);
      // Yield to the event loop so typing/rendering never stutters.
      await new Promise((resolve) => setTimeout(resolve, 0));
    }
  }
}

/** Fetch a fresh challenge and solve it. Challenges are single-use and expire
 * in 15 minutes — call again if registration is retried. */
export async function fetchAndSolve(onProgress?: (hashes: number) => void): Promise<PowSolution> {
  return solveChallenge(await api.challenge(), onProgress);
}
