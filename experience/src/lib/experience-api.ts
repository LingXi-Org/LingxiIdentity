import type { UIError } from './errors';
import { normalizeExperienceError } from './errors';
import type { ExperienceSettings, Identifier, Interaction, InteractionEvent, SocialConnector } from './experience-config';

export type SubmitResponse = { redirectTo?: string };
export type VerificationResponse = { verificationId: string };
export type SocialAuthorizationResponse = VerificationResponse & { authorizationUri: string };

export class ExperienceApiError extends Error {
  readonly code: string;
  readonly status: number;
  readonly details: unknown;

  constructor(message: string, options: { code: string; status: number; details?: unknown }) {
    super(message);
    this.name = 'ExperienceApiError';
    this.code = options.code;
    this.status = options.status;
    this.details = options.details;
  }
}

const jsonOrUndefined = async (response: Response): Promise<unknown> => {
  if (response.status === 204) return undefined;
  const text = await response.text();
  if (!text) return undefined;
  try {
    return JSON.parse(text) as unknown;
  } catch {
    return { message: text };
  }
};

const errorPayload = (payload: unknown): { code?: string; message?: string; details?: unknown } => {
  if (!payload || typeof payload !== 'object') return {};
  const body = payload as Record<string, unknown>;
  const nested = body.body && typeof body.body === 'object' ? (body.body as Record<string, unknown>) : body;
  return {
    code: typeof nested.code === 'string' ? nested.code : undefined,
    message: typeof nested.message === 'string' ? nested.message : undefined,
    details: nested.details,
  };
};

export class ExperienceApi {
  private async request<T>(path: string, init: RequestInit = {}): Promise<T> {
    const headers = new Headers(init.headers);
    headers.set('Accept', 'application/json');
    if (init.body && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json');
    let response: Response;
    try {
      response = await fetch(path, { ...init, headers, credentials: 'include' });
    } catch (error) {
      throw new ExperienceApiError('Network request failed', { code: 'experience.network_error', status: 0, details: error });
    }
    const payload = await jsonOrUndefined(response);
    if (!response.ok) {
      const parsed = errorPayload(payload);
      throw new ExperienceApiError(parsed.message ?? response.statusText, {
        code: parsed.code ?? `http.${response.status}`,
        status: response.status,
        details: parsed.details ?? payload,
      });
    }
    return payload as T;
  }

  async getSettings() {
    try {
      return await this.request<ExperienceSettings>('/api/.well-known/experience');
    } catch (error) {
      // Logto 1.33.0 serves the same payload from the legacy sign-in-exp alias
      // on installations upgraded from an older baseline.
      if (error instanceof ExperienceApiError && error.status === 404) {
        return this.request<ExperienceSettings>('/api/.well-known/sign-in-exp');
      }
      throw error;
    }
  }

  getInteraction() {
    return this.request<Interaction>('/api/experience/interaction');
  }

  initInteraction(interactionEvent: InteractionEvent, captchaToken?: string) {
    return this.request<void>('/api/experience', {
      method: 'PUT',
      body: JSON.stringify({ interactionEvent, ...(captchaToken ? { captchaToken } : {}) }),
    });
  }

  setInteractionEvent(interactionEvent: InteractionEvent) {
    return this.request<void>('/api/experience/interaction-event', {
      method: 'PUT',
      body: JSON.stringify({ interactionEvent }),
    });
  }

  sendVerificationCode(interactionEvent: InteractionEvent, identifier: Identifier) {
    return this.request<VerificationResponse>('/api/experience/verification/verification-code', {
      method: 'POST',
      body: JSON.stringify({ interactionEvent, identifier }),
    });
  }

  verifyVerificationCode(identifier: Identifier, verificationId: string, code: string) {
    return this.request<VerificationResponse>('/api/experience/verification/verification-code/verify', {
      method: 'POST',
      body: JSON.stringify({ identifier, verificationId, code }),
    });
  }

  verifyPassword(identifier: Identifier, password: string) {
    return this.request<VerificationResponse>('/api/experience/verification/password', {
      method: 'POST',
      body: JSON.stringify({ identifier, password }),
    });
  }

  identify(verificationId?: string) {
    return this.request<void>('/api/experience/identification', {
      method: 'POST',
      body: JSON.stringify(verificationId ? { verificationId } : {}),
    });
  }

  updateProfile(payload: Record<string, unknown>) {
    return this.request<void>('/api/experience/profile', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }

  resetPassword(password: string) {
    return this.request<void>('/api/experience/profile/password', {
      method: 'PUT',
      body: JSON.stringify({ password }),
    });
  }

  submit() {
    return this.request<SubmitResponse>('/api/experience/submit', { method: 'POST' });
  }

  async signIn(identifier: Identifier, password: string) {
    await this.initInteraction('SignIn');
    const verification = await this.verifyPassword(identifier, password);
    await this.identify(verification.verificationId);
    return this.submit();
  }

  async beginRegistration(identifier: Identifier, verify: boolean) {
    await this.initInteraction('Register');
    if (identifier.type === 'username') {
      await this.updateProfile(identifier);
      return undefined;
    }
    if (verify) return this.sendVerificationCode('Register', identifier);
    // Logto v1.33 requires verified email/phone identifiers. Keep the API boundary explicit;
    // the server decides whether a verification record is required.
    return this.sendVerificationCode('Register', identifier);
  }

  async finishRegistration(identifier: Identifier, verificationId: string, code: string | undefined, password?: string) {
    let verifiedId = verificationId;
    if (code) {
      const verified = await this.verifyVerificationCode(identifier, verificationId, code);
      verifiedId = verified.verificationId;
    }
    await this.updateProfile({ type: identifier.type, verificationId: verifiedId });
    if (password) await this.updateProfile({ type: 'password', value: password });
    await this.identify();
    return this.submit();
  }

  async beginForgotPassword(identifier: Identifier) {
    await this.initInteraction('ForgotPassword');
    return this.sendVerificationCode('ForgotPassword', identifier);
  }

  async finishForgotPassword(identifier: Identifier, verificationId: string, code: string, password: string) {
    const verified = await this.verifyVerificationCode(identifier, verificationId, code);
    await this.identify(verified.verificationId);
    await this.resetPassword(password);
    return this.submit();
  }

  async socialAuthorization(connector: SocialConnector) {
    await this.initInteraction('SignIn');
    const state = crypto.randomUUID();
    const redirectUri = `${window.location.origin}/callback/social/${encodeURIComponent(connector.id)}`;
    const result = await this.request<SocialAuthorizationResponse>(
      `/api/experience/verification/social/${encodeURIComponent(connector.id)}/authorization-uri`,
      { method: 'POST', body: JSON.stringify({ state, redirectUri }) }
    );
    sessionStorage.setItem('lingxi_experience_social', JSON.stringify({
      connectorId: connector.id,
      verificationId: result.verificationId,
      state,
    }));
    return result.authorizationUri;
  }

  async completeSocialCallback(connectorId: string, params: URLSearchParams) {
    const raw = sessionStorage.getItem('lingxi_experience_social');
    if (!raw) throw new ExperienceApiError('Social sign-in session not found', { code: 'session.expired', status: 400 });
    const saved = JSON.parse(raw) as { connectorId: string; verificationId: string; state: string };
    if (saved.connectorId !== connectorId || saved.state !== params.get('state')) {
      throw new ExperienceApiError('Social sign-in state mismatch', { code: 'session.state_mismatch', status: 400 });
    }
    const connectorData: Record<string, string> = {};
    params.forEach((value, key) => { if (key !== 'state') connectorData[key] = value; });
    const verification = await this.request<VerificationResponse>(
      `/api/experience/verification/social/${encodeURIComponent(connectorId)}/verify`,
      { method: 'POST', body: JSON.stringify({ connectorData, verificationId: saved.verificationId }) }
    );
    await this.identify(verification.verificationId);
    sessionStorage.removeItem('lingxi_experience_social');
    return this.submit();
  }
}

export const api = new ExperienceApi();

export const toUIError = (error: unknown): UIError => normalizeExperienceError(error);
