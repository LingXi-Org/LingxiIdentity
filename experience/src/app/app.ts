import { normalizeExperienceError, type UIError } from '../lib/errors';
import { api, type SubmitResponse } from '../lib/experience-api';
import {
  hasForgotPassword,
  isEmail,
  isPhone,
  passwordPolicyError,
  primarySignUpIdentifier,
  signInMethod,
  type ExperienceSettings,
  type Identifier,
  type Interaction,
  type SocialConnector,
} from '../lib/experience-config';
import '../styles/auth.css';

type View = 'sign-in' | 'register' | 'forgot' | 'register-verify' | 'forgot-verify' | 'callback';

type AppState = {
  settings?: ExperienceSettings;
  interaction?: Interaction;
  view: View;
  identifier?: Identifier;
  verificationId?: string;
  /**
   * Registration passwords are deliberately kept only in page memory between
   * the identifier/password step and the verification-code step. They are
   * never written to localStorage/sessionStorage and disappear on refresh.
   */
  registrationPassword?: string;
  error?: UIError;
  busy: boolean;
};

const escapeHtml = (value: unknown) => String(value ?? '')
  .replaceAll('&', '&amp;')
  .replaceAll('<', '&lt;')
  .replaceAll('>', '&gt;')
  .replaceAll('"', '&quot;')
  .replaceAll("'", '&#039;');

const root = document.querySelector<HTMLElement>('#app');
if (!root) throw new Error('缺少 Lingxi Experience 根节点');

const state: AppState = { view: 'sign-in', busy: false };

const firstScreen = () => {
  const query = new URLSearchParams(window.location.search).get('first_screen');
  if (query === 'register' || window.location.pathname.startsWith('/register')) return 'register' as const;
  if (query === 'reset_password' || window.location.pathname.includes('reset-password')) return 'forgot' as const;
  return undefined;
};

const setUrl = (view: View) => {
  const path = view === 'register' || view === 'register-verify' ? '/register'
    : view === 'forgot' || view === 'forgot-verify' ? '/reset-password' : '/sign-in';
  const query = window.location.search
    .replace(/([?&])first_screen=[^&]*&?/g, '$1')
    .replace(/[?&]$/, '');
  window.history.replaceState({}, '', `${path}${query}`);
};

const identifierLabel = (type: string) => type === 'username' ? '用户名' : type === 'phone' ? '手机号' : '邮箱';

const getPrimaryColor = () => state.settings?.color?.primaryColor ?? '#111111';

const focusFirst = () => {
  window.setTimeout(() => root.querySelector<HTMLElement>('input:not([type="hidden"])')?.focus(), 0);
};

const submitResult = (result: SubmitResponse | undefined) => {
  const redirectTo = result?.redirectTo;
  if (!redirectTo) {
    state.view = 'sign-in';
    state.error = {
      code: 'experience.redirect_missing',
      message: '身份验证已完成，但未收到返回应用的地址。请返回灵犀智学后重试。',
      field: 'form',
    };
    render();
    return;
  }
  const target = new URL(redirectTo, window.location.origin);
  if (target.protocol !== 'http:' && target.protocol !== 'https:') {
    throw new Error('不支持的重定向协议');
  }
  window.location.assign(target.href);
};

const setError = (error: unknown) => {
  state.error = normalizeExperienceError(error);
  state.busy = false;
  render();
};

const errorHtml = () => state.error
  ? `<p class="form-message error" role="alert">${escapeHtml(state.error.message)}</p>`
  : '';

const registrationLegal = `
  <p class="legal">
    注册即表示你同意我们的
    <a href="https://lingxilearn.cn/terms" target="_blank" rel="noopener noreferrer">服务条款</a>
    和
    <a href="https://lingxilearn.cn/privacy" target="_blank" rel="noopener noreferrer">隐私政策</a>
  </p>`;

const shell = (
  title: string,
  description: string,
  content: string,
  footer = '',
  legal = ''
) => {
  const brand = state.settings?.branding?.logoUrl;
  root.innerHTML = `
    <div class="auth-page">
      <section class="auth-card" aria-labelledby="auth-title">
        <header class="auth-header">
          ${brand ? `<img class="brand-logo" src="${escapeHtml(brand)}" alt="灵犀智学" />` : '<div class="brand-mark" aria-hidden="true">L</div>'}
          <h1 id="auth-title">${escapeHtml(title)}</h1>
          <p class="auth-description">${escapeHtml(description)}</p>
        </header>
        ${content}
        ${footer ? `<footer class="auth-footer">${footer}</footer>` : ''}
      </section>
      ${legal}
    </div>`;
  document.documentElement.style.setProperty('--primary', getPrimaryColor());
};

const button = (label: string, disabled = false) => `
  <button class="primary-button" type="submit" ${disabled ? 'disabled' : ''}>
    ${disabled ? '<span class="spinner" aria-hidden="true"></span>' : ''}${escapeHtml(label)}
  </button>`;

const attachPasswordToggles = () => {
  root.querySelectorAll<HTMLButtonElement>('.password-toggle').forEach((toggle) => {
    toggle.addEventListener('click', () => {
      const input = root.querySelector<HTMLInputElement>(`#${toggle.dataset.target}`);
      if (!input) return;
      input.type = input.type === 'password' ? 'text' : 'password';
      toggle.textContent = input.type === 'password' ? '显示' : '隐藏';
    });
  });
};

const renderSignIn = () => {
  const method = state.settings
    && (signInMethod(state.settings, 'email') ?? state.settings.signIn?.methods?.[0]);
  const type = method?.identifier === 'phone' || method?.identifier === 'username'
    ? method.identifier
    : 'email';
  const connectors = state.settings?.socialConnectors ?? [];
  const forgot = hasForgotPassword(state.settings ?? {});
  const content = `
    <form id="sign-in-form" class="auth-form" novalidate>
      <label for="identifier">${identifierLabel(type)}</label>
      <input id="identifier" name="identifier" type="${type === 'email' ? 'email' : 'text'}" autocomplete="${type}" required placeholder="${type === 'email' ? 'name@example.com' : ''}" />
      <label for="password">密码</label>
      <div class="password-wrap">
        <input id="password" name="password" type="password" autocomplete="current-password" required />
        <button type="button" class="password-toggle" data-target="password" aria-label="显示密码">显示</button>
      </div>
      ${forgot ? '<button type="button" class="text-button" data-action="forgot">忘记密码？</button>' : ''}
      ${errorHtml()}
      ${button('登录', state.busy)}
    </form>
    ${connectors.length ? `
      <div class="divider"><span>或使用以下方式继续</span></div>
      <div class="social-list">
        ${connectors.map((connector) => `<button class="social-button" type="button" data-social="${escapeHtml(connector.id)}">${escapeHtml(connector.name ?? connector.target ?? connector.id)}</button>`).join('')}
      </div>` : ''}`;
  const footer = state.settings?.signUp?.identifiers?.length
    ? '还没有账户？ <button type="button" class="text-button" data-action="register">立即注册</button>'
    : '';
  shell('欢迎回来', '登录你的灵犀智学账户', content, footer);

  root.querySelector<HTMLFormElement>('#sign-in-form')?.addEventListener('submit', async (event) => {
    event.preventDefault();
    state.error = undefined;
    const form = new FormData(event.currentTarget as HTMLFormElement);
    const value = String(form.get('identifier') ?? '').trim();
    const password = String(form.get('password') ?? '');
    if ((type === 'email' && !isEmail(value)) || (type === 'phone' && !isPhone(value)) || !value) {
      state.error = {
        code: 'guard.invalid_input',
        message: `请输入有效的${identifierLabel(type)}。`,
        field: 'identifier',
      };
      render();
      return;
    }
    if (!password) {
      state.error = { code: 'guard.invalid_input', message: '请输入密码。', field: 'password' };
      render();
      return;
    }
    state.busy = true;
    render();
    try {
      submitResult(await api.signIn({ type: type as Identifier['type'], value }, password));
    } catch (error) {
      setError(error);
    }
  });
  attachActions();
  attachSocial(connectors);
  attachPasswordToggles();
  focusFirst();
};

const renderRegister = () => {
  const type = primarySignUpIdentifier(state.settings ?? {});
  const passwordRequired = state.settings?.signUp?.password !== false;
  const policy = state.settings?.passwordPolicy;
  const policyText = policy?.length?.min ? `密码至少需要 ${policy.length.min} 个字符。` : '';
  const content = `
    <form id="register-form" class="auth-form" novalidate>
      <label for="identifier">${identifierLabel(type)}</label>
      <input id="identifier" name="identifier" type="${type === 'email' ? 'email' : 'text'}" autocomplete="${type}" required placeholder="${type === 'email' ? 'name@example.com' : ''}" />
      ${passwordRequired ? `
        <label for="password">密码</label>
        <div class="password-wrap">
          <input id="password" name="password" type="password" autocomplete="new-password" required />
          <button type="button" class="password-toggle" data-target="password" aria-label="显示密码">显示</button>
        </div>` : ''}
      ${policyText ? `<p class="field-hint">${escapeHtml(policyText)}</p>` : ''}
      ${errorHtml()}
      ${button(type === 'email' || type === 'phone' ? '继续并发送验证码' : '创建账户', state.busy)}
    </form>`;
  shell(
    '创建账户',
    '注册灵犀智学账户',
    content,
    '已有账户？ <button type="button" class="text-button" data-action="signin">返回登录</button>',
    registrationLegal
  );

  root.querySelector<HTMLFormElement>('#register-form')?.addEventListener('submit', async (event) => {
    event.preventDefault();
    state.error = undefined;
    const form = new FormData(event.currentTarget as HTMLFormElement);
    const value = String(form.get('identifier') ?? '').trim();
    const password = String(form.get('password') ?? '');
    if ((type === 'email' && !isEmail(value)) || (type === 'phone' && !isPhone(value)) || !value) {
      state.error = {
        code: 'guard.invalid_input',
        message: `请输入有效的${identifierLabel(type)}。`,
        field: 'identifier',
      };
      render();
      return;
    }
    if (passwordRequired && !password) {
      state.error = { code: 'guard.invalid_input', message: '请设置密码。', field: 'password' };
      render();
      return;
    }
    const passwordPolicyMessage = passwordRequired
      ? passwordPolicyError(state.settings?.passwordPolicy, password)
      : undefined;
    if (passwordPolicyMessage) {
      state.error = { code: 'guard.invalid_input', message: passwordPolicyMessage, field: 'password' };
      render();
      return;
    }

    state.identifier = { type, value };
    state.registrationPassword = passwordRequired ? password : undefined;
    state.busy = true;
    render();
    try {
      const verification = await api.beginRegistration(
        state.identifier,
        state.settings?.signUp?.verify !== false
      );
      if (!verification) {
        if (state.registrationPassword) {
          await api.updateProfile({ type: 'password', value: state.registrationPassword });
        }
        await api.identify();
        const result = await api.submit();
        state.registrationPassword = undefined;
        submitResult(result);
        return;
      }
      state.verificationId = verification.verificationId;
      state.busy = false;
      state.view = 'register-verify';
      setUrl(state.view);
      render();
    } catch (error) {
      setError(error);
    }
  });
  attachActions();
  attachPasswordToggles();
  focusFirst();
};

const renderRegisterVerify = () => {
  const passwordRequired = state.settings?.signUp?.password !== false;
  if (!state.identifier || !state.verificationId || (passwordRequired && !state.registrationPassword)) {
    state.view = 'register';
    state.identifier = undefined;
    state.verificationId = undefined;
    state.registrationPassword = undefined;
    state.error = {
      code: 'session.verification_session_not_found',
      message: '注册页面已刷新，请重新填写邮箱和密码以继续。',
      field: 'form',
    };
    setUrl(state.view);
    render();
    return;
  }

  const content = `
    <form id="register-verify-form" class="auth-form" novalidate>
      <p class="step-note">验证码已发送至 <strong>${escapeHtml(state.identifier.value)}</strong></p>
      <label for="code">验证码</label>
      <input id="code" name="code" inputmode="numeric" autocomplete="one-time-code" required />
      ${errorHtml()}
      ${button('验证并完成注册', state.busy)}
    </form>`;
  shell(
    state.identifier.type === 'phone' ? '验证手机号' : '验证邮箱',
    '输入收到的验证码即可完成注册，无需再次输入密码。',
    content,
    `<button type="button" class="text-button" data-action="register">更换${identifierLabel(state.identifier.type)}</button>`,
    registrationLegal
  );

  root.querySelector<HTMLFormElement>('#register-verify-form')?.addEventListener('submit', async (event) => {
    event.preventDefault();
    state.error = undefined;
    const form = new FormData(event.currentTarget as HTMLFormElement);
    const code = String(form.get('code') ?? '').trim();
    if (!code || !state.identifier || !state.verificationId) {
      state.error = { code: 'guard.invalid_input', message: '请输入验证码。', field: 'code' };
      render();
      return;
    }
    state.busy = true;
    render();
    try {
      const result = await api.finishRegistration(
        state.identifier,
        state.verificationId,
        code,
        state.registrationPassword
      );
      state.registrationPassword = undefined;
      submitResult(result);
    } catch (error) {
      setError(error);
    }
  });
  attachActions();
  focusFirst();
};

const renderForgot = () => {
  const emailEnabled = Boolean(state.settings?.forgotPassword?.email);
  const phoneEnabled = Boolean(state.settings?.forgotPassword?.phone);
  const bothEnabled = emailEnabled && phoneEnabled;
  const type = phoneEnabled && !emailEnabled ? 'phone' : 'email';
  const content = `
    <form id="forgot-form" class="auth-form" novalidate>
      ${bothEnabled ? '<label for="identifier-type">找回方式</label><select id="identifier-type" name="identifier-type"><option value="email">邮箱</option><option value="phone">手机号</option></select>' : ''}
      <label for="identifier">${identifierLabel(type)}</label>
      <input id="identifier" name="identifier" type="${type === 'email' ? 'email' : 'text'}" autocomplete="${type}" required />
      ${errorHtml()}
      ${button('发送验证码', state.busy)}
    </form>`;
  shell(
    '重置密码',
    '我们会向已验证的账户发送验证码',
    content,
    '<button type="button" class="text-button" data-action="signin">返回登录</button>'
  );

  root.querySelector<HTMLFormElement>('#forgot-form')?.addEventListener('submit', async (event) => {
    event.preventDefault();
    state.error = undefined;
    const form = new FormData(event.currentTarget as HTMLFormElement);
    const selectedType = String(form.get('identifier-type') ?? type);
    const selectedIdentifierType = selectedType === 'phone' ? 'phone' : 'email';
    const value = String(form.get('identifier') ?? '').trim();
    if ((selectedIdentifierType === 'email' && !isEmail(value))
      || (selectedIdentifierType === 'phone' && !isPhone(value))) {
      state.error = {
        code: 'guard.invalid_input',
        message: `请输入有效的${identifierLabel(selectedIdentifierType)}。`,
        field: 'identifier',
      };
      render();
      return;
    }
    state.identifier = { type: selectedIdentifierType, value };
    state.busy = true;
    render();
    try {
      const verification = await api.beginForgotPassword(state.identifier);
      state.verificationId = verification.verificationId;
      state.busy = false;
      state.view = 'forgot-verify';
      setUrl(state.view);
      render();
    } catch (error) {
      setError(error);
    }
  });

  root.querySelector<HTMLSelectElement>('#identifier-type')?.addEventListener('change', (event) => {
    const selected = (event.currentTarget as HTMLSelectElement).value === 'phone' ? 'phone' : 'email';
    const input = root.querySelector<HTMLInputElement>('#identifier');
    const label = root.querySelector<HTMLLabelElement>('label[for="identifier"]');
    if (input) {
      input.type = selected === 'email' ? 'email' : 'text';
      input.setAttribute('autocomplete', selected);
    }
    if (label) label.textContent = identifierLabel(selected);
  });
  attachActions();
  focusFirst();
};

const renderForgotVerify = () => {
  const content = `
    <form id="forgot-verify-form" class="auth-form" novalidate>
      <p class="step-note">验证码已发送至 <strong>${escapeHtml(state.identifier?.value)}</strong></p>
      <label for="code">验证码</label>
      <input id="code" name="code" inputmode="numeric" autocomplete="one-time-code" required />
      <label for="password">新密码</label>
      <div class="password-wrap">
        <input id="password" name="password" type="password" autocomplete="new-password" required />
        <button type="button" class="password-toggle" data-target="password">显示</button>
      </div>
      <label for="confirm">确认新密码</label>
      <input id="confirm" name="confirm" type="password" autocomplete="new-password" required />
      ${errorHtml()}
      ${button('重置密码', state.busy)}
    </form>`;
  shell(
    '设置新密码',
    '请设置一个新的账户密码',
    content,
    '<button type="button" class="text-button" data-action="signin">返回登录</button>'
  );

  root.querySelector<HTMLFormElement>('#forgot-verify-form')?.addEventListener('submit', async (event) => {
    event.preventDefault();
    state.error = undefined;
    const form = new FormData(event.currentTarget as HTMLFormElement);
    const code = String(form.get('code') ?? '').trim();
    const password = String(form.get('password') ?? '');
    const confirm = String(form.get('confirm') ?? '');
    if (!code || !password || password !== confirm || !state.identifier || !state.verificationId) {
      state.error = {
        code: 'guard.invalid_input',
        message: password !== confirm ? '两次输入的密码不一致。' : '请输入验证码和新密码。',
        field: 'form',
      };
      render();
      return;
    }
    const passwordPolicyMessage = passwordPolicyError(state.settings?.passwordPolicy, password);
    if (passwordPolicyMessage) {
      state.error = { code: 'guard.invalid_input', message: passwordPolicyMessage, field: 'password' };
      render();
      return;
    }
    state.busy = true;
    render();
    try {
      submitResult(await api.finishForgotPassword(
        state.identifier,
        state.verificationId,
        code,
        password
      ));
    } catch (error) {
      setError(error);
    }
  });
  attachActions();
  attachPasswordToggles();
  focusFirst();
};

const attachSocial = (connectors: SocialConnector[]) => {
  root.querySelectorAll<HTMLButtonElement>('[data-social]').forEach((buttonElement) => {
    buttonElement.addEventListener('click', async () => {
      const connector = connectors.find((item) => item.id === buttonElement.dataset.social);
      if (!connector) return;
      state.busy = true;
      render();
      try {
        window.location.assign(await api.socialAuthorization(connector));
      } catch (error) {
        setError(error);
      }
    });
  });
};

const attachActions = () => {
  root.querySelectorAll<HTMLElement>('[data-action]').forEach((element) => {
    element.addEventListener('click', () => {
      const action = element.dataset.action;
      state.error = undefined;
      state.busy = false;
      state.identifier = undefined;
      state.verificationId = undefined;
      state.registrationPassword = undefined;
      if (action === 'register') state.view = 'register';
      if (action === 'signin') state.view = 'sign-in';
      if (action === 'forgot') state.view = 'forgot';
      setUrl(state.view);
      render();
    });
  });
};

const renderCallback = async () => {
  shell(
    '正在登录',
    '正在完成第三方身份验证',
    '<div class="loading-panel"><span class="spinner"></span> 请稍候…</div>'
  );
  const match = window.location.pathname.match(/^\/callback\/social\/([^/]+)/);
  if (!match) {
    state.view = 'sign-in';
    setError({ code: 'session.invalid_callback', message: '无效的第三方登录回调。' });
    return;
  }
  try {
    submitResult(await api.completeSocialCallback(
      decodeURIComponent(match[1]),
      new URLSearchParams(window.location.search)
    ));
  } catch (error) {
    state.view = 'sign-in';
    setError(error);
  }
};

const render = () => {
  if (state.view === 'callback') {
    void renderCallback();
    return;
  }
  if (state.view === 'register') return renderRegister();
  if (state.view === 'register-verify') return renderRegisterVerify();
  if (state.view === 'forgot') return renderForgot();
  if (state.view === 'forgot-verify') return renderForgotVerify();
  return renderSignIn();
};

const restoreInteractionView = () => {
  const event = state.interaction?.interactionEvent;
  const pending = state.interaction?.verificationRecords?.find((record) =>
    (record.type === 'EmailVerificationCode' || record.type === 'PhoneVerificationCode')
      && !record.verified
  );
  if (pending?.identifier && pending.id && event === 'ForgotPassword') {
    state.identifier = pending.identifier;
    state.verificationId = pending.id;
    return 'forgot-verify' as const;
  }
  // Registration passwords are intentionally not persisted. After a refresh,
  // restart the short registration step instead of asking for the password a
  // second time on the verification-code screen.
  if (event === 'Register') return 'register' as const;
  if (event === 'ForgotPassword') return 'forgot' as const;
  return 'sign-in' as const;
};

export const startExperience = async () => {
  shell(
    '正在加载',
    '正在准备安全的身份验证流程',
    '<div class="loading-panel"><span class="spinner"></span> 加载中…</div>'
  );
  try {
    state.settings = await api.getSettings();
    if (window.location.pathname.startsWith('/callback/social/')) {
      state.view = 'callback';
      render();
      return;
    }
    try {
      state.interaction = await api.getInteraction();
    } catch (error) {
      const normalized = normalizeExperienceError(error);
      if (normalized.status !== 404 && normalized.code !== 'session.interaction_not_found') {
        throw error;
      }
    }
    state.view = firstScreen() ?? restoreInteractionView();
    render();
  } catch (error) {
    setError(error);
  }
};
