<script lang="ts">
  /** The one way to render an icon (ui-guardrails §15). Decorative by
   * default (aria-hidden); pass `label` to make it meaningful. Color comes
   * from currentColor — set semantic state color on the parent. */
  import { iconMarkup, type IconName } from './icons';

  let {
    name,
    filled = false,
    size = 14,
    label
  }: { name: IconName; filled?: boolean; size?: number; label?: string } = $props();
</script>

{#if label}
  <svg viewBox="0 0 20 20" width={size} height={size} role="img" aria-label={label}>
    {@html iconMarkup(name, filled)}
  </svg>
{:else}
  <svg viewBox="0 0 20 20" width={size} height={size} aria-hidden="true">
    {@html iconMarkup(name, filled)}
  </svg>
{/if}
