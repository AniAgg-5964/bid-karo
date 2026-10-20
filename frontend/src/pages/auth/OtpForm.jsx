import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { ArrowLeft, KeyRound, MailCheck, RefreshCw } from "lucide-react";

import { useAuth } from "../../contexts/AuthContext";
import { Button } from "../../components/ui/Button";
import { FieldError, Input, Label } from "../../components/ui/Field";

export function OtpForm({
  email,
  purpose,
  initialMessage = "",
  resendAfter = 60,
  onVerified,
  onBack,
}) {
  const { t } = useTranslation();
  const { verifyOtp, resendOtp } = useAuth();
  const [code, setCode] = useState("");
  const [message, setMessage] = useState(initialMessage);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [resending, setResending] = useState(false);
  const [seconds, setSeconds] = useState(resendAfter);

  useEffect(() => {
    if (seconds <= 0) return undefined;
    const timer = window.setInterval(() => {
      setSeconds((current) => Math.max(current - 1, 0));
    }, 1000);
    return () => window.clearInterval(timer);
  }, [seconds]);

  const submit = async (event) => {
    event.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      const data = await verifyOtp({ email, purpose, code });
      onVerified(data);
    } catch (err) {
      setError(err.message === "NETWORK_ERROR" ? t("errors.network") : err.message || t("errors.generic"));
    } finally {
      setSubmitting(false);
    }
  };

  const resend = async () => {
    setError("");
    setResending(true);
    try {
      const data = await resendOtp({ email, purpose });
      setMessage(data.message);
      setSeconds(data.resend_after_seconds || 60);
    } catch (err) {
      setError(err.message === "NETWORK_ERROR" ? t("errors.network") : err.message || t("errors.generic"));
    } finally {
      setResending(false);
    }
  };

  return (
    <form onSubmit={submit} className="space-y-4" noValidate>
      <div className="flex items-start gap-3 rounded-xl border border-teal-100 bg-teal-50/70 p-3.5 dark:border-teal-900 dark:bg-teal-950/30">
        <MailCheck className="mt-0.5 h-5 w-5 shrink-0 text-teal-700 dark:text-teal-300" />
        <div>
          <p className="text-sm font-semibold text-navy-900 dark:text-white">
            {t("auth.otpSentTitle")}
          </p>
          <p className="mt-0.5 text-xs leading-5 muted">
            {message || t("auth.otpSentBody", { email })}
          </p>
          <p className="mt-1 text-xs font-medium text-navy-800 dark:text-navy-100">{email}</p>
        </div>
      </div>

      <div>
        <Label htmlFor="otp-code">{t("auth.otpCode")}</Label>
        <div className="relative">
          <KeyRound className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-navy-400" />
          <Input
            id="otp-code"
            inputMode="numeric"
            autoComplete="one-time-code"
            autoFocus
            required
            minLength={6}
            maxLength={6}
            pattern="[0-9]{6}"
            value={code}
            onChange={(event) => setCode(event.target.value.replace(/\D/g, "").slice(0, 6))}
            className="pl-9 text-center text-lg font-semibold tracking-[0.45em]"
            placeholder="000000"
          />
        </div>
        <p className="mt-1.5 text-xs muted">{t("auth.otpExpiry")}</p>
      </div>

      <FieldError>{error}</FieldError>

      <Button type="submit" className="w-full" size="lg" loading={submitting} disabled={code.length !== 6}>
        {submitting ? t("auth.verifying") : t("auth.verify")}
      </Button>

      <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
        <button
          type="button"
          onClick={onBack}
          className="inline-flex items-center gap-1.5 font-semibold text-navy-600 hover:text-navy-900 dark:text-navy-300 dark:hover:text-white"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          {purpose === "login" ? t("auth.backToSignIn") : t("auth.backToRegister")}
        </button>
        <button
          type="button"
          onClick={resend}
          disabled={seconds > 0 || resending}
          className="inline-flex items-center gap-1.5 font-semibold text-teal-700 hover:text-teal-900 disabled:cursor-not-allowed disabled:text-navy-400 dark:text-teal-300 dark:hover:text-teal-200"
        >
          <RefreshCw className={resending ? "h-3.5 w-3.5 animate-spin" : "h-3.5 w-3.5"} />
          {seconds > 0 ? t("auth.resendIn", { seconds }) : t("auth.resend")}
        </button>
      </div>
    </form>
  );
}
