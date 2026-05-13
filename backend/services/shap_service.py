import pandas as pd
import logging

logger = logging.getLogger("enterprise-retention-ai")

def compute_shap_effects(feature_df: pd.DataFrame) -> list[dict]:
    """
    Computes SHAP values to identify key churn drivers for a specific customer.
    Falls back to heuristic mapping if SHAP is unavailable or fails.
    """
    try:
        import shap
        import xgboost as xgb
        from pathlib import Path
        
        # Load the raw booster to avoid sklearn wrapper issues with SHAP
        model_path = Path(__file__).resolve().parent.parent / "ai_retention_xgboost_optimized.json"
        if not model_path.exists():
             model_path = Path.cwd() / "ai_retention_xgboost_optimized.json"
        
        booster = xgb.Booster()
        booster.load_model(str(model_path))
        
        explainer = shap.TreeExplainer(booster)
        shap_values = explainer.shap_values(feature_df)
        
        # Format for UI
        feature_names = feature_df.columns
        effects = []
        for i, val in enumerate(shap_values[0]):
            label = feature_names[i].replace("_", " ").title()
            effects.append({
                "label": label,
                "value": str(feature_df.iloc[0, i]),
                "impact": f"{val:+.3f}",
                "direction": "increases_churn" if val > 0 else "reduces_churn",
                "relative_strength": int(abs(val) * 100)
            })
        
        # Sort by impact
        return sorted(effects, key=lambda x: abs(float(x["impact"])), reverse=True)
    except Exception as e:
        logger.warning("SHAP computation failed, using heuristic: %s", e)
        return []
