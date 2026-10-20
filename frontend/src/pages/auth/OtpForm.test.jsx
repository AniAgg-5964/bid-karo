import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { OtpForm } from "./OtpForm";

const verifyOtp = vi.fn();
const resendOtp = vi.fn();

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key, options) => (options?.seconds ? `${key}:${options.seconds}` : key),
  }),
}));

vi.mock("../../contexts/AuthContext", () => ({
  useAuth: () => ({ verifyOtp, resendOtp }),
}));

describe("OtpForm", () => {
  beforeEach(() => {
    verifyOtp.mockReset();
    resendOtp.mockReset();
  });

  it("only enables submit at six digits and verifies the code", async () => {
    const onVerified = vi.fn();
    verifyOtp.mockResolvedValue({ access_token: "token" });

    render(
      <OtpForm
        email="owner@example.com"
        purpose="register"
        resendAfter={60}
        onVerified={onVerified}
        onBack={() => {}}
      />,
    );

    const input = screen.getByLabelText("auth.otpCode");
    const submit = screen.getByRole("button", { name: "auth.verify" });
    expect(submit).toBeDisabled();

    fireEvent.change(input, { target: { value: "12ab34-56" } });
    expect(input).toHaveValue("123456");
    expect(submit).toBeEnabled();

    fireEvent.click(submit);

    await waitFor(() =>
      expect(verifyOtp).toHaveBeenCalledWith({
        email: "owner@example.com",
        purpose: "register",
        code: "123456",
      }),
    );
    expect(onVerified).toHaveBeenCalledWith({ access_token: "token" });
  });

  it("shows the server error and keeps the code editable", async () => {
    verifyOtp.mockRejectedValue(new Error("That code is not valid."));

    render(
      <OtpForm
        email="owner@example.com"
        purpose="login"
        resendAfter={60}
        onVerified={() => {}}
        onBack={() => {}}
      />,
    );

    fireEvent.change(screen.getByLabelText("auth.otpCode"), {
      target: { value: "000000" },
    });
    fireEvent.click(screen.getByRole("button", { name: "auth.verify" }));

    expect(await screen.findByText("That code is not valid.")).toBeInTheDocument();
    expect(screen.getByLabelText("auth.otpCode")).toHaveValue("000000");
  });

  it("resends and restarts the cooldown", async () => {
    resendOtp.mockResolvedValue({
      message: "A new code was sent.",
      resend_after_seconds: 60,
    });

    render(
      <OtpForm
        email="owner@example.com"
        purpose="login"
        initialMessage="A code was sent."
        resendAfter={0}
        onVerified={() => {}}
        onBack={() => {}}
      />,
    );

    const resend = screen.getByRole("button", { name: /auth.resend$/ });
    fireEvent.click(resend);

    await waitFor(() =>
      expect(resendOtp).toHaveBeenCalledWith({
        email: "owner@example.com",
        purpose: "login",
      }),
    );
    expect(await screen.findByText("A new code was sent.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /auth.resendIn:60/ })).toBeDisabled();
  });
});
