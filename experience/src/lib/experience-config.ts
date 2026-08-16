export type SignInMethod = {
  identifier: string;
  password?: boolean;
  verificationCode?: boolean;
  isPasswordPrimary?: boolean;
};

export type SocialConnector = {
  id: string;
  name?: string;
  target?: string;
  logo?: string;
  logoDark?: string;
  [key: string]: unknown;
};

export type PasswordPolicy = {
  length?: { min?: number; max?: number };
  characterTypes?: { min?: number; required?: string[] };
  [key: string]: unknown;
};

export type ExperienceSettings = {
  color?: { primaryColor?: string; darkPrimaryColor?: string; isDarkModeEnabled?: boolean };
  branding?: { logoUrl?: string; darkLogoUrl?: string; favicon?: string; darkFavicon?: string };
  signIn?: { methods?: SignInMethod[] };
  signInMode?: 'SignIn' | 'Register' | 'SignInAndRegister' | string;
  signUp?: {
    identifiers?: string[];
    password?: boolean;
    verify?: boolean;
    secondaryIdentifiers?: Array<{ identifier: string; verify?: boolean }>;
  };
  socialSignIn?: {
    automaticAccountLinking?: boolean;
    skipRequiredIdentifiers?: boolean;
  };
  forgotPassword?: { email?: boolean; phone?: boolean };
  passwordPolicy?: PasswordPolicy;
  socialConnectors?: SocialConnector[];
  ssoConnectors?: Array<Record<string, unknown>>;
  customContent?: Record<string, string>;
  captchaConfig?: { type?: string; siteKey?: string };
  [key: string]: unknown;
};

export type InteractionEvent = 'SignIn' | 'Register' | 'ForgotPassword';

export type Identifier = { type: 'email' | 'phone' | 'username'; value: string };

export type VerificationRecord = {
  id: string;
  type: string;
  identifier?: Identifier;
  verified?: boolean;
};

export type Interaction = {
  interactionEvent?: InteractionEvent;
  userId?: string;
  profile?: Record<string, unknown>;
  verificationRecords?: VerificationRecord[];
  mfa?: Record<string, unknown>;
};

export const isEmail = (value: string) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);

export const isPhone = (value: string) => /^\+?[0-9 ()-]{7,}$/.test(value);

export const primarySignUpIdentifier = (settings: ExperienceSettings): 'email' | 'phone' | 'username' => {
  const configured = settings.signUp?.identifiers?.[0];
  return configured === 'phone' || configured === 'username' ? configured : 'email';
};

export const signInMethod = (settings: ExperienceSettings, identifier: string): SignInMethod | undefined =>
  settings.signIn?.methods?.find((method) => method.identifier === identifier);

export const hasForgotPassword = (settings: ExperienceSettings) =>
  Boolean(settings.forgotPassword?.email || settings.forgotPassword?.phone);

/**
 * Social sign-in may fall back to registration only when registration is
 * enabled by the sign-in mode and a primary sign-up identifier is configured.
 */
export const allowsRegistration = (settings: ExperienceSettings) =>
  settings.signInMode !== undefined
    ? settings.signInMode !== 'SignIn'
    : Boolean(settings.signUp?.identifiers?.length);

/** Fast, client-side checks only. Logto remains the source of truth for all password policy rules. */
export const passwordPolicyError = (policy: PasswordPolicy | undefined, password: string) => {
  if (!policy) return undefined;
  const min = policy.length?.min;
  const max = policy.length?.max;
  if (min && password.length < min) return `Password must be at least ${min} characters.`;
  if (max && password.length > max) return `Password must be at most ${max} characters.`;
  const requiredTypes = policy.characterTypes?.min ?? 1;
  const types = new Set<string>();
  for (const character of password) {
    if (/[a-z]/.test(character)) types.add('lowercase');
    else if (/[A-Z]/.test(character)) types.add('uppercase');
    else if (/[0-9]/.test(character)) types.add('digits');
    else if ('!"#$%&\'()*+,-./:;<=>?@[\\]^_`{|}~ '.includes(character)) types.add('symbols');
    else return 'Password contains an unsupported character.';
  }
  if (types.size < requiredTypes) return `Use at least ${requiredTypes} different character types.`;
  return undefined;
};
