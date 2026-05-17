from __future__ import annotations

import json
import importlib.util
from pathlib import Path


def _load_run_recipe_module():
    script_path = Path("scripts/monthly_report_run_recipe.py")
    spec = importlib.util.spec_from_file_location(
        "monthly_report_run_recipe", script_path
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_recipe_scope_reminder_maps_to_workshop_prompt_scope_notes():
    recipe_path = Path(
        "docs/samples/monthly-reports/fixtures/report_recipes/"
        "hirayama_economics_pattern_b_shell.recipe.json"
    )
    recipe = json.loads(recipe_path.read_text(encoding="utf-8"))

    fields = _load_run_recipe_module().recipe_to_workshop_job_fields(recipe)

    assert fields["prompt_scope_notes"].startswith("本レポートの主題は **Economics SL**")
    assert "飯村様" in fields["prompt_scope_notes"]
    assert "scope_reminder" not in fields


def test_recipe_scope_reminder_blank_maps_to_none():
    fields = _load_run_recipe_module().recipe_to_workshop_job_fields(
        {
            "recipe_version": 1,
            "prompts": {"scope_reminder": "  \n  "},
        }
    )

    assert fields == {"prompt_scope_notes": None}
