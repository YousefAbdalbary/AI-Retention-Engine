import json
from typing import Any, Dict


class PromptBuilder:
    """Production-grade Prompt Builder for Enterprise Customer Retention."""

    @staticmethod
    def build_system_prompt() -> str:
        return (
            "You are an elite Enterprise Customer Success Manager, Retention Specialist, CRM Strategist, "
            "and Sales Consultant. Your goal is to analyze customer data and produce highly personalized, "
            "actionable, and business-friendly retention strategies.\n\n"
            "OUTPUT QUALITY REQUIREMENTS:\n"
            "- AVOID generic recommendations and repetitive campaigns.\n"
            "- AVOID generic emails and obvious advice. THE EMAIL MUST BE HIGHLY PERSONALIZED.\n"
            "- PRODUCE customer-specific insights and personalized recommendations.\n"
            "- THE EMAIL STRATEGY MUST USE THE EXACT NUMBERS (like Feature Usage %, NPS, Loyalty Score) AND SPECIFIC PROFILE DETAILS.\n"
            "- PRODUCE realistic CRM actions and executive-friendly explanations.\n"
            "- DIFFERENTIATE: ensure different customers receive distinct, tailored recommendations and emails.\n"
            "- All outputs must be highly actionable for sales and success teams."
        )

    @staticmethod
    def build_customer_intelligence_profile(
        customer_id: str,
        customer_data: Dict[str, Any],
        risk_pct: float,
        risk_level: str,
        is_vip: bool,
        revenue: float,
        top_drivers_text: str,
    ) -> str:
        """Constructs a comprehensive customer context string."""
        # Extract optional fields or provide defaults
        name = customer_data.get("name") or "Unknown"
        company = customer_data.get("company") or "Unknown Company"
        plan = customer_data.get("contract") or "Standard Plan"
        industry = customer_data.get("industry") or "Unknown Industry"
        region = customer_data.get("region") or "Global"

        confidence = customer_data.get("ai_confidence_score", 85)
        nps = customer_data.get("nps_score") or "N/A"
        feature_usage = customer_data.get("feature_usage_pct") or "N/A"
        email_open = customer_data.get("email_open_rate") or "N/A"

        return f"""
CUSTOMER INTELLIGENCE PROFILE:

1. Customer Information:
   - Name: {name}
   - Company: {company}
   - Plan/Contract: {plan}
   - Region: {region}
   - Industry: {industry}

2. Prediction Information:
   - Churn Risk: {risk_pct:.1f}%
   - Risk Level: {risk_level}
   - AI Confidence: {confidence}%

3. Behavior Information:
   - NPS Score: {nps}
   - Feature Usage: {feature_usage}
   - Email Engagement: {email_open}

4. Business Information:
   - Customer Lifetime Value (Total Paid): ${customer_data.get('total_amount_paid', 0):,.2f}
   - Revenue at Risk: ${revenue:,.2f}
   - VIP Status: {'YES' if is_vip else 'NO'}

5. AI Information (SHAP Explanations):
   - Top Risk Drivers:
{top_drivers_text}
"""

    @staticmethod
    def build_chain_of_thought_prompt() -> str:
        return (
            "CHAIN OF THOUGHT ANALYSIS:\n"
            "Before generating the final JSON output, internally reason through the following steps. "
            "(Do not output your reasoning steps, just use them to construct the final JSON answers):\n"
            "1. Why is this specific customer at risk based on their behavior and AI drivers?\n"
            "2. What underlying business problem exists for them?\n"
            "3. What intervention is most effective for this exact profile?\n"
            "4. Which communication channel fits best given their engagement history?\n"
            "5. Which tone should be used for this segment?\n"
            "6. What specific offer or incentive should be proposed?\n"
            "7. What follow-up actions are needed by the sales or account team?\n\n"
            "SELF-EVALUATION:\n"
            "- Does the recommendation match their feature usage and behavior?\n"
            "- Does the channel match their email engagement?\n"
            "- Does the tone match their VIP/Segment status?\n"
            "- Does the action directly address the top churn drivers?\n"
        )

    @staticmethod
    def build_output_format_prompt() -> str:
        return (
            "MULTI-OUTPUT GENERATION:\n"
            "Based on your analysis, generate the following outputs. "
            "You MUST return ONLY a valid JSON object with the exact structure below. "
            "Do not include Markdown blocks (like ```json), just the raw JSON.\n\n"
            "{\n"
            '  "english": {\n'
            '    "customer_persona": "Brief description of the customer persona.",\n'
            '    "customer_segment": "The identified business segment.",\n'
            '    "retention_strategy": "The overarching strategy to save the account.",\n'
            '    "communication_strategy": "The recommended communication channel and tone.",\n'
            '    "email_strategy": "A highly personalized draft of an email to send to the customer. MUST use their specific name, reference their specific feature usage, NPS score, or recent behavior, and address their exact risk drivers. DO NOT output a generic template.",\n'
            '    "why_generated": "Business translation of why this action is necessary now.",\n'
            '    "personalization_factors": "List the data points (e.g. usage, nps) that shaped this email.",\n'
            '    "expected_outcome": "The projected business result if this strategy is executed.",\n'
            '    "recommended_actions": ["Action 1", "Action 2", "Action 3"],\n'
            '    "follow_up_plan": "Specific follow-up steps for the account manager.",\n'
            '    "executive_summary": "High-level summary of risk, value, and action plan."\n'
            "  },\n"
            '  "arabic": {\n'
            '    "customer_persona": "Arabic translation",\n'
            '    "customer_segment": "Arabic translation",\n'
            '    "retention_strategy": "Arabic translation",\n'
            '    "communication_strategy": "Arabic translation",\n'
            '    "email_strategy": "Arabic translation of the highly personalized email draft.",\n'
            '    "why_generated": "Arabic translation",\n'
            '    "personalization_factors": "Arabic translation",\n'
            '    "expected_outcome": "Arabic translation",\n'
            '    "recommended_actions": ["Arabic Action 1", "Arabic Action 2", "Arabic Action 3"],\n'
            '    "follow_up_plan": "Arabic translation",\n'
            '    "executive_summary": "Arabic translation"\n'
            "  }\n"
            "}\n"
            "Ensure the Arabic translation sounds natural, professional, and business-focused."
        )

    @staticmethod
    def build_final_prompt(
        customer_id: str,
        customer_data: Dict[str, Any],
        risk_pct: float,
        risk_level: str,
        is_vip: bool,
        revenue: float,
        top_drivers_text: str,
    ) -> list[Dict[str, str]]:
        system_msg = PromptBuilder.build_system_prompt()
        context = PromptBuilder.build_customer_intelligence_profile(
            customer_id,
            customer_data,
            risk_pct,
            risk_level,
            is_vip,
            revenue,
            top_drivers_text,
        )
        cot = PromptBuilder.build_chain_of_thought_prompt()
        fmt = PromptBuilder.build_output_format_prompt()

        user_msg = f"{context}\n\n{cot}\n\n{fmt}"

        return [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg},
        ]
