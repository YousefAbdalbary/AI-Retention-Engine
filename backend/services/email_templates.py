"""
Enterprise AI Retention Engine — Dynamic HTML Email Templates.

Generates risk-level-specific, responsive HTML emails with:
- Branded header with gradient
- Personalized body copy
- CTA button
- Company footer

Customer-facing emails — NO internal model results (risk %, scores, etc.)
are ever exposed to the end user.

Three tiers:
  LOW   (0-39%)  — Appreciation / loyalty
  MEDIUM (40-69%) — Re-engagement / incentive
  HIGH  (70-100%) — Urgent VIP recovery
"""

from __future__ import annotations

from datetime import datetime, timezone


# ── colour palettes per risk tier ──────────────────────────────────────────
_PALETTES = {
    "LOW": {
        "gradient_start": "#00b894",
        "gradient_end": "#00cec9",
        "cta_bg": "#00b894",
        "accent": "#00b894",
        "emoji": "🌟",
    },
    "MEDIUM": {
        "gradient_start": "#f39c12",
        "gradient_end": "#e17055",
        "cta_bg": "#f39c12",
        "accent": "#f39c12",
        "emoji": "⚡",
    },
    "HIGH": {
        "gradient_start": "#e74c3c",
        "gradient_end": "#c0392b",
        "cta_bg": "#e74c3c",
        "accent": "#e74c3c",
        "emoji": "💎",
    },
}


def _base_layout(
    *,
    palette: dict,
    subject_line: str,
    hero_heading: str,
    hero_subtext: str,
    body_html: str,
    cta_text: str,
    cta_url: str,
    footer_note: str = "",
) -> str:
    """Return a complete responsive HTML email string.

    No model results, risk scores, or internal data are included.
    """
    year = datetime.now(timezone.utc).year

    return f"""\
<!DOCTYPE html>
<html lang="en" xmlns="http://www.w3.org/1999/xhtml">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <meta http-equiv="X-UA-Compatible" content="IE=edge" />
  <title>{subject_line}</title>
  <!--[if mso]>
  <noscript>
    <xml>
      <o:OfficeDocumentSettings>
        <o:PixelsPerInch>96</o:PixelsPerInch>
      </o:OfficeDocumentSettings>
    </xml>
  </noscript>
  <![endif]-->
  <style>
    /* Reset */
    body, table, td, a {{ -webkit-text-size-adjust: 100%; -ms-text-size-adjust: 100%; }}
    table, td {{ mso-table-lspace: 0pt; mso-table-rspace: 0pt; }}
    img {{ -ms-interpolation-mode: bicubic; border: 0; height: auto; line-height: 100%; outline: none; text-decoration: none; }}
    body {{ margin: 0; padding: 0; width: 100% !important; height: 100% !important; background-color: #f4f6f9; }}

    /* Container */
    .email-wrapper {{ width: 100%; background-color: #f4f6f9; padding: 32px 0; }}
    .email-container {{ max-width: 600px; margin: 0 auto; background: #ffffff; border-radius: 16px; overflow: hidden; box-shadow: 0 4px 24px rgba(0,0,0,0.08); }}

    /* Header */
    .email-header {{
      background: linear-gradient(135deg, {palette['gradient_start']}, {palette['gradient_end']});
      padding: 40px 32px;
      text-align: center;
    }}
    .email-header h1 {{ color: #ffffff; font-family: 'Segoe UI', Arial, sans-serif; font-size: 26px; margin: 0 0 8px 0; font-weight: 700; }}
    .email-header p {{ color: rgba(255,255,255,0.9); font-family: 'Segoe UI', Arial, sans-serif; font-size: 14px; margin: 0; }}

    /* Body */
    .email-body {{ padding: 32px; font-family: 'Segoe UI', Arial, sans-serif; color: #2d3436; line-height: 1.7; font-size: 15px; }}
    .email-body h2 {{ font-size: 20px; margin: 0 0 16px 0; color: #2d3436; }}
    .email-body p {{ margin: 0 0 14px 0; }}

    /* CTA Button */
    .cta-wrapper {{ text-align: center; padding: 8px 0 16px 0; }}
    .cta-button {{
      display: inline-block;
      background: {palette['cta_bg']};
      color: #ffffff !important;
      font-family: 'Segoe UI', Arial, sans-serif;
      font-size: 16px;
      font-weight: 600;
      text-decoration: none;
      padding: 14px 40px;
      border-radius: 8px;
      letter-spacing: 0.3px;
    }}

    /* Divider */
    .divider {{ border: none; border-top: 1px solid #e9ecef; margin: 24px 0; }}

    /* Footer */
    .email-footer {{
      background: #f8f9fa;
      padding: 24px 32px;
      text-align: center;
      font-family: 'Segoe UI', Arial, sans-serif;
      font-size: 12px;
      color: #b2bec3;
      border-top: 1px solid #e9ecef;
    }}
    .email-footer a {{ color: {palette['accent']}; text-decoration: none; }}
    .email-footer .brand {{ font-weight: 700; color: #636e72; font-size: 13px; }}

    /* Responsive */
    @media only screen and (max-width: 620px) {{
      .email-container {{ width: 100% !important; border-radius: 0 !important; }}
      .email-header {{ padding: 28px 20px !important; }}
      .email-body {{ padding: 24px 20px !important; }}
      .email-footer {{ padding: 20px !important; }}
    }}
  </style>
</head>
<body>
  <div class="email-wrapper">
    <table role="presentation" cellpadding="0" cellspacing="0" width="100%">
      <tr><td align="center">
        <div class="email-container">

          <!-- HEADER -->
          <div class="email-header">
            <h1>{palette['emoji']} {hero_heading}</h1>
            <p>{hero_subtext}</p>
          </div>

          <!-- BODY -->
          <div class="email-body">

            <!-- Main Content -->
            {body_html}

            <!-- CTA -->
            <div class="cta-wrapper">
              <a href="{cta_url}" class="cta-button" target="_blank">{cta_text}</a>
            </div>

            <hr class="divider" />
            <p style="font-size: 13px; color: #636e72; text-align: center;">
              {footer_note}
            </p>
          </div>

          <!-- FOOTER -->
          <div class="email-footer">
            <p class="brand">RetentionAI</p>
            <p>Smart Customer Engagement Platform</p>
            <p>&copy; {year} RetentionAI. All rights reserved.</p>
            <p style="margin-top:8px;">
              <a href="#">Privacy Policy</a> &nbsp;|&nbsp;
              <a href="#">Unsubscribe</a>
            </p>
          </div>

        </div>
      </td></tr>
    </table>
  </div>
</body>
</html>"""


# ── Public API ─────────────────────────────────────────────────────────────

def generate_email_template(
    customer_id: str,
    risk_pct: float,
    *,
    personalized_message: str = "",
) -> tuple[str, str]:
    """
    Return ``(subject, html_body)`` for a retention email.

    The risk_pct is used internally to pick the correct template tier
    but is NEVER shown to the customer.

    Parameters
    ----------
    customer_id : str
        Unique customer identifier.
    risk_pct : float
        Churn-risk percentage (0-100). Used for routing only.
    personalized_message : str, optional
        AI-generated or manually-crafted personal note inserted in body.
    """

    if risk_pct < 40:
        return _low_risk_email(customer_id, personalized_message)
    if risk_pct < 70:
        return _medium_risk_email(customer_id, personalized_message)
    return _high_risk_email(customer_id, personalized_message)


# ── Private builders ───────────────────────────────────────────────────────

def _low_risk_email(
    customer_id: str, personal_msg: str
) -> tuple[str, str]:
    palette = _PALETTES["LOW"]
    subject = f"Thank You for Being Amazing, {customer_id}!"

    body = f"""\
<h2>We Appreciate You!</h2>
<p>Dear Valued Customer <strong>{customer_id}</strong>,</p>
<p>
  We just wanted to take a moment to say <strong>thank you</strong> for being
  an active and loyal member of our community. Your continued engagement means
  the world to us, and we're thrilled to have you on board.
</p>
{'<p style="background:#e8f8f5;padding:14px 18px;border-radius:8px;color:#0c5460;"><em>"' + personal_msg + '"</em></p>' if personal_msg else ''}
<p>
  Here's what's coming next for you:
</p>
<ul style="padding-left: 20px; color: #2d3436;">
  <li>🎁 <strong>Exclusive early access</strong> to our upcoming premium features</li>
  <li>🏆 <strong>Loyalty rewards</strong> — you're earning points every day</li>
  <li>🚀 <strong>Priority support</strong> for our most valued members</li>
  <li>📊 <strong>Personalized insights</strong> tailored to your usage patterns</li>
</ul>
<p>
  Stay tuned — exciting things are on the horizon. We're constantly working to
  make your experience even better!
</p>"""

    html = _base_layout(
        palette=palette,
        subject_line=subject,
        hero_heading="You're a Star Customer!",
        hero_subtext="A quick note of appreciation from our team",
        body_html=body,
        cta_text="Explore Upcoming Features →",
        cta_url="https://app.retentionai.com/features",
        footer_note="You're receiving this because you're one of our most valued customers. Keep being awesome!",
    )
    return subject, html


def _medium_risk_email(
    customer_id: str, personal_msg: str
) -> tuple[str, str]:
    palette = _PALETTES["MEDIUM"]
    subject = f"{customer_id}, We've Got Something Special For You"

    body = f"""\
<h2>We've Noticed You've Been Away</h2>
<p>Dear <strong>{customer_id}</strong>,</p>
<p>
  We've noticed your activity has slowed down recently, and we wanted to reach
  out personally. Your experience matters to us, and we'd love to understand how
  we can serve you better.
</p>
{'<p style="background:#fff8e1;padding:14px 18px;border-radius:8px;color:#856404;"><em>"' + personal_msg + '"</em></p>' if personal_msg else ''}
<p>
  To show you how much we value your membership, we'd like to offer you an
  <strong>exclusive incentive</strong>:
</p>
<div style="background: linear-gradient(135deg, #fff8e1, #fff3cd); padding: 20px; border-radius: 12px; text-align: center; margin: 20px 0;">
  <p style="font-size: 28px; font-weight: 700; color: #e17055; margin: 0;">20% OFF</p>
  <p style="font-size: 14px; color: #856404; margin: 6px 0 0 0;">Your Next Renewal — Limited Time Offer</p>
</div>
<p>Here's what you'll get when you re-engage:</p>
<ul style="padding-left: 20px; color: #2d3436;">
  <li>💰 <strong>20% discount</strong> on your next billing cycle</li>
  <li>🎯 <strong>Personalized onboarding</strong> refresher session</li>
  <li>📞 <strong>Priority support access</strong> for 90 days</li>
  <li>📈 <strong>Custom usage report</strong> with actionable insights</li>
</ul>
<p>
  We believe in the value we provide, and we're confident that once you see what's
  new, you'll be glad you stayed. Don't miss out!
</p>"""

    html = _base_layout(
        palette=palette,
        subject_line=subject,
        hero_heading="We Miss You!",
        hero_subtext="Your exclusive offer is waiting inside",
        body_html=body,
        cta_text="Claim Your 20% Discount →",
        cta_url="https://app.retentionai.com/offer/claim",
        footer_note="This exclusive offer expires in 72 hours. Don't let it slip away!",
    )
    return subject, html


def _high_risk_email(
    customer_id: str, personal_msg: str
) -> tuple[str, str]:
    palette = _PALETTES["HIGH"]
    subject = f"{customer_id}, Your Exclusive VIP Offer Is Waiting"

    body = f"""\
<h2>An Exclusive Offer Just For You</h2>
<p>Dear <strong>{customer_id}</strong>,</p>
<p>
  We understand that things change, and we respect every decision you make. But
  before you make a final call, we wanted to share something
  <strong>exclusively reserved for valued members like you</strong>.
</p>
{'<p style="background:#fce4ec;padding:14px 18px;border-radius:8px;color:#721c24;"><em>"' + personal_msg + '"</em></p>' if personal_msg else ''}
<div style="background: linear-gradient(135deg, #ffeef0, #f8d7da); padding: 24px; border-radius: 12px; text-align: center; margin: 20px 0; border: 1px solid #f5c6cb;">
  <p style="font-size: 14px; color: #721c24; margin: 0 0 4px 0; text-transform: uppercase; letter-spacing: 1px;">VIP Recovery Package</p>
  <p style="font-size: 36px; font-weight: 700; color: #e74c3c; margin: 0;">40% OFF</p>
  <p style="font-size: 14px; color: #856404; margin: 6px 0 0 0;">+ Dedicated Success Manager + Premium Support</p>
</div>
<p>Your VIP Package includes:</p>
<ul style="padding-left: 20px; color: #2d3436;">
  <li>🔥 <strong>40% discount</strong> on your next 3 billing cycles</li>
  <li>👤 <strong>Dedicated Success Manager</strong> assigned to your account</li>
  <li>⚡ <strong>Premium Priority Support</strong> — response within 1 hour</li>
  <li>🎁 <strong>Complimentary feature upgrade</strong> for 6 months</li>
  <li>📊 <strong>Quarterly business review</strong> with our team</li>
</ul>
<p style="font-weight: 600; color: #e74c3c;">
  ⏰ This offer is only available for the next 48 hours and won't be repeated.
  Act now to secure your exclusive package.
</p>"""

    html = _base_layout(
        palette=palette,
        subject_line=subject,
        hero_heading="We Value You!",
        hero_subtext="An exclusive offer crafted just for you",
        body_html=body,
        cta_text="Claim VIP Package Now →",
        cta_url="https://app.retentionai.com/vip/recovery",
        footer_note="This is a one-time exclusive offer. Expires in 48 hours.",
    )
    return subject, html
