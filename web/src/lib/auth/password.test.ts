import { describe, expect, it } from 'vitest';
import { sv } from '$lib/i18n/sv';
import { PASSWORD_MIN_LENGTH, validateNewPassword } from './password';

describe('validateNewPassword', () => {
  it('rejects passwords shorter than the minimum length', () => {
    const short = 'a'.repeat(PASSWORD_MIN_LENGTH - 1);
    expect(validateNewPassword(short, short)).toBe(sv['password.too_short']);
  });

  it('rejects mismatching confirmation', () => {
    expect(validateNewPassword('långtochsäkertlösenord', 'långtochsäkertlösenorD')).toBe(
      sv['password.mismatch']
    );
  });

  it('accepts a matching pair of at least the minimum length', () => {
    expect(validateNewPassword('långtochsäkertlösenord', 'långtochsäkertlösenord')).toBeNull();
  });
});
