export type ExperienceErrorCode =
  | 'session.invalid_credentials'
  | 'session.interaction_not_found'
  | 'session.identifier_not_found'
  | 'session.verification_session_not_found'
  | 'session.expired'
  | 'user.email_already_in_use'
  | 'user.phone_already_in_use'
  | 'user.username_already_in_use'
  | 'guard.invalid_input'
  | 'verification_code.invalid'
  | 'verification_code.expired'
  | 'connector.unavailable'
  | 'session.captcha_failed'
  | (string & {});

export type UIError = {
  code: ExperienceErrorCode;
  message: string;
  status?: number;
  field?: 'identifier' | 'password' | 'code' | 'form';
};

const messages: Record<string, { message: string; field?: UIError['field'] }> = {
  'session.invalid_credentials': { message: 'The email or password is incorrect.', field: 'form' },
  'session.identifier_not_found': { message: 'We could not find that account.', field: 'identifier' },
  'session.interaction_not_found': { message: 'This sign-in session has expired. Start again.', field: 'form' },
  'session.verification_session_not_found': { message: 'This verification session has expired. Start again.', field: 'code' },
  'session.expired': { message: 'This sign-in session has expired. Start again.', field: 'form' },
  'user.email_already_in_use': { message: 'An account with this email already exists.', field: 'identifier' },
  'user.phone_already_in_use': { message: 'An account with this phone number already exists.', field: 'identifier' },
  'user.username_already_in_use': { message: 'That username is already in use.', field: 'identifier' },
  'verification_code.invalid': { message: 'That verification code is not correct.', field: 'code' },
  'verification_code.expired': { message: 'That verification code has expired. Request a new one.', field: 'code' },
  'connector.unavailable': { message: 'This sign-in provider is temporarily unavailable.', field: 'form' },
  'session.captcha_failed': { message: 'Please complete the verification challenge and try again.', field: 'form' },
  'guard.invalid_input': { message: 'Check the highlighted fields and try again.', field: 'form' },
};

export const normalizeExperienceError = (
  error: unknown,
  fallback = 'Something went wrong. Please try again.'
): UIError => {
  if (error && typeof error === 'object' && 'code' in error) {
    const candidate = error as { code?: unknown; status?: unknown; message?: unknown };
    const code = typeof candidate.code === 'string' ? candidate.code : 'experience.unknown_error';
    const known = messages[code];
    return {
      code,
      message: known?.message ?? (typeof candidate.message === 'string' ? candidate.message : fallback),
      status: typeof candidate.status === 'number' ? candidate.status : undefined,
      field: known?.field,
    };
  }

  return { code: 'experience.network_error', message: fallback, field: 'form' };
};
