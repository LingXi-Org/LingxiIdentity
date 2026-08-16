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
  'session.invalid_credentials': { message: '邮箱或密码错误，请检查后重试。', field: 'form' },
  'session.identifier_not_found': { message: '未找到对应账户。', field: 'identifier' },
  'session.interaction_not_found': { message: '本次身份验证已失效，请重新开始。', field: 'form' },
  'session.verification_session_not_found': { message: '验证码会话已失效，请重新获取验证码。', field: 'code' },
  'session.expired': { message: '本次身份验证已过期，请重新开始。', field: 'form' },
  'user.email_already_in_use': { message: '该邮箱已注册，请直接登录。', field: 'identifier' },
  'user.phone_already_in_use': { message: '该手机号已注册，请直接登录。', field: 'identifier' },
  'user.username_already_in_use': { message: '该用户名已被使用。', field: 'identifier' },
  'verification_code.invalid': { message: '验证码错误，请重新输入。', field: 'code' },
  'verification_code.expired': { message: '验证码已过期，请重新获取。', field: 'code' },
  'connector.unavailable': { message: '该登录方式暂时不可用，请稍后重试。', field: 'form' },
  'session.captcha_failed': { message: '安全验证未通过，请完成验证后重试。', field: 'form' },
  'guard.invalid_input': { message: '请检查输入内容后重试。', field: 'form' },
};

export const normalizeExperienceError = (
  error: unknown,
  fallback = '操作失败，请稍后重试。'
): UIError => {
  if (error && typeof error === 'object' && 'code' in error) {
    const candidate = error as { code?: unknown; status?: unknown };
    const code = typeof candidate.code === 'string' ? candidate.code : 'experience.unknown_error';
    const known = messages[code];
    return {
      code,
      message: known?.message ?? fallback,
      status: typeof candidate.status === 'number' ? candidate.status : undefined,
      field: known?.field,
    };
  }

  return { code: 'experience.network_error', message: fallback, field: 'form' };
};
