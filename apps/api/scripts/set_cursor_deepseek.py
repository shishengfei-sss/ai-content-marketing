"""Enable Cursor DeepSeek BYOK and add DeepSeek models."""
from __future__ import annotations

import json
import sqlite3
import sys
from copy import deepcopy
from pathlib import Path

STATE_DB = Path(r"C:\Users\admin\AppData\Roaming\Cursor\User\globalStorage\state.vscdb")
APP_USER_KEY = (
    "src.vs.platform.reactivestorage.browser.reactiveStorageServiceImpl"
    ".persistentStorage.applicationUser"
)

DEEPSEEK_MODELS = [
    {
        "name": "deepseek-v4-flash",
        "display": "DeepSeek V4 Flash",
        "markdown": "**DeepSeek V4 Flash**<br />Fast and cheap for daily coding",
    },
    {
        "name": "deepseek-v4-pro",
        "display": "DeepSeek V4 Pro",
        "markdown": "**DeepSeek V4 Pro**<br />Stronger reasoning for Agent tasks",
    },
]


def make_model_entry(spec: dict) -> dict:
    name = spec["name"]
    display = spec["display"]
    return {
        "name": name,
        "defaultOn": True,
        "parameterDefinitions": [],
        "variants": [
            {
                "parameterValues": [],
                "displayName": display,
                "isMaxMode": False,
                "isDefaultMaxConfig": True,
                "isDefaultNonMaxConfig": True,
                "tooltipData": {
                    "primaryText": "",
                    "secondaryText": "",
                    "secondaryWarningText": False,
                    "icon": "",
                    "tertiaryText": "",
                    "tertiaryTextUrl": "",
                    "markdownContent": spec["markdown"],
                },
                "displayNameOutsidePicker": display,
                "variantStringRepresentation": f"{name}[]",
                "legacySlug": name,
            }
        ],
        "legacySlugs": [],
        "idAliases": [],
        "cloudAgentEffortModes": [],
        "modelPickerBadges": [],
        "supportsAgent": True,
        "degradationStatus": 0,
        "tooltipData": {
            "primaryText": "",
            "secondaryText": "",
            "secondaryWarningText": False,
            "icon": "",
            "tertiaryText": "",
            "tertiaryTextUrl": "",
            "markdownContent": spec["markdown"],
        },
        "supportsThinking": True,
        "supportsImages": False,
        "supportsMaxMode": False,
        "clientDisplayName": display,
        "serverModelName": name,
        "supportsNonMaxMode": True,
        "tooltipDataForMaxMode": {
            "primaryText": "",
            "secondaryText": "",
            "secondaryWarningText": False,
            "icon": "",
            "tertiaryText": "",
            "tertiaryTextUrl": "",
            "markdownContent": spec["markdown"],
        },
        "isRecommendedForBackgroundComposer": False,
        "supportsPlanMode": True,
        "inputboxShortModelName": display,
        "supportsSandboxing": True,
    }


def upsert_models(models: list, specs: list[dict]) -> None:
    by_name = {m.get("name"): m for m in models}
    for spec in specs:
        entry = make_model_entry(spec)
        by_name[spec["name"]] = entry
    models[:] = list(by_name.values())


def main() -> int:
    conn = sqlite3.connect(STATE_DB)
    try:
        row = conn.execute(
            "SELECT value FROM ItemTable WHERE key=?", (APP_USER_KEY,)
        ).fetchone()
        data = json.loads(row[0])

        data["useOpenAIKey"] = True
        data["openAIBaseUrl"] = "https://api.deepseek.com"

        models = data.setdefault("availableDefaultModels2", [])
        upsert_models(models, DEEPSEEK_MODELS)

        ai_settings = data.setdefault("aiSettings", {})
        enabled = ai_settings.setdefault("modelOverrideEnabled", [])
        for spec in DEEPSEEK_MODELS:
            if spec["name"] not in enabled:
                enabled.append(spec["name"])

        model_config = ai_settings.setdefault("modelConfig", {})
        for surface in ("composer", "cmd-k", "plan-execution", "quick-agent"):
            cfg = model_config.setdefault(surface, {})
            cfg["modelName"] = "deepseek-v4-pro"
            cfg["maxMode"] = False
            cfg["selectedModels"] = [
                {"modelId": "deepseek-v4-pro", "parameters": []}
            ]

        feature_models = data.setdefault("featureModelConfigs", {})
        for surface in ("composer", "cmdK", "planExecution", "quickAgent"):
            cfg = feature_models.setdefault(surface, {})
            cfg["defaultModel"] = "deepseek-v4-pro"
            cfg["fallbackModels"] = ["deepseek-v4-flash", "kimi-k2.7-code"]

        subagents = feature_models.setdefault("subagentModels", {})
        explore = subagents.setdefault("explore", {})
        explore["defaultModel"] = "deepseek-v4-flash"

        conn.execute(
            "UPDATE ItemTable SET value=? WHERE key=?",
            (json.dumps(data, ensure_ascii=False), APP_USER_KEY),
        )
        conn.commit()
    finally:
        conn.close()

    print("Cursor DeepSeek BYOK enabled.")
    print("- useOpenAIKey: true")
    print("- base URL: https://api.deepseek.com")
    print("- models: deepseek-v4-flash, deepseek-v4-pro")
    print("- default: deepseek-v4-pro (composer/chat)")
    print("Please reload Cursor window (Ctrl+Shift+P -> Developer: Reload Window).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
