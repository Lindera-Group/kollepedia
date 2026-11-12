import type { Features } from '$lib/features';

declare global {
  namespace App {
    // interface Error {}
    // interface Locals {}
    interface PageData {
      /** Feature flags from the root layout's server load (lib/features.ts). */
      features?: Features;
    }
  }
}

export {};
