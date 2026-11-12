<script lang="ts">
  /** Flat discussion thread (Iteration 4) — used on both the concept page and
   * the proposal review view. Posting requires an identity (login or dev
   * signature); deletion is offered for own posts (and super admins) with an
   * inline confirm. A 404 from the WIP backend degrades to the empty state. */
  import { ApiError, night4, type CommentOut } from '$lib/api';
  import { errorMessage } from '$lib/errors';
  import { formatDate, t } from '$lib/i18n.svelte';
  import { currentUser } from '$lib/user.svelte';

  interface Props {
    kind: 'concept' | 'proposal';
    targetId: string;
  }

  let { kind, targetId }: Props = $props();

  let comments = $state<CommentOut[] | null>(null);
  let loadError = $state<string | null>(null);
  let body = $state('');
  let posting = $state(false);
  let postError = $state<string | null>(null);
  let confirmingId = $state<string | null>(null);
  let deleting = $state(false);
  let deleteError = $state<string | null>(null);

  const canWrite = $derived(currentUser.handle !== '');
  const ordered = $derived(
    [...(comments ?? [])].sort((a, b) => a.created_at.localeCompare(b.created_at))
  );

  async function load(id: string): Promise<void> {
    loadError = null;
    try {
      comments =
        kind === 'concept' ? await night4.conceptComments(id) : await night4.proposalComments(id);
    } catch (e) {
      comments = [];
      if (!(e instanceof ApiError && e.status === 404)) {
        loadError = errorMessage(e);
      }
    }
  }

  $effect(() => {
    const id = targetId;
    comments = null;
    body = '';
    postError = null;
    confirmingId = null;
    deleteError = null;
    load(id);
  });

  async function post(event: SubmitEvent): Promise<void> {
    event.preventDefault();
    if (posting) return;
    if (!body.trim()) {
      postError = t('disc.error_empty');
      return;
    }
    posting = true;
    postError = null;
    try {
      const created =
        kind === 'concept'
          ? await night4.addConceptComment(targetId, body.trim())
          : await night4.addProposalComment(targetId, body.trim());
      comments = [...(comments ?? []), created];
      body = '';
    } catch (e) {
      postError = errorMessage(e);
    } finally {
      posting = false;
    }
  }

  function canDelete(comment: CommentOut): boolean {
    if (!currentUser.handle) return false;
    return currentUser.is_super_admin || comment.created_by?.handle === currentUser.handle;
  }

  async function removeComment(id: string): Promise<void> {
    if (deleting) return;
    deleting = true;
    deleteError = null;
    try {
      await night4.deleteComment(id);
      comments = (comments ?? []).filter((c) => c.id !== id);
      confirmingId = null;
    } catch (e) {
      deleteError = errorMessage(e);
    } finally {
      deleting = false;
    }
  }
</script>

<div class="thread">
  <h2>{t('disc.title')}</h2>

  {#if comments === null}
    <p class="muted ui">{t('disc.loading')}</p>
  {:else if loadError}
    <p class="err ui" role="alert">{t('disc.load_error', { error: loadError })}</p>
  {:else}
    {#if ordered.length === 0}
      <p class="muted ui">{t('disc.empty')}</p>
    {:else}
      <ul class="posts">
        {#each ordered as comment (comment.id)}
          <li class="post">
            <p class="meta ui">
              {#if comment.created_by}
                <a class="author" href="/authors/{comment.created_by.handle}"
                  ><strong>{comment.created_by.display_name}</strong></a
                >
              {:else}
                <strong>{t('tm.unknown_author')}</strong>
              {/if}
              <span class="mono when">{formatDate(comment.created_at)}</span>
              {#if canDelete(comment)}
                {#if confirmingId === comment.id}
                  <span class="confirm" role="alert">
                    {t('disc.delete_q')}
                    <button
                      type="button"
                      class="btn btn-quiet danger"
                      disabled={deleting}
                      onclick={() => removeComment(comment.id)}
                    >
                      {deleting ? t('disc.deleting') : t('common.yes')}
                    </button>
                    <button
                      type="button"
                      class="btn btn-quiet"
                      disabled={deleting}
                      onclick={() => {
                        confirmingId = null;
                        deleteError = null;
                      }}
                    >
                      {t('common.cancel')}
                    </button>
                  </span>
                {:else}
                  <button
                    type="button"
                    class="delete"
                    aria-label={t('disc.delete_aria')}
                    title={t('disc.delete_title')}
                    onclick={() => {
                      confirmingId = comment.id;
                      deleteError = null;
                    }}>×</button
                  >
                {/if}
              {/if}
            </p>
            <p class="body">{comment.body}</p>
          </li>
        {/each}
      </ul>
      {#if deleteError}
        <p class="err ui" role="alert">{t('disc.delete_error', { error: deleteError })}</p>
      {/if}
    {/if}

    {#if canWrite}
      <form class="post-form ui" onsubmit={post} aria-label={t('disc.post_aria')}>
        <textarea
          class="input"
          rows="3"
          maxlength="4000"
          bind:value={body}
          disabled={posting}
          placeholder={t('disc.placeholder')}
          aria-label={t('disc.post_aria')}
        ></textarea>
        {#if postError}
          <p class="err" role="alert">{postError}</p>
        {/if}
        <div class="actions">
          <button type="submit" class="btn btn-primary" disabled={posting}>
            {posting ? t('disc.posting') : t('disc.post')}
          </button>
        </div>
      </form>
    {:else}
      <p class="muted ui">{t('disc.locked_hint')}</p>
    {/if}
  {/if}
</div>

<style>
  .thread {
    max-width: 65ch;
  }

  .thread h2 {
    font-size: var(--text-lg);
  }

  .muted {
    font-size: var(--text-sm);
    color: var(--ink-3);
  }

  .err {
    font-size: var(--text-sm);
    color: var(--del-strong);
  }

  .posts {
    list-style: none;
    padding: 0;
    margin: 0 0 var(--space-4);
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
  }

  .post {
    padding: var(--space-3) var(--space-4);
    border: 1px solid var(--line);
    border-radius: var(--radius-md);
    background: var(--bg-raised);
  }

  .post .meta {
    display: flex;
    align-items: baseline;
    gap: var(--space-3);
    flex-wrap: wrap;
    margin: 0 0 var(--space-2);
    font-size: var(--text-sm);
  }

  .author {
    color: inherit;
    text-decoration-color: color-mix(in srgb, var(--ink-3) 45%, transparent);
  }

  .author:hover {
    color: var(--accent);
  }

  .when {
    color: var(--ink-3);
  }

  .post .body {
    margin: 0;
    white-space: pre-wrap;
  }

  .delete {
    margin-left: auto;
    border: none;
    background: none;
    padding: 0 0.3em;
    font-size: var(--text-sm);
    line-height: 1;
    color: var(--ink-3);
    cursor: pointer;
    border-radius: var(--radius-sm);
    opacity: 0.55;
    transition: opacity 0.15s, color 0.15s;
  }

  .post:hover .delete,
  .delete:focus-visible {
    opacity: 1;
  }

  .delete:hover {
    color: var(--del-strong);
  }

  .confirm {
    margin-left: auto;
    display: inline-flex;
    align-items: center;
    gap: var(--space-2);
    font-size: var(--text-sm);
    color: var(--ink-2);
  }

  .confirm .danger {
    color: var(--del-strong);
  }

  /* Comments are prose — keep the deliberate serif/base-size deviation
     on top of the .input primitive. */
  .post-form textarea {
    width: 100%;
    font-family: var(--font-serif);
    font-size: var(--text-base);
  }

  .post-form .err {
    margin: var(--space-2) 0 0;
  }

  .post-form .actions {
    margin-top: var(--space-2);
  }
</style>
