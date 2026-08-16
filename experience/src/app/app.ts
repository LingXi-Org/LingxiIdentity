import { normalizeExperienceError, type UIError } from '../lib/errors';
import {
  api,
  type SubmitResponse,
} from '../lib/experience-api';
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
if (!root) throw new Error('Lingxi Experience app root is missing');

const state: AppState = { view: 'sign-in', busy: false };

const firstScreen = () => {
  const query = new URLSearchParams(window.location.search).get('first_screen');
  if (query === 'register' || window.location.pathname.startsWith('/register')) return 'register' as const;
  if (query === 'reset_password' || window.location.pathname.includes('reset-password')) return 'forgot' as const;
  return undefined;
};

const interactionRecord = (type: string) =>
  state.interaction?.verificationRecords?.find((record) => record.type === type);

const setUrl = (view: View) => {
  const path = view === 'register' || view === 'register-verify' ? '/register'
    : view === 'forgot' || view === 'forgot-verify' ? '/reset-password' : '/sign-in';
  const query = window.location.search
    .replace(/([?&])first_screen=[^&]*&?/g, '$1')
    .replace(/[?&]$/, '');
  window.history.replaceState({}, '', `${path}${query}`);
};

const identifierLabel = (type: string) => type === 'username' ? 'Username' : type === 'phone' ? 'Phone number' : 'Email';

const getPrimaryColor = () => state.settings?.color?.primaryColor ?? '#111111';

const focusFirst = () => {
  window.setTimeout(() => root.querySelector<HTMLElement>('input:not([type="hidden"])')?.focus(), 0);
};

const submitResult = (result: SubmitResponse | undefined) => {
  const redirectTo = result?.redirectTo;
  if (!redirectTo) {
    state.view = 'sign-in';
    state.error = { code: 'experience.redirect_missing', message: 'Sign-in completed. Return to the application to continue.', field: 'form' };
    render();
    return;
  }
  const target = new URL(redirectTo, window.location.origin);
  if (target.protocol !== 'http:' && target.protocol !== 'https:') {
    throw new Error('Unsupported redirect protocol');
  }
  window.location.assign(target.href);
};

const setError = (error: unknown) => {
  state.error = normalizeExperienceError(error);
  state.busy = false;
  render();
};

const errorHtml = () => state.error ? `<p class="form-message error" role="alert">${escapeHtml(state.error.message)}</p>` : '';

const shell = (title: string, description: string, content: string, footer = '') => {
  const brand = state.settings?.branding?.logoUrl;
  root.innerHTML = `
    <div class="auth-page">
      <section class="auth-card" aria-labelledby="auth-title">
        <header class="auth-header">
          ${brand ? `<img class="brand-logo" src="${escapeHtml(brand)}" alt="Lingxi" />` : '<div class="brand-mark" aria-hidden="true">L</div>'}
          <h1 id="auth-title">${escapeHtml(title)}</h1>
          <p class="auth-description">${escapeHtml(description)}</p>
        </header>
        ${content}
        ${footer ? `<footer class="auth-footer">${footer}</footer>` : ''}
      </section>
      <p class="legal">By continuing, you agree to the Lingxi terms and privacy policy.</p>
    </div>`;
  document.documentElement.style.setProperty('--primary', getPrimaryColor());
};

const button = (label: string, disabled = false) => `<button class="primary-button" type="submit" ${disabled ? 'disabled' : ''}>${disabled ? '<span class="spinner" aria-hidden="true"></span>' : ''}${escapeHtml(label)}</button>`;

const renderSignIn = () => {
  const method = state.settings && (signInMethod(state.settings, 'email') ?? state.settings.signIn?.methods?.[0]);
  const type = method?.identifier === 'phone' || method?.identifier === 'username' ? method.identifier : 'email';
  const connectors = state.settings?.socialConnectors ?? [];
  const forgot = hasForgotPassword(state.settings ?? {});
  const content = `
    <form id="sign-in-form" class="auth-form" novalidate>
      <label for="identifier">${identifierLabel(type)}</label>
      <input id="identifier" name="identifier" type="${type === 'email' ? 'email' : 'text'}" autocomplete="${type}" required placeholder="${type === 'email' ? 'you@example.com' : ''}" />
      <label for="password">Password</label>
      <div class="password-wrap"><input id="password" name="password" type="password" autocomplete="current-password" required /><button type="button" class="password-toggle" data-target="password" aria-label="Show password">Show</button></div>
      ${forgot ? '<button type="button" class="text-button" data-action="forgot">Forgot password?</button>' : ''}
      ${errorHtml()}
      ${button('Continue', state.busy)}
    </form>
    ${connectors.length ? `<div class="divider"><span>or continue with</span></div><div class="social-list">${connectors.map((connector) => `<button class="social-button" type="button" data-social="${escapeHtml(connector.id)}">${escapeHtml(connector.name ?? connector.target ?? connector.id)}</button>`).join('')}</div>` : ''}`;
  const footer = state.settings?.signUp?.identifiers?.length ? `Don't have an account? <button type="button" class="text-button" data-action="register">Create account</button>` : '';
  shell('Welcome back', 'Sign in to continue to Lingxi.', content, footer);
  root.querySelector<HTMLFormElement>('#sign-in-form')?.addEventListener('submit', async (event) => {
    event.preventDefault();
    state.error = undefined;
    const form = new FormData(event.currentTarget as HTMLFormElement);
    const value = String(form.get('identifier') ?? '').trim();
    const password = String(form.get('password') ?? '');
    if ((type === 'email' && !isEmail(value)) || (type === 'phone' && !isPhone(value)) || !value) {
      state.error = { code: 'guard.invalid_input', message: `Enter a valid ${identifierLabel(type).toLowerCase()}.`, field: 'identifier' };
      render();
      return;
    }
    if (!password) {
      state.error = { code: 'guard.invalid_input', message: 'Enter your password.', field: 'password' };
      render();
      return;
    }
    state.busy = true;
    render();
    try {
      submitResult(await api.signIn({ type: type as Identifier['type'], value }, password));
    } catch (error) { setError(error); }
  });
  attachActions();
  attachSocial(connectors);
  focusFirst();
};

const renderRegister = () => {
  const type = primarySignUpIdentifier(state.settings ?? {});
  const passwordRequired = state.settings?.signUp?.password !== false;
  const policy = state.settings?.passwordPolicy;
  const policyText = policy?.length?.min ? `Password must be at least ${policy.length.min} characters.` : '';
  const content = `
    <form id="register-form" class="auth-form" novalidate>
      <label for="identifier">${identifierLabel(type)}</label>
      <input id="identifier" name="identifier" type="${type === 'email' ? 'email' : 'text'}" autocomplete="${type}" required />
      ${passwordRequired ? '<label for="password">Password</label><div class="password-wrap"><input id="password" name="password" type="password" autocomplete="new-password" required /><button type="button" class="password-toggle" data-target="password" aria-label="Show password">Show</button></div>' : ''}
      ${policyText ? `<p class="field-hint">${escapeHtml(policyText)}</p>` : ''}
      ${errorHtml()}
      ${button('Create account', state.busy)}
    </form>`;
  shell('Create your account', 'Start building with Lingxi.', content, 'Already have an account? <button type="button" class="text-button" data-action="signin">Sign in</button>');
  root.querySelector<HTMLFormElement>('#register-form')?.addEventListener('submit', async (event) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget as HTMLFormElement);
    const value = String(form.get('identifier') ?? '').trim();
    const password = String(form.get('password') ?? '');
    if ((type === 'email' && !isEmail(value)) || (type === 'phone' && !isPhone(value)) || !value) {
      state.error = { code: 'guard.invalid_input', message: `Enter a valid ${identifierLabel(type).toLowerCase()}.`, field: 'identifier' };
      render();
      return;
    }
    if (passwordRequired && !password) {
      state.error = { code: 'guard.invalid_input', message: 'Choose a password.', field: 'password' };
      render();
      return;
    }
    const passwordPolicyMessage = passwordRequired
      ? passwordPolicyError(state.settings?.passwordPolicy, password ?? '')
      : undefined;
    if (passwordPolicyMessage) {
      state.error = { code: 'guard.invalid_input', message: passwordPolicyMessage, field: 'password' };
      render();
      return;
    }
    state.busy = true;
    state.identifier = { type, value };
    render();
    try {
      const verification = await api.beginRegistration(state.identifier, state.settings?.signUp?.verify !== false);
      if (!verification) {
        if (password) await api.updateProfile({ type: 'password', value: password });
        await api.identify();
        submitResult(await api.submit());
        return;
      }
      state.verificationId = verification.verificationId;
      state.busy = false;
      state.view = 'register-verify';
      setUrl(state.view);
      render();
    } catch (error) { setError(error); }
  });
  attachActions();
  root.querySelectorAll<HTMLButtonElement>('.password-toggle').forEach((toggle) => toggle.addEventListener('click', () => {
    const input = root.querySelector<HTMLInputElement>(`#${toggle.dataset.target}`);
    if (input) { input.type = input.type === 'password' ? 'text' : 'password'; toggle.textContent = input.type === 'password' ? 'Show' : 'Hide'; }
  }));
  focusFirst();
};

const renderRegisterVerify = () => {
  const passwordRequired = state.settings?.signUp?.password !== false;
  const content = `
    <form id="register-verify-form" class="auth-form" novalidate>
      <p class="step-note">We sent a verification code to <strong>${escapeHtml(state.identifier?.value)}</strong>.</p>
      <label for="code">Verification code</label>
      <input id="code" name="code" inputmode="numeric" autocomplete="one-time-code" required />
      ${passwordRequired ? '<label for="password">Password</label><div class="password-wrap"><input id="password" name="password" type="password" autocomplete="new-password" required /><button type="button" class="password-toggle" data-target="password">Show</button></div>' : ''}
      ${errorHtml()}
      ${button('Verify and create account', state.busy)}
    </form>`;
  shell('Verify your email', 'Enter the code to finish creating your account.', content, '<button type="button" class="text-button" data-action="register">Use a different email</button>');
  root.querySelector<HTMLFormElement>('#register-verify-form')?.addEventListener('submit', async (event) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget as HTMLFormElement);
    const code = String(form.get('code') ?? '').trim();
    const password = passwordRequired ? String(form.get('password') ?? '') : undefined;
    if (!code || !state.identifier || !state.verificationId || (passwordRequired && !password)) {
      state.error = {
        code: 'guard.invalid_input',
        message: passwordRequired ? 'Enter the code and choose a password.' : 'Enter the verification code.',
        field: 'form',
      };
      render();
      return;
    }
    const passwordPolicyMessage = passwordRequired
      ? passwordPolicyError(state.settings?.passwordPolicy, password ?? '')
      : undefined;
    if (passwordPolicyMessage) {
      state.error = { code: 'guard.invalid_input', message: passwordPolicyMessage, field: 'password' };
      render();
      return;
    }
    state.busy = true;
    render();
    try { submitResult(await api.finishRegistration(state.identifier, state.verificationId, code, password)); } catch (error) { setError(error); }
  });
  attachActions();
  root.querySelectorAll<HTMLButtonElement>('.password-toggle').forEach((toggle) => toggle.addEventListener('click', () => {
    const input = root.querySelector<HTMLInputElement>(`#${toggle.dataset.target}`);
    if (input) { input.type = input.type === 'password' ? 'text' : 'password'; toggle.textContent = input.type === 'password' ? 'Show' : 'Hide'; }
  }));
  focusFirst();
};

const renderForgot = () => {
  const emailEnabled = Boolean(state.settings?.forgotPassword?.email);
  const phoneEnabled = Boolean(state.settings?.forgotPassword?.phone);
  const bothEnabled = emailEnabled && phoneEnabled;
  const type = phoneEnabled && !emailEnabled ? 'phone' : 'email';
  const content = `
    <form id="forgot-form" class="auth-form" novalidate>
      ${bothEnabled ? '<label for="identifier-type">Recovery method</label><select id="identifier-type" name="identifier-type"><option value="email">Email</option><option value="phone">Phone number</option></select>' : ''}
      <label for="identifier">${identifierLabel(type)}</label>
      <input id="identifier" name="identifier" type="${type === 'email' ? 'email' : 'text'}" autocomplete="${type}" required />
      ${errorHtml()}
      ${button('Send code', state.busy)}
    </form>`;
  shell('Reset your password', 'We will send a verification code to your account.', content, '<button type="button" class="text-button" data-action="signin">Back to sign in</button>');
  root.querySelector<HTMLFormElement>('#forgot-form')?.addEventListener('submit', async (event) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget as HTMLFormElement);
    const selectedType = String(form.get('identifier-type') ?? type);
    const selectedIdentifierType = selectedType === 'phone' ? 'phone' : 'email';
    const value = String(form.get('identifier') ?? '').trim();
    if ((selectedIdentifierType === 'email' && !isEmail(value)) || (selectedIdentifierType === 'phone' && !isPhone(value))) {
      state.error = { code: 'guard.invalid_input', message: `Enter a valid ${identifierLabel(selectedIdentifierType).toLowerCase()}.`, field: 'identifier' };
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
    } catch (error) { setError(error); }
  });
  root.querySelector<HTMLSelectElement>('#identifier-type')?.addEventListener('change', (event) => {
    const selected = (event.currentTarget as HTMLSelectElement).value === 'phone' ? 'phone' : 'email';
    const input = root.querySelector<HTMLInputElement>('#identifier');
    const label = root.querySelector<HTMLLabelElement>('label[for="identifier"]');
    if (input) { input.type = selected === 'email' ? 'email' : 'text'; input.setAttribute('autocomplete', selected); }
    if (label) label.textContent = identifierLabel(selected);
  });
  attachActions();
  focusFirst();
};

const renderForgotVerify = () => {
  const content = `
    <form id="forgot-verify-form" class="auth-form" novalidate>
      <p class="step-note">We sent a verification code to <strong>${escapeHtml(state.identifier?.value)}</strong>.</p>
      <label for="code">Verification code</label>
      <input id="code" name="code" inputmode="numeric" autocomplete="one-time-code" required />
      <label for="password">New password</label>
      <div class="password-wrap"><input id="password" name="password" type="password" autocomplete="new-password" required /><button type="button" class="password-toggle" data-target="password">Show</button></div>
      <label for="confirm">Confirm new password</label>
      <input id="confirm" name="confirm" type="password" autocomplete="new-password" required />
      ${errorHtml()}
      ${button('Reset password', state.busy)}
    </form>`;
  shell('Choose a new password', 'Use a password you have not used elsewhere.', content, '<button type="button" class="text-button" data-action="signin">Back to sign in</button>');
  root.querySelector<HTMLFormElement>('#forgot-verify-form')?.addEventListener('submit', async (event) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget as HTMLFormElement);
    const code = String(form.get('code') ?? '').trim();
    const password = String(form.get('password') ?? '');
    const confirm = String(form.get('confirm') ?? '');
    if (!code || !password || password !== confirm || !state.identifier || !state.verificationId) {
      state.error = { code: 'guard.invalid_input', message: password !== confirm ? 'Passwords do not match.' : 'Enter the code and a new password.', field: 'form' };
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
    try { submitResult(await api.finishForgotPassword(state.identifier, state.verificationId, code, password)); } catch (error) { setError(error); }
  });
  attachActions();
  root.querySelectorAll<HTMLButtonElement>('.password-toggle').forEach((toggle) => toggle.addEventListener('click', () => {
    const input = root.querySelector<HTMLInputElement>(`#${toggle.dataset.target}`);
    if (input) { input.type = input.type === 'password' ? 'text' : 'password'; toggle.textContent = input.type === 'password' ? 'Show' : 'Hide'; }
  }));
  focusFirst();
};

const attachSocial = (connectors: SocialConnector[]) => {
  root.querySelectorAll<HTMLButtonElement>('[data-social]').forEach((buttonElement) => buttonElement.addEventListener('click', async () => {
    const connector = connectors.find((item) => item.id === buttonElement.dataset.social);
    if (!connector) return;
    state.busy = true;
    render();
    try { window.location.assign(await api.socialAuthorization(connector)); } catch (error) { setError(error); }
  }));
};

const attachActions = () => {
  root.querySelectorAll<HTMLElement>('[data-action]').forEach((element) => element.addEventListener('click', () => {
    const action = element.dataset.action;
    state.error = undefined;
    state.busy = false;
    if (action === 'register') state.view = 'register';
    if (action === 'signin') state.view = 'sign-in';
    if (action === 'forgot') state.view = 'forgot';
    setUrl(state.view);
    render();
  }));
};

const renderCallback = async () => {
  shell('Signing you in', 'Completing your secure sign-in with the provider.', '<div class="loading-panel"><span class="spinner"></span> Please wait…</div>');
  const match = window.location.pathname.match(/^\/callback\/social\/([^/]+)/);
  if (!match) {
    state.view = 'sign-in';
    setError({ code: 'session.invalid_callback', message: 'Invalid provider callback.' });
    return;
  }
  try {
    submitResult(await api.completeSocialCallback(
      decodeURIComponent(match[1]),
      new URLSearchParams(window.location.search),
      state.settings,
    ));
  } catch (error) {
    state.view = 'sign-in';
    setError(error);
  }
};

const render = () => {
  if (state.view === 'callback') { void renderCallback(); return; }
  if (state.view === 'register') return renderRegister();
  if (state.view === 'register-verify') return renderRegisterVerify();
  if (state.view === 'forgot') return renderForgot();
  if (state.view === 'forgot-verify') return renderForgotVerify();
  return renderSignIn();
};

const restoreInteractionView = () => {
  const event = state.interaction?.interactionEvent;
  const pending = state.interaction?.verificationRecords?.find((record) =>
    (record.type === 'EmailVerificationCode' || record.type === 'PhoneVerificationCode') && !record.verified
  );
  if (pending?.identifier && pending.id) {
    state.identifier = pending.identifier;
    state.verificationId = pending.id;
    if (event === 'Register') return 'register-verify' as const;
    if (event === 'ForgotPassword') return 'forgot-verify' as const;
  }
  if (event === 'Register') return 'register' as const;
  if (event === 'ForgotPassword') return 'forgot' as const;
  return 'sign-in' as const;
};

export const startExperience = async () => {
  shell('Loading Lingxi', 'Preparing your secure sign-in.', '<div class="loading-panel"><span class="spinner"></span> Loading…</div>');
  try {
    state.settings = await api.getSettings();
    if (window.location.pathname.startsWith('/callback/social/')) {
      state.view = 'callback';
      render();
      return;
    }
    try { state.interaction = await api.getInteraction(); } catch (error) {
      const normalized = normalizeExperienceError(error);
      if (normalized.status !== 404 && normalized.code !== 'session.interaction_not_found') throw error;
    }
    state.view = firstScreen() ?? restoreInteractionView();
    render();
  } catch (error) {
    setError(error);
  }
};
