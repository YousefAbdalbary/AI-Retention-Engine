from services.prompt_builder import PromptBuilder

messages = PromptBuilder.build_final_prompt(
    customer_id="TEST-123",
    customer_data={"name": "Alice", "industry": "Tech", "nps_score": 9.5},
    risk_pct=85.5,
    risk_level="CRITICAL",
    is_vip=True,
    revenue=12000.0,
    top_drivers_text="- Cancel Rate: 0.5\n- Support Tickets: 5"
)

print(messages[1]["content"][:500])
print("SUCCESS!")
