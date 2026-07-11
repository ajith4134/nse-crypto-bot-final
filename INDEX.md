# INDEX.md — AUTO-GENERATED. Do not edit by hand.

Regenerate with `make index` (parses the source via AST).

## `.cache/huggingface/hub/models--Maple728--TimeMoE-50M/.no_exist/446753ee48ff3726d0606a81d0092d54acee995e/custom_generate/generate.py`
_(no summary)_

## `.cache/huggingface/hub/models--Maple728--TimeMoE-50M/snapshots/446753ee48ff3726d0606a81d0092d54acee995e/configuration_time_moe.py`
_(no summary)_
- **classes:** TimeMoeConfig
- **imports:** transformers, typing

## `.cache/huggingface/hub/models--Maple728--TimeMoE-50M/snapshots/446753ee48ff3726d0606a81d0092d54acee995e/modeling_time_moe.py`
_(no summary)_
- **classes:** TimeMoeInputEmbedding, TimeMoeRotaryEmbedding, TimeMoeRMSNorm, TimeMoeTemporalBlock, TimeMoeMLP, TimeMoeSparseExpertsLayer, TimeMoeAttention, TimeMoeFlashAttention2, TimeMoeDecoderLayer, TimeMoePreTrainedModel, TimeMoeModel, TimeMoeOutputLayer, TimeMoeForPrediction
- **functions:** `_get_unpad_data(attention_mask)`; `load_balancing_loss_func(gate_logits, top_k, num_experts, attention_mask) -> torch.Tensor`; `repeat_kv(hidden_states, n_rep) -> torch.Tensor`; `rotate_half(x)`; `apply_rotary_pos_emb(q, k, cos, sin, position_ids, unsqueeze_dim)`
- **imports:** configuration_time_moe, math, torch, torch.nn.functional, transformers, transformers.activations, transformers.modeling_attn_mask_utils, transformers.modeling_outputs, transformers.utils, ts_generation_mixin, typing, warnings

## `.cache/huggingface/hub/models--Maple728--TimeMoE-50M/snapshots/446753ee48ff3726d0606a81d0092d54acee995e/ts_generation_mixin.py`
_(no summary)_
- **classes:** TSGenerationMixin
- **imports:** torch, transformers, transformers.generation, transformers.generation.utils, transformers.utils, typing, warnings

## `.cache/huggingface/hub/models--amazon--chronos-t5-tiny/.no_exist/29d808298f1a62493e7b9a5e08529d0d930fa189/custom_generate/generate.py`
_(no summary)_

## `.cache/huggingface/hub/models--vikhyatk--moondream2/.no_exist/6b714b26eea5cbd9f31e4edb2541c170afa935ba/custom_generate/generate.py`
_(no summary)_

## `.cache/huggingface/hub/models--vikhyatk--moondream2/snapshots/6b714b26eea5cbd9f31e4edb2541c170afa935ba/config.py`
_(no summary)_
- **classes:** TextConfig, VisionConfig, RegionConfig, TokenizerConfig, MoondreamConfig
- **imports:** dataclasses, typing

## `.cache/huggingface/hub/models--vikhyatk--moondream2/snapshots/6b714b26eea5cbd9f31e4edb2541c170afa935ba/hf_moondream.py`
_(no summary)_
- **classes:** HfConfig, HfMoondream
- **functions:** `extract_question(text)`
- **imports:** config, image_crops, moondream, region, text, torch, torch.nn, transformers, typing, utils, vision

## `.cache/huggingface/hub/models--vikhyatk--moondream2/snapshots/6b714b26eea5cbd9f31e4edb2541c170afa935ba/image_crops.py`
_(no summary)_
- **classes:** OverlapCropOutput
- **functions:** `select_tiling(height, width, crop_size, max_crops) -> tuple[int, int]`; `overlap_crop_image(image, overlap_margin, max_crops, base_size, patch_size) -> OverlapCropOutput`; `reconstruct_from_crops(crops, tiling, overlap_margin, patch_size) -> torch.Tensor`
- **imports:** math, numpy, torch, typing

## `.cache/huggingface/hub/models--vikhyatk--moondream2/snapshots/6b714b26eea5cbd9f31e4edb2541c170afa935ba/layers.py`
_(no summary)_
- **classes:** LinearWeights, QuantizedLinear, LayerNormWeights, MLPWeights, AttentionWeights
- **functions:** `gelu_approx(x)`; `linear(x, w) -> torch.Tensor`; `dequantize_tensor(W_q, scale, zero, orig_shape, dtype)`; `layer_norm(x, w) -> torch.Tensor`; `mlp(x, w, lora) -> torch.Tensor`; `attn(x, w, n_heads) -> torch.Tensor`
- **imports:** dataclasses, torch, torch.nn, torch.nn.functional, typing

## `.cache/huggingface/hub/models--vikhyatk--moondream2/snapshots/6b714b26eea5cbd9f31e4edb2541c170afa935ba/lora.py`
_(no summary)_
- **functions:** `variant_cache_dir()`; `cached_variant_path(variant_id)`; `nest(flat)`; `variant_state_dict(variant_id, device)`
- **imports:** functools, os, pathlib, shutil, torch, typing, urllib.request

## `.cache/huggingface/hub/models--vikhyatk--moondream2/snapshots/6b714b26eea5cbd9f31e4edb2541c170afa935ba/moondream.py`
_(no summary)_
- **classes:** EncodedImage, KVCache, MoondreamModel
- **functions:** `_is_cjk_char(cp)`
- **imports:** PIL, config, dataclasses, image_crops, layers, lora, random, region, text, tokenizers, torch, torch.nn, typing, utils, vision

## `.cache/huggingface/hub/models--vikhyatk--moondream2/snapshots/6b714b26eea5cbd9f31e4edb2541c170afa935ba/region.py`
_(no summary)_
- **functions:** `fourier_features(x, w) -> torch.Tensor`; `encode_coordinate(coord, w) -> torch.Tensor`; `decode_coordinate(hidden_state, w) -> torch.Tensor`; `encode_size(size, w) -> torch.Tensor`; `decode_size(hidden_state, w) -> torch.Tensor`; `encode_spatial_refs(spatial_refs, w) -> torch.Tensor`
- **imports:** layers, math, torch, torch.nn, typing

## `.cache/huggingface/hub/models--vikhyatk--moondream2/snapshots/6b714b26eea5cbd9f31e4edb2541c170afa935ba/rope.py`
_(no summary)_
- **functions:** `precompute_freqs_cis(dim, end, theta, use_scaled, dtype) -> torch.Tensor`; `apply_rotary_emb(x, freqs_cis, position_ids, num_heads, rot_dim, interleave) -> torch.Tensor`
- **imports:** torch

## `.cache/huggingface/hub/models--vikhyatk--moondream2/snapshots/6b714b26eea5cbd9f31e4edb2541c170afa935ba/text.py`
_(no summary)_
- **functions:** `text_encoder(input_ids, w)`; `attn(x, w, freqs_cis, kv_cache, attn_mask, n_heads, n_kv_heads, position_ids, lora)`; `_attn(x, w, freqs_cis, attn_mask, n_heads, n_kv_heads)`; `_produce_hidden(inputs_embeds, w, config)`; `text_decoder(x, w, attn_mask, position_ids, config, lora)`; `lm_head(hidden_BTC, w)`; `_lm_head(hidden_BTC, w)`; `build_text_model(config, dtype) -> nn.Module`
- **imports:** config, layers, rope, torch, torch.nn, typing

## `.cache/huggingface/hub/models--vikhyatk--moondream2/snapshots/6b714b26eea5cbd9f31e4edb2541c170afa935ba/utils.py`
_(no summary)_
- **functions:** `remove_outlier_points(points_tuples, k_nearest, threshold)`
- **imports:** numpy

## `.cache/huggingface/hub/models--vikhyatk--moondream2/snapshots/6b714b26eea5cbd9f31e4edb2541c170afa935ba/vision.py`
_(no summary)_
- **functions:** `prepare_crops(image, config, device) -> Tuple[torch.Tensor, Tuple[int, int]]`; `create_patches(x, patch_size)`; `vision_encoder(input_BCHW, w, config)`; `vision_projection(global_features, reconstructed, w, config)`; `build_vision_model(config, dtype)`
- **imports:** PIL, config, image_crops, layers, numpy, torch, torch.nn, torch.nn.functional, typing

## `.cache/huggingface/modules/__init__.py`
_(no summary)_

## `.cache/huggingface/modules/transformers_modules/Maple728/TimeMoE_hyphen_50M/446753ee48ff3726d0606a81d0092d54acee995e/__init__.py`
_(no summary)_

## `.cache/huggingface/modules/transformers_modules/Maple728/TimeMoE_hyphen_50M/446753ee48ff3726d0606a81d0092d54acee995e/configuration_time_moe.py`
_(no summary)_
- **classes:** TimeMoeConfig
- **imports:** transformers, typing

## `.cache/huggingface/modules/transformers_modules/Maple728/TimeMoE_hyphen_50M/446753ee48ff3726d0606a81d0092d54acee995e/modeling_time_moe.py`
_(no summary)_
- **classes:** TimeMoeInputEmbedding, TimeMoeRotaryEmbedding, TimeMoeRMSNorm, TimeMoeTemporalBlock, TimeMoeMLP, TimeMoeSparseExpertsLayer, TimeMoeAttention, TimeMoeFlashAttention2, TimeMoeDecoderLayer, TimeMoePreTrainedModel, TimeMoeModel, TimeMoeOutputLayer, TimeMoeForPrediction
- **functions:** `_get_unpad_data(attention_mask)`; `load_balancing_loss_func(gate_logits, top_k, num_experts, attention_mask) -> torch.Tensor`; `repeat_kv(hidden_states, n_rep) -> torch.Tensor`; `rotate_half(x)`; `apply_rotary_pos_emb(q, k, cos, sin, position_ids, unsqueeze_dim)`
- **imports:** configuration_time_moe, math, torch, torch.nn.functional, transformers, transformers.activations, transformers.modeling_attn_mask_utils, transformers.modeling_outputs, transformers.utils, ts_generation_mixin, typing, warnings

## `.cache/huggingface/modules/transformers_modules/Maple728/TimeMoE_hyphen_50M/446753ee48ff3726d0606a81d0092d54acee995e/ts_generation_mixin.py`
_(no summary)_
- **classes:** TSGenerationMixin
- **imports:** torch, transformers, transformers.generation, transformers.generation.utils, transformers.utils, typing, warnings

## `.cache/huggingface/modules/transformers_modules/Maple728/TimeMoE_hyphen_50M/__init__.py`
_(no summary)_

## `.cache/huggingface/modules/transformers_modules/Maple728/__init__.py`
_(no summary)_

## `.cache/huggingface/modules/transformers_modules/__init__.py`
_(no summary)_

## `.cache/huggingface/modules/transformers_modules/vikhyatk/__init__.py`
_(no summary)_

## `.cache/huggingface/modules/transformers_modules/vikhyatk/moondream2/6b714b26eea5cbd9f31e4edb2541c170afa935ba/__init__.py`
_(no summary)_

## `.cache/huggingface/modules/transformers_modules/vikhyatk/moondream2/6b714b26eea5cbd9f31e4edb2541c170afa935ba/config.py`
_(no summary)_
- **classes:** TextConfig, VisionConfig, RegionConfig, TokenizerConfig, MoondreamConfig
- **imports:** dataclasses, typing

## `.cache/huggingface/modules/transformers_modules/vikhyatk/moondream2/6b714b26eea5cbd9f31e4edb2541c170afa935ba/hf_moondream.py`
_(no summary)_
- **classes:** HfConfig, HfMoondream
- **functions:** `extract_question(text)`
- **imports:** config, image_crops, moondream, region, text, torch, torch.nn, transformers, typing, utils, vision

## `.cache/huggingface/modules/transformers_modules/vikhyatk/moondream2/6b714b26eea5cbd9f31e4edb2541c170afa935ba/image_crops.py`
_(no summary)_
- **classes:** OverlapCropOutput
- **functions:** `select_tiling(height, width, crop_size, max_crops) -> tuple[int, int]`; `overlap_crop_image(image, overlap_margin, max_crops, base_size, patch_size) -> OverlapCropOutput`; `reconstruct_from_crops(crops, tiling, overlap_margin, patch_size) -> torch.Tensor`
- **imports:** math, numpy, torch, typing

## `.cache/huggingface/modules/transformers_modules/vikhyatk/moondream2/6b714b26eea5cbd9f31e4edb2541c170afa935ba/layers.py`
_(no summary)_
- **classes:** LinearWeights, QuantizedLinear, LayerNormWeights, MLPWeights, AttentionWeights
- **functions:** `gelu_approx(x)`; `linear(x, w) -> torch.Tensor`; `dequantize_tensor(W_q, scale, zero, orig_shape, dtype)`; `layer_norm(x, w) -> torch.Tensor`; `mlp(x, w, lora) -> torch.Tensor`; `attn(x, w, n_heads) -> torch.Tensor`
- **imports:** dataclasses, torch, torch.nn, torch.nn.functional, typing

## `.cache/huggingface/modules/transformers_modules/vikhyatk/moondream2/6b714b26eea5cbd9f31e4edb2541c170afa935ba/lora.py`
_(no summary)_
- **functions:** `variant_cache_dir()`; `cached_variant_path(variant_id)`; `nest(flat)`; `variant_state_dict(variant_id, device)`
- **imports:** functools, os, pathlib, shutil, torch, typing, urllib.request

## `.cache/huggingface/modules/transformers_modules/vikhyatk/moondream2/6b714b26eea5cbd9f31e4edb2541c170afa935ba/moondream.py`
_(no summary)_
- **classes:** EncodedImage, KVCache, MoondreamModel
- **functions:** `_is_cjk_char(cp)`
- **imports:** PIL, config, dataclasses, image_crops, layers, lora, random, region, text, tokenizers, torch, torch.nn, typing, utils, vision

## `.cache/huggingface/modules/transformers_modules/vikhyatk/moondream2/6b714b26eea5cbd9f31e4edb2541c170afa935ba/region.py`
_(no summary)_
- **functions:** `fourier_features(x, w) -> torch.Tensor`; `encode_coordinate(coord, w) -> torch.Tensor`; `decode_coordinate(hidden_state, w) -> torch.Tensor`; `encode_size(size, w) -> torch.Tensor`; `decode_size(hidden_state, w) -> torch.Tensor`; `encode_spatial_refs(spatial_refs, w) -> torch.Tensor`
- **imports:** layers, math, torch, torch.nn, typing

## `.cache/huggingface/modules/transformers_modules/vikhyatk/moondream2/6b714b26eea5cbd9f31e4edb2541c170afa935ba/rope.py`
_(no summary)_
- **functions:** `precompute_freqs_cis(dim, end, theta, use_scaled, dtype) -> torch.Tensor`; `apply_rotary_emb(x, freqs_cis, position_ids, num_heads, rot_dim, interleave) -> torch.Tensor`
- **imports:** torch

## `.cache/huggingface/modules/transformers_modules/vikhyatk/moondream2/6b714b26eea5cbd9f31e4edb2541c170afa935ba/text.py`
_(no summary)_
- **functions:** `text_encoder(input_ids, w)`; `attn(x, w, freqs_cis, kv_cache, attn_mask, n_heads, n_kv_heads, position_ids, lora)`; `_attn(x, w, freqs_cis, attn_mask, n_heads, n_kv_heads)`; `_produce_hidden(inputs_embeds, w, config)`; `text_decoder(x, w, attn_mask, position_ids, config, lora)`; `lm_head(hidden_BTC, w)`; `_lm_head(hidden_BTC, w)`; `build_text_model(config, dtype) -> nn.Module`
- **imports:** config, layers, rope, torch, torch.nn, typing

## `.cache/huggingface/modules/transformers_modules/vikhyatk/moondream2/6b714b26eea5cbd9f31e4edb2541c170afa935ba/utils.py`
_(no summary)_
- **functions:** `remove_outlier_points(points_tuples, k_nearest, threshold)`
- **imports:** numpy

## `.cache/huggingface/modules/transformers_modules/vikhyatk/moondream2/6b714b26eea5cbd9f31e4edb2541c170afa935ba/vision.py`
_(no summary)_
- **functions:** `prepare_crops(image, config, device) -> Tuple[torch.Tensor, Tuple[int, int]]`; `create_patches(x, patch_size)`; `vision_encoder(input_BCHW, w, config)`; `vision_projection(global_features, reconstructed, w, config)`; `build_vision_model(config, dtype)`
- **imports:** PIL, config, image_crops, layers, numpy, torch, torch.nn, torch.nn.functional, typing

## `.cache/huggingface/modules/transformers_modules/vikhyatk/moondream2/__init__.py`
_(no summary)_

## `.claude/hooks/hook_skill_learnings.py`
_PostToolUse hook on the Skill tool — the "read learnings first" half of the self-improving loop._
- **functions:** `main() -> int`
- **imports:** json, pathlib, sys

## `.claude/plugins/marketplaces/claude-plugins-official/plugins/hookify/core/__init__.py`
_(no summary)_

## `.claude/plugins/marketplaces/claude-plugins-official/plugins/hookify/core/config_loader.py`
_Configuration loader for hookify plugin._
- **classes:** Condition, Rule
- **functions:** `extract_frontmatter(content) -> tuple[Dict[str, Any], str]`; `load_rules(event) -> List[Rule]`; `load_rule_file(file_path) -> Optional[Rule]`
- **imports:** dataclasses, glob, os, re, sys, typing

## `.claude/plugins/marketplaces/claude-plugins-official/plugins/hookify/core/rule_engine.py`
_Rule evaluation engine for hookify plugin._
- **classes:** RuleEngine
- **functions:** `compile_regex(pattern) -> re.Pattern`
- **imports:** core.config_loader, functools, re, sys, typing

## `.claude/plugins/marketplaces/claude-plugins-official/plugins/hookify/hooks/__init__.py`
_(no summary)_

## `.claude/plugins/marketplaces/claude-plugins-official/plugins/hookify/hooks/posttooluse.py`
_PostToolUse hook executor for hookify plugin._
- **functions:** `main()`
- **imports:** json, os, sys

## `.claude/plugins/marketplaces/claude-plugins-official/plugins/hookify/hooks/pretooluse.py`
_PreToolUse hook executor for hookify plugin._
- **functions:** `main()`
- **imports:** json, os, sys

## `.claude/plugins/marketplaces/claude-plugins-official/plugins/hookify/hooks/stop.py`
_Stop hook executor for hookify plugin._
- **functions:** `main()`
- **imports:** json, os, sys

## `.claude/plugins/marketplaces/claude-plugins-official/plugins/hookify/hooks/userpromptsubmit.py`
_UserPromptSubmit hook executor for hookify plugin._
- **functions:** `main()`
- **imports:** json, os, sys

## `.claude/plugins/marketplaces/claude-plugins-official/plugins/hookify/matchers/__init__.py`
_(no summary)_

## `.claude/plugins/marketplaces/claude-plugins-official/plugins/hookify/utils/__init__.py`
_(no summary)_

## `.claude/plugins/marketplaces/claude-plugins-official/plugins/security-guidance/hooks/_base.py`
_Shared low-level helpers for the security-guidance hook modules._
- **functions:** `state_dir()`; `debug_log(message)`; `_read_plugin_version_int()`; `_record_usage(usage, model, cost_usd)`; `_record_http_error(status)`; `_usage_metrics()`
- **imports:** datetime, json, os, threading

## `.claude/plugins/marketplaces/claude-plugins-official/plugins/security-guidance/hooks/diffstate.py`
_Git-derived diff/review-state helpers for the security-guidance plugin._
- **functions:** `save_baseline_sha(session_id, sha)`; `load_baseline_sha(session_id)`; `record_touched_path(session_id, file_path)`; `consume_stop_state(session_id)`; `restore_unreviewed_stop_state(session_id, paths, baseline_sha)`; `get_baseline_file_content(session_id, file_path, cwd)`; `capture_git_baseline(cwd)`; `_reviewed_shas_path(repo_root)`; `_load_reviewed_shas(repo_root)`; `_append_reviewed_shas(repo_root, shas, vulns_found)`; `_list_untracked(cwd)`; `compute_v2_review_set(cwd, baseline_sha, head_at_capture, untracked_at_baseline)`
- **imports:** _base, gitutil, os, session_state, subprocess

## `.claude/plugins/marketplaces/claude-plugins-official/plugins/security-guidance/hooks/ensure_agent_sdk.py`
_SessionStart bootstrap: ensure claude_agent_sdk is importable for the_
- **functions:** `_encode_phase(s)`; `_encode_err_kind(s)`; `_encode_rc(err_kind)`; `_is_signal_kill(returncode) -> bool`; `_cooldown_remaining(state_dir) -> float`; `_write_cooldown(state_dir) -> None`; `_encode_stderr_sig(err_kind)`; `_encode_exc_kind(err_kind)`; `_encode_errno(err_kind)`; `_probe_has_pip() -> bool`; `_pip_err_from_stderr(stderr_b)`; `_target_dir(state_dir) -> Path`; `_target_sdk_importable(state_dir) -> bool`; `_build_via_target(state_dir) -> tuple[int, str, str]`; `_sdk_on_syspath() -> bool`; `_plugin_version_int() -> int`; `main() -> tuple[int, str, str]`; `_maybe_emit_user_notice(outcome, pv) -> str | None`
- **imports:** __future__, _base, importlib.util, json, os, pathlib, subprocess, sys, time

## `.claude/plugins/marketplaces/claude-plugins-official/plugins/security-guidance/hooks/extensibility.py`
_Project-specific extensibility for the security-guidance plugin._
- **functions:** `load_for_session(cwd) -> None`; `guidance_block() -> str`; `user_patterns() -> List[Dict[str, Any]]`; `_config_paths(cwd, basename) -> List[Tuple[str, str]]`; `_load_guidance(cwd) -> str`; `_wrap_guidance(guidance) -> str`; `_load_user_patterns(cwd) -> List[Dict[str, Any]]`; `_read_config(path) -> Optional[Dict[str, Any]]`; `_validate_pattern(entry, source) -> Optional[Dict[str, Any]]`; `_glob_match(path, include, exclude) -> bool`; `_has_redos_structure(regex) -> bool`
- **imports:** _base, fnmatch, json, os, re, typing

## `.claude/plugins/marketplaces/claude-plugins-official/plugins/security-guidance/hooks/gitutil.py`
_Leaf git/subprocess helpers and diff parsing for the security-guidance plugin._
- **functions:** `_git_rev_parse_head(cwd)`; `_find_git_index(cwd)`; `_diff_pathspec(cwd, paths)`; `_temp_index(cwd, untracked_paths)`; `_git_toplevel(cwd)`; `_git_dir(repo_root)`; `_git_rev_list_range(repo_root, base, head)`; `_git_diff_range(repo_root, base, head)`; `_detect_main_branch(repo_root)`; `_git_reflog_recent_commits(repo_root, max_age_s, max_n)`; `_git_name_only(cwd, base, include_untracked)`; `_git_status_porcelain(cwd)`; `_is_ancestor(cwd, maybe_ancestor, descendant)`; `get_git_diff(cwd, baseline_sha, full_context, paths, untracked_paths)`; `_prioritize_diff_files(diff_files, cap)`; `_is_reviewable_source(file_path)`; `extract_file_paths_from_diff(diff_output)`; `parse_diff_into_files(diff_output)`; `filter_preexisting_from_diff(diff_files, cwd, baseline_sha)`
- **imports:** _base, contextlib, os, re, subprocess

## `.claude/plugins/marketplaces/claude-plugins-official/plugins/security-guidance/hooks/llm.py`
_LLM-based security analysis for the security-guidance plugin._
- **functions:** `_inject_agent_sdk_venv_into_syspath(state_dir)`; `_bootstrap_pywin32(site_packages_dir)`; `_anthropic_base_url() -> str`; `_probe_anthropic(timeout) -> bool`; `_strip_anthropic_from_no_proxy() -> None`; `ensure_anthropic_reachable() -> bool`; `_cap_files_for_prompt(files)`; `_build_auth_headers(use_token)`; `_model_supports_adaptive_thinking(model) -> bool`; `_is_3p_provider() -> bool`; `_call_claude_via_sdk(prompt, output_schema)`; `_call_claude(prompt, output_schema, thinking_budget, max_tokens, model, retry_5xx)`; `_dual_or_enabled() -> bool`; `_call_claude_dual_or(prompt, output_schema)`; `_format_vulns_guidance(vulns) -> Optional[str]`; `_format_vulns_summary(vulns, prefix) -> Optional[str]`; `_finding_keys(findings) -> set`; `_dedup_against_state(session_id, vulns, prompted) -> Tuple[List[Dict[str, Any]], int]`; `analyze_code_security(files, is_diff, previous_findings) -> Tuple[Optional[str], List[Dict[str, Any]]]`; `_agentic_commit_review_enabled() -> bool`; `_agentic_spawn_env() -> Dict[str, str]`; `agentic_review(repo_dir, diff_files, touched_paths) -> Tuple[Optional[str], List[Dict[str, Any]], Dict[str, Any]]`; `analyze_security_concerns(files, is_diff) -> Optional[str]`
- **imports:** _base, extensibility, glob, json, os, re, review_api, session_state, sys, typing, urllib.request

## `.claude/plugins/marketplaces/claude-plugins-official/plugins/security-guidance/hooks/patterns.py`
_Regex-based security pattern definitions for the security-guidance plugin._
- **classes:** RuleId
- **functions:** `rule_names_to_mask(rule_names)`
- **imports:** enum

## `.claude/plugins/marketplaces/claude-plugins-official/plugins/security-guidance/hooks/review_api.py`
_Public review API for the security-guidance agentic commit reviewer._
- **functions:** `cap_diff_for_prompt(files) -> tuple[list[tuple[str, str]], int]`; `build_investigate_prompt(touched_paths, diff_files) -> str`; `build_refute_prompt(candidates, diff_text) -> str`; `tag_diff_anchor(candidates, diff_text) -> list[dict[str, Any]]`; `filter_by_severity(findings) -> list[dict[str, Any]]`; `format_findings(findings) -> str`
- **imports:** __future__, extensibility, json, os, typing

## `.claude/plugins/marketplaces/claude-plugins-official/plugins/security-guidance/hooks/security_reminder_hook.py`
_Security Guidance Plugin for Claude Code_
- **functions:** `emit_metrics(metrics, rewake_summary, additional_context, system_message, hook_event_name)`; `atomic_check_and_mark_warning(session_id, warning_key)`; `atomic_check_counter(session_id, counter_key, max_count)`; `atomic_check_rate_limit(session_id, key, max_per_window, window_s)`; `record_pending_warnings(session_id, file_path, rule_names)`; `sweep_pending_warnings(session_id)`; `check_patterns(file_path, content)`; `extract_content_from_input(tool_name, tool_input)`; `handle_user_prompt_submit(input_data)`; `_resolve_amend_pre_sha(repo_root, expected_post_sha)`; `_claim_bash_hook_once(input_data)`; `is_push_sweep_enabled()`; `_compute_push_sweep_base(prev_upstream, push_range, reviewed)`; `_push_section(bash_output)`; `_detect_prev_upstream(repo_root, bash_output)`; `is_commit_review_enabled()`; `_agentic_review_with_race(repo_root, diff_files, rel_touched, previous_findings) -> Tuple[Optional[str], List[Dict[str, Any]], Dict[str, Any]]`; `handle_commit_review_posttooluse(input_data)`; `handle_push_sweep_posttooluse(input_data)`; `handle_stop_hook(input_data)`; `_maybe_bootstrap_agent_sdk_async()`; `main()`
- **imports:** _base, contextlib, datetime, diffstate, enum, extensibility, gitutil, glob, json, llm, os, patterns, random, re, review_api, session_state, subprocess, sys, threading, typing, urllib.request

## `.claude/plugins/marketplaces/claude-plugins-official/plugins/security-guidance/hooks/session_state.py`
_Per-session state-file plumbing for the security-guidance plugin._
- **functions:** `_state_key(session_id)`; `get_state_file(session_id)`; `get_lock_file(session_id)`; `cleanup_old_state_files()`; `load_state(session_id)`; `save_state(session_id, state)`; `with_locked_state(session_id, callback)`
- **imports:** _base, datetime, json, os, re

## `.claude/plugins/marketplaces/claude-plugins-official/plugins/skill-creator/skills/skill-creator/eval-viewer/generate_review.py`
_Generate and serve a review page for eval results._
- **classes:** ReviewHandler
- **functions:** `get_mime_type(path) -> str`; `find_runs(workspace) -> list[dict]`; `_find_runs_recursive(root, current, runs) -> None`; `build_run(root, run_dir) -> dict | None`; `embed_file(path) -> dict`; `load_previous_iteration(workspace) -> dict[str, dict]`; `generate_html(runs, skill_name, previous, benchmark) -> str`; `_kill_port(port) -> None`; `main() -> None`
- **imports:** argparse, base64, functools, http.server, json, mimetypes, os, pathlib, re, signal, subprocess, sys, time, webbrowser

## `.claude/plugins/marketplaces/claude-plugins-official/plugins/skill-creator/skills/skill-creator/scripts/__init__.py`
_(no summary)_

## `.claude/plugins/marketplaces/claude-plugins-official/plugins/skill-creator/skills/skill-creator/scripts/aggregate_benchmark.py`
_Aggregate individual run results into benchmark summary statistics._
- **functions:** `calculate_stats(values) -> dict`; `load_run_results(benchmark_dir) -> dict`; `aggregate_results(results) -> dict`; `generate_benchmark(benchmark_dir, skill_name, skill_path) -> dict`; `generate_markdown(benchmark) -> str`; `main()`
- **imports:** argparse, datetime, json, math, pathlib, sys

## `.claude/plugins/marketplaces/claude-plugins-official/plugins/skill-creator/skills/skill-creator/scripts/generate_report.py`
_Generate an HTML report from run_loop.py output._
- **functions:** `generate_html(data, auto_refresh, skill_name) -> str`; `main()`
- **imports:** argparse, html, json, pathlib, sys

## `.claude/plugins/marketplaces/claude-plugins-official/plugins/skill-creator/skills/skill-creator/scripts/improve_description.py`
_Improve a skill description based on eval results._
- **functions:** `_call_claude(prompt, model, timeout) -> str`; `improve_description(skill_name, skill_content, current_description, eval_results, history, model, test_results, log_dir, iteration) -> str`; `main()`
- **imports:** argparse, json, os, pathlib, re, scripts.utils, subprocess, sys

## `.claude/plugins/marketplaces/claude-plugins-official/plugins/skill-creator/skills/skill-creator/scripts/package_skill.py`
_Skill Packager - Creates a distributable .skill file of a skill folder_
- **functions:** `should_exclude(rel_path) -> bool`; `package_skill(skill_path, output_dir)`; `main()`
- **imports:** fnmatch, pathlib, scripts.quick_validate, sys, zipfile

## `.claude/plugins/marketplaces/claude-plugins-official/plugins/skill-creator/skills/skill-creator/scripts/quick_validate.py`
_Quick validation script for skills - minimal version_
- **functions:** `validate_skill(skill_path)`
- **imports:** os, pathlib, re, sys, yaml

## `.claude/plugins/marketplaces/claude-plugins-official/plugins/skill-creator/skills/skill-creator/scripts/run_eval.py`
_Run trigger evaluation for a skill description._
- **functions:** `find_project_root() -> Path`; `run_single_query(query, skill_name, skill_description, timeout, project_root, model) -> bool`; `run_eval(eval_set, skill_name, description, num_workers, timeout, project_root, runs_per_query, trigger_threshold, model) -> dict`; `main()`
- **imports:** argparse, concurrent.futures, json, os, pathlib, scripts.utils, select, subprocess, sys, time, uuid

## `.claude/plugins/marketplaces/claude-plugins-official/plugins/skill-creator/skills/skill-creator/scripts/run_loop.py`
_Run the eval + improve loop until all pass or max iterations reached._
- **functions:** `split_eval_set(eval_set, holdout, seed) -> tuple[list[dict], list[dict]]`; `run_loop(eval_set, skill_path, description_override, num_workers, timeout, max_iterations, runs_per_query, trigger_threshold, holdout, model, verbose, live_report_path, log_dir) -> dict`; `main()`
- **imports:** argparse, json, pathlib, random, scripts.generate_report, scripts.improve_description, scripts.run_eval, scripts.utils, sys, tempfile, time, webbrowser

## `.claude/plugins/marketplaces/claude-plugins-official/plugins/skill-creator/skills/skill-creator/scripts/utils.py`
_Shared utilities for skill-creator scripts._
- **functions:** `parse_skill_md(skill_path) -> tuple[str, str, str]`
- **imports:** pathlib

## `.claude/skills/ai-scientist/state_snapshot.py`
_ai-scientist state snapshot — grounds ideation in REAL project state._
- **functions:** `root_of(start) -> Path`; `read_head(p, n) -> str`; `git(root) -> str`; `deps(root)`; `module_inventory(root)`; `latest_audit(root)`; `idea_ledger(root)`; `vendored(root)`; `main()`
- **imports:** __future__, argparse, collections, json, os, pathlib, re, subprocess, time

## `.claude/skills/cpu-solo/cpu_solo.py`
_cpu-solo — free all cores for the current test/build/feature by PAUSING (SIGSTOP) the project's_
- **functions:** `_procs()`; `_self_tree(rows)`; `pause(include_all, min_cpu)`; `resume()`; `status()`; `main()`
- **imports:** __future__, argparse, os, pathlib, re, signal, subprocess

## `.claude/skills/dashboard-visual-qa/data_consistency_qa.py`
_data_consistency_qa — verify the dashboard tells the TRUTH about the data on disk (both ways)._
- **functions:** `_api(path)`; `_disk(fname)`; `_len(x)`; `run()`
- **imports:** json, os, pathlib, subprocess, time

## `.claude/skills/dashboard-visual-qa/hook_dashboard_edit.py`
_PostToolUse hook: when an Edit/Write/MultiEdit touches dashboard / FreqUI / OpenAlgo_
- **functions:** `is_dashboard_view(path) -> bool`; `main()`
- **imports:** json, os, sys, time

## `.claude/skills/dashboard-visual-qa/interaction_qa.py`
_interaction_qa — end-to-end INPUT + BUTTON tester for every dashboard view._
- **functions:** `_drive(page, ctrl)`; `_await_app(page, settle)`; `_enumerate(page, tries)`; `run(only)`; `_write_md(report, path)`
- **imports:** argparse, json, os, pathlib, playwright.sync_api, re, time

## `.claude/skills/dashboard-visual-qa/visual_qa.py`
_dashboard-visual-qa — screenshot + before/after diff + load-perf + "landed" check_
- **functions:** `views()`; `reachable(url) -> bool`; `capture(label, only)`; `_pixel_diff(base, cur)`; `compare()`; `promote()`; `lighthouse(url)`; `main()`
- **imports:** __future__, argparse, json, os, pathlib, shutil, socket, subprocess, sys, time, urllib.parse

## `.claude/skills/founder-intent/capture_journey.py`
_founder-intent — gather the REAL build history + the owner's captured intent into one bundle._
- **functions:** `sh()`; `read(p, n)`; `git_journey()`; `goal_pillars()`; `memories()`; `research_docs()`; `main()`
- **imports:** __future__, glob, json, os, pathlib, re, subprocess, time

## `.claude/skills/hot-path/hotpath.py`
_hot-path — find Python hot paths worth compiling, and report the tooling to do it._
- **classes:** _Hot
- **functions:** `cmd_tools()`; `_score(node)`; `cmd_scan(dirs, top)`; `main()`
- **imports:** __future__, argparse, ast, os, pathlib, shutil

## `.claude/skills/independent-audit/audit.py`
_independent-audit — real code+architecture connectivity auditor (REPORT-ONLY)._
- **functions:** `find_repo_root(start) -> Path`; `is_entrypoint(mod) -> bool`; `is_test(mod) -> bool`; `discover_python(root)`; `build_graph_grimp(pkgs)`; `_resolve(target, known, first_party_top)`; `build_graph_ast(root, modules)`; `is_pkg(mod, modules) -> bool`; `analyse_graph(nodes, edges, max_list)`; `_norm_path(p) -> str`; `audit_dashboard(root)`; `audit_dead_code(root, source_dirs, max_list)`; `audit_index_drift(root, modules, max_list)`; `write_report(root, data) -> Path`; `main()`
- **imports:** __future__, argparse, ast, collections, json, os, pathlib, re, subprocess, sys, time

## `.claude/skills/money-lens/money_lens.py`
_money-lens — judge any step through the PRIME DIRECTIVE:_
- **functions:** `detect_mode()`; `main()`
- **imports:** __future__, argparse, glob, json, os, pathlib

## `.claude/skills/video-understand/ingest.py`
_Video ingest for the video-understand skill._
- **functions:** `run(cmd) -> subprocess.CompletedProcess`; `slugify(s) -> str`; `download(url, scratch) -> Path`; `duration_of(video) -> float`; `mmss(t) -> str`; `extract_frames(video, out, scene_th, cap, dur) -> list[dict]`; `transcribe(video, out_dir, model_size) -> dict`; `main() -> None`
- **imports:** __future__, argparse, json, pathlib, re, subprocess, sys

## `.cortex_build_job.py`
_run_network.py — CORTEX B7: unified network-state generator → network_state.json._
- **functions:** `_split(X, y, frac, seed)`; `_split_chrono(X, y, frac)`; `_pair_block(path, n_rows, tf_min, horizon_bars) -> dict | None`; `_real_dataset_multi(rows_per_pair, max_pairs, tf_min, horizon_bars) -> dict`; `_real_dataset(n_rows, tf_min, horizon_bars) -> dict`; `_deep_lane_factories() -> list[tuple]`; `_trust_ledger()`; `main() -> dict`
- **imports:** __future__, argparse, collections, core.columns, core.segments, data.benchmarks, eval.golden, json, nodes.active_subnet, nodes.reflex, numpy, os, random, run_columns, time

## `.julia/packages/CondaPkg/lKlVY/test/data/example-python-package/src/example_python_package/__init__.py`
_(no summary)_
- **functions:** `hello(who)`

## `.julia/packages/ForwardDiff/4J2wz/benchmarks/py/algopy_benchmarks.py`
_(no summary)_
- **functions:** `gradient(f)`; `hessian(f)`; `ackley(x)`; `rosenbrock(x)`; `self_weighted_logit(x)`; `bench(f, x, repeat)`
- **imports:** algopy, numpy, timeit

## `.julia/packages/ForwardDiff/4J2wz/benchmarks/py/autograd_benchmarks.py`
_(no summary)_
- **functions:** `ackley(x)`; `rosenbrock(x)`; `self_weighted_logit(x)`; `bench(f, x, r, n)`
- **imports:** autograd, autograd.numpy, timeit

## `.julia/packages/PythonCall/avYrV/pysrc/juliacall/__init__.py`
_(no summary)_
- **classes:** JuliaError
- **functions:** `newmodule(name)`; `convert(T, x)`; `interactive(enable)`; `init()`; `load_ipython_extension(ip)`

## `.julia/packages/PythonCall/avYrV/pysrc/juliacall/importer.py`
_Experimental module for loading Julia files as Python modules._
- **classes:** Finder
- **functions:** `install()`; `uninstall(finder)`; `gen_code(jl)`; `gen_file(jl, py)`; `exec_module(name, code)`
- **imports:** importlib.machinery, io, os, sys

## `.julia/packages/PythonCall/avYrV/pysrc/juliacall/ipython.py`
_Experimental IPython extension for Julia._
- **classes:** JuliaMagics
- **functions:** `load_ipython_extension(ip)`
- **imports:** IPython.core.magic, __main__

## `.julia/packages/PythonCall/avYrV/pysrc/juliacall/matplotlib.py`
_Minimal matplotlib backend which shows plots using Julia's display mechanism._
- **classes:** FigureManager
- **functions:** `show(format)`
- **imports:** juliacall, matplotlib.backend_bases, matplotlib.backends.backend_agg

## `.julia/packages/PythonCall/avYrV/pytest/test_all.py`
_(no summary)_
- **functions:** `test_import()`; `test_newmodule()`; `test_convert()`; `test_interactive()`; `test_JuliaError()`; `test_issue_394()`; `test_issue_433()`; `test_julia_gc()`; `test_call_nogil(yld, raw)`
- **imports:** pytest

## `.julia/packages/PythonCall/avYrV/src/C/find_libpython.py`
_Locate libpython associated with this Python executable._
- **classes:** Dl_info
- **functions:** `linked_libpython()`; `_linked_libpython_unix()`; `_linked_libpython_windows()`; `library_name(name, suffix, is_windows)`; `append_truthy(list, item)`; `uniquifying(items)`; `uniquified(func)`; `candidate_names(suffix)`; `candidate_paths(suffix)`; `normalize_path(path, suffix, is_apple)`; `_remove_suffix_apple(path)`; `finding_libpython()`; `find_libpython()`; `print_all(items)`; `cli_find_libpython(cli_op, verbose)`; `main(args)`
- **imports:** __future__, ctypes.util, functools, logging, os, sys, sysconfig

## `.julia/packages/SymbolicRegression/L5TJa/benchmark/analyze.py`
_(no summary)_
- **classes:** Node
- **functions:** `collect_children(parent, start_line_idx)`; `go_to_level(node, levels)`
- **imports:** numpy, pandas

## `.julia/packages/SymbolicRegression/L5TJa/benchmark/family_tree.py`
_(no summary)_
- **functions:** `load_pysr_graph(json_path, progress)`; `simplify_graph(G)`
- **imports:** json, networkx, tqdm

## `.julia/packages/SymbolicRegression/L5TJa/src/scripts/apply_deprecates.py`
_(no summary)_
- **imports:** glob, re

## `.local/lib/python3.13/site-packages/pypdf/__init__.py`
_pypdf is a free and open-source pure-python PDF library capable of splitting,_
- **imports:** _crypt_providers, _doc_common, _encryption, _page, _reader, _text_extraction, _version, _writer, constants, pagerange, papersizes

## `.local/lib/python3.13/site-packages/pypdf/_cmap.py`
_(no summary)_
- **functions:** `get_encoding(ft) -> tuple[Union[str, dict[int, str]], dict[Any, Any]]`; `_parse_encoding(ft) -> Union[str, dict[int, str]]`; `_parse_to_unicode(ft) -> tuple[dict[Any, Any], list[int]]`; `prepare_cm(ft) -> bytes`; `process_cm_line(line, process_rg, process_char, multiline_rg, map_dict, int_entry) -> tuple[bool, bool, Union[None, tuple[int, int]]]`; `_check_mapping_size(size) -> None`; `parse_bfrange(line, map_dict, int_entry, multiline_rg) -> Union[None, tuple[int, int]]`; `parse_bfchar(line, map_dict, int_entry) -> None`; `_type1_alternative(ft, map_dict, int_entry) -> tuple[dict[Any, Any], list[int]]`
- **imports:** _codecs, _utils, binascii, errors, generic, math, typing

## `.local/lib/python3.13/site-packages/pypdf/_codecs/__init__.py`
_(no summary)_
- **functions:** `fill_from_encoding(enc) -> list[str]`; `rev_encoding(enc) -> dict[str, int]`
- **imports:** adobe_glyphs, pdfdoc, std, symbol, zapfding

## `.local/lib/python3.13/site-packages/pypdf/_codecs/_codecs.py`
_This module is for codecs only._
- **classes:** Codec, LzwCodec
- **imports:** abc, io, pypdf._utils, pypdf.errors

## `.local/lib/python3.13/site-packages/pypdf/_codecs/adobe_glyphs.py`
_(no summary)_
- **functions:** `_complete() -> None`

## `.local/lib/python3.13/site-packages/pypdf/_codecs/core_font_metrics.py`
_(no summary)_
- **imports:** pypdf._font

## `.local/lib/python3.13/site-packages/pypdf/_codecs/pdfdoc.py`
_(no summary)_

## `.local/lib/python3.13/site-packages/pypdf/_codecs/std.py`
_(no summary)_

## `.local/lib/python3.13/site-packages/pypdf/_codecs/symbol.py`
_(no summary)_

## `.local/lib/python3.13/site-packages/pypdf/_codecs/zapfding.py`
_(no summary)_

## `.local/lib/python3.13/site-packages/pypdf/_crypt_providers/__init__.py`
_(no summary)_
- **imports:** pypdf._crypt_providers._base

## `.local/lib/python3.13/site-packages/pypdf/_crypt_providers/_base.py`
_(no summary)_
- **classes:** CryptBase, CryptIdentity

## `.local/lib/python3.13/site-packages/pypdf/_crypt_providers/_cryptography.py`
_(no summary)_
- **classes:** CryptRC4, CryptAES
- **functions:** `rc4_encrypt(key, data) -> bytes`; `rc4_decrypt(key, data) -> bytes`; `aes_ecb_encrypt(key, data) -> bytes`; `aes_ecb_decrypt(key, data) -> bytes`; `aes_cbc_encrypt(key, iv, data) -> bytes`; `aes_cbc_decrypt(key, iv, data) -> bytes`
- **imports:** cryptography, cryptography.hazmat.primitives.ciphers.algorithms, cryptography.hazmat.primitives.ciphers.base, cryptography.hazmat.primitives.ciphers.modes, cryptography.hazmat.primitives.padding, pypdf._crypt_providers._base, pypdf._utils, pypdf.errors, secrets

## `.local/lib/python3.13/site-packages/pypdf/_crypt_providers/_fallback.py`
_(no summary)_
- **classes:** CryptRC4, CryptAES
- **functions:** `rc4_encrypt(key, data) -> bytes`; `rc4_decrypt(key, data) -> bytes`; `aes_ecb_encrypt(key, data) -> bytes`; `aes_ecb_decrypt(key, data) -> bytes`; `aes_cbc_encrypt(key, iv, data) -> bytes`; `aes_cbc_decrypt(key, iv, data) -> bytes`
- **imports:** pypdf._crypt_providers._base, pypdf.errors

## `.local/lib/python3.13/site-packages/pypdf/_crypt_providers/_pycryptodome.py`
_(no summary)_
- **classes:** CryptRC4, CryptAES
- **functions:** `rc4_encrypt(key, data) -> bytes`; `rc4_decrypt(key, data) -> bytes`; `aes_ecb_encrypt(key, data) -> bytes`; `aes_ecb_decrypt(key, data) -> bytes`; `aes_cbc_encrypt(key, iv, data) -> bytes`; `aes_cbc_decrypt(key, iv, data) -> bytes`
- **imports:** Crypto, Crypto.Cipher, Crypto.Util.Padding, pypdf._crypt_providers._base, pypdf._utils, pypdf.errors, secrets

## `.local/lib/python3.13/site-packages/pypdf/_doc_common.py`
_(no summary)_
- **classes:** DocumentInformation, PdfDocCommon, LazyDict
- **functions:** `convert_to_int(d, size) -> Union[int, tuple[Any, ...]]`
- **imports:** _encryption, _page, _page_labels, _utils, abc, collections.abc, constants, datetime, errors, filters, generic, generic._files, struct, types, typing, xmp

## `.local/lib/python3.13/site-packages/pypdf/_encryption.py`
_(no summary)_
- **classes:** CryptFilter, AlgV4, AlgV5, PasswordType, EncryptAlgorithm, EncryptionValues, Encryption
- **functions:** `_padding(data) -> bytes`; `_saslprep(password) -> str`
- **imports:** _utils, enum, generic, hashlib, pypdf._crypt_providers, secrets, stringprep, struct, typing, unicodedata

## `.local/lib/python3.13/site-packages/pypdf/_font.py`
_(no summary)_
- **classes:** FontDescriptor, CoreFontMetrics, Font
- **imports:** __future__, _cmap, _codecs.adobe_glyphs, _utils, collections.abc, constants, dataclasses, errors, pypdf.generic, typing

## `.local/lib/python3.13/site-packages/pypdf/_page.py`
_(no summary)_
- **classes:** Transformation, ImageFile, VirtualListImages, PageObject, _VirtualList
- **functions:** `_get_rectangle(self, name, defaults) -> RectangleObject`; `_set_rectangle(self, name, value) -> None`; `_delete_rectangle(self, name) -> None`; `_create_rectangle_accessor(name, fallback) -> property`; `_get_fonts_walk(obj, fnt, emb) -> tuple[set[str], set[str]]`
- **imports:** _font, _protocols, _text_extraction, _text_extraction._text_extractor, _utils, collections.abc, constants, copy, dataclasses, decimal, errors, generic, io, math, pathlib, typing

## `.local/lib/python3.13/site-packages/pypdf/_page_labels.py`
_Page labels are shown by PDF viewers as "the page number"._
- **functions:** `number2uppercase_roman_numeral(num) -> str`; `number2lowercase_roman_numeral(number) -> str`; `number2uppercase_letter(number) -> str`; `number2lowercase_letter(number) -> str`; `get_label_from_nums(dictionary_object, index) -> str`; `index2label(reader, index) -> str`; `nums_insert(key, value, nums) -> None`; `nums_clear_range(key, page_index_to, nums) -> None`; `nums_next(key, nums) -> tuple[Optional[NumberObject], Optional[DictionaryObject]]`
- **imports:** _protocols, _utils, collections.abc, generic, typing

## `.local/lib/python3.13/site-packages/pypdf/_protocols.py`
_Helpers for working with PDF types._
- **classes:** PdfObjectProtocol, XmpInformationProtocol, PdfCommonDocProtocol, PdfReaderProtocol, PdfWriterProtocol
- **imports:** _utils, abc, pathlib, typing

## `.local/lib/python3.13/site-packages/pypdf/_reader.py`
_(no summary)_
- **classes:** PdfReader
- **imports:** _doc_common, _encryption, _utils, collections.abc, constants, errors, generic, io, os, pathlib, re, sys, types, typing, xmp

## `.local/lib/python3.13/site-packages/pypdf/_text_extraction/__init__.py`
_Code related to text extraction._
- **classes:** OrientationNotFoundError
- **functions:** `set_custom_rtl(_min, _max, specials) -> tuple[int, int, list[int]]`; `mult(m, n) -> list[float]`; `orient(m) -> int`; `crlf_space_check(text, cmtm_prev, cmtm_matrix, memo_cmtm, font_resource, orientations, output, font_size, visitor_text, str_widths, spacewidth, str_height) -> tuple[str, str, list[float], list[float]]`; `get_text_operands(operands, cm_matrix, tm_matrix, font, orientations) -> tuple[str, bool]`; `get_display_str(text, cm_matrix, tm_matrix, font_resource, font, text_operands, font_size, rtl_dir, visitor_text) -> tuple[str, bool, float]`
- **imports:** _font, generic, math, typing

## `.local/lib/python3.13/site-packages/pypdf/_text_extraction/_layout_mode/__init__.py`
_Layout mode text extraction extension for pypdf_
- **imports:** _fixed_width_page, _font

## `.local/lib/python3.13/site-packages/pypdf/_text_extraction/_layout_mode/_fixed_width_page.py`
_Extract PDF text preserving the layout of the source PDF_
- **classes:** BTGroup
- **functions:** `resolve_font(fonts, name) -> Font`; `bt_group(tj_op, rendered_text, displaced_tx) -> BTGroup`; `recurse_to_target_op(ops, text_state_mgr, end_target, fonts, strip_rotated) -> tuple[list[BTGroup], list[TextStateParams]]`; `y_coordinate_groups(bt_groups, debug_path) -> dict[int, list[BTGroup]]`; `text_show_operations(ops, fonts, strip_rotated, debug_path) -> list[BTGroup]`; `fixed_char_width(bt_groups, scale_weight) -> float`; `fixed_width_page(ty_groups, char_width, space_vertically, font_height_weight) -> str`
- **imports:** _font, _text_state_manager, _text_state_params, _utils, collections.abc, itertools, math, pathlib, typing

## `.local/lib/python3.13/site-packages/pypdf/_text_extraction/_layout_mode/_text_state_manager.py`
_manage the PDF transform stack during "layout" mode text extraction_
- **classes:** TextStateManager
- **imports:** _font, _text_state_params, collections, collections.abc, errors, typing

## `.local/lib/python3.13/site-packages/pypdf/_text_extraction/_layout_mode/_text_state_params.py`
_A dataclass that captures the CTM and Text State for a tj operation_
- **classes:** TextStateParams
- **imports:** _font, dataclasses, math, typing

## `.local/lib/python3.13/site-packages/pypdf/_text_extraction/_text_extractor.py`
_(no summary)_
- **classes:** TextExtraction
- **imports:** _font, generic, math, typing

## `.local/lib/python3.13/site-packages/pypdf/_utils.py`
_Utility functions for PDF library._
- **classes:** classproperty, File, Version
- **functions:** `parse_iso8824_date(text) -> Optional[datetime]`; `format_iso8824_date(dt) -> str`; `_get_max_pdf_version_header(header1, header2) -> str`; `read_until_whitespace(stream, maxchars) -> bytes`; `read_non_whitespace(stream) -> bytes`; `skip_over_whitespace(stream) -> bool`; `check_if_whitespace_only(value) -> bool`; `skip_over_comment(stream) -> None`; `read_until_regex() -> bytes`; `read_block_backwards(stream, to_read) -> bytes`; `read_previous_line(stream) -> bytes`; `matrix_multiply(a, b) -> TransformationMatrixType`; `mark_location(stream) -> None`; `deprecate(msg, stacklevel) -> None`; `deprecation(msg) -> NoReturn`; `deprecate_with_replacement(old_name, new_name, removed_in) -> None`; `deprecation_with_replacement(old_name, new_name, removed_in) -> NoReturn`; `deprecate_no_replacement(name, removed_in) -> None`; `deprecation_no_replacement(name, removed_in) -> NoReturn`; `logger_error(message) -> None`; `logger_warning(message) -> None`; `rename_kwargs(func_name, kwargs, aliases, fail) -> None`; `_human_readable_bytes(bytes) -> str`
- **imports:** dataclasses, datetime, errors, functools, io, logging, os, re, sys, typing, warnings

## `.local/lib/python3.13/site-packages/pypdf/_version.py`
_(no summary)_

## `.local/lib/python3.13/site-packages/pypdf/_writer.py`
_(no summary)_
- **classes:** ObjectDeletionFlag, PdfWriter
- **functions:** `_rolling_checksum(stream, blocksize) -> str`; `_pdf_objectify(obj) -> PdfObject`; `_create_outline_item(action_ref, title, color, italic, bold) -> TreeObject`
- **imports:** _doc_common, _encryption, _page, _page_labels, _reader, _utils, collections.abc, constants, decimal, enum, errors, generic, generic._appearance_stream, hashlib, io, itertools, pagerange, pathlib, re, struct, sys, types, typing, uuid, xmp

## `.local/lib/python3.13/site-packages/pypdf/annotations/__init__.py`
_PDF specifies several annotation types which pypdf makes available here._
- **imports:** _base, _markup_annotations, _non_markup_annotations

## `.local/lib/python3.13/site-packages/pypdf/annotations/_base.py`
_(no summary)_
- **classes:** AnnotationDictionary
- **imports:** abc, constants, generic, generic._data_structures

## `.local/lib/python3.13/site-packages/pypdf/annotations/_markup_annotations.py`
_(no summary)_
- **classes:** MarkupAnnotation, Text, FreeText, Line, PolyLine, Rectangle, Highlight, Ellipse, Polygon
- **functions:** `_get_bounding_rectangle(vertices) -> RectangleObject`
- **imports:** _base, abc, constants, generic, generic._base, generic._rectangle, generic._utils, sys, typing, uuid

## `.local/lib/python3.13/site-packages/pypdf/annotations/_non_markup_annotations.py`
_(no summary)_
- **classes:** Link, Popup
- **imports:** _base, generic._base, generic._data_structures, generic._fit, generic._rectangle, typing

## `.local/lib/python3.13/site-packages/pypdf/constants.py`
_Various constants, enums, and flags to aid readability._
- **classes:** StrEnum, Core, TrailerKeys, CatalogAttributes, EncryptionDictAttributes, UserAccessPermissions, Resources, PagesAttributes, PageAttributes, FileSpecificationDictionaryEntries, StreamAttributes, FilterTypes, FilterTypeAbbreviations, LzwFilterParameters, CcittFaxDecodeParameters, ImageAttributes, ColorSpaces, TypArguments, TypFitArguments, GoToActionArguments, AnnotationDictionaryAttributes, InteractiveFormDictEntries, FieldDictionaryAttributes, CheckboxRadioButtonAttributes, FieldFlag, DocumentInformationAttributes, PageLayouts, GraphicsStateParameters, CatalogDictionary, OutlineFontFlag, PageLabelStyle, AnnotationFlag, ImageType, AFRelationship, BorderStyles, FontFlags
- **imports:** enum

## `.local/lib/python3.13/site-packages/pypdf/errors.py`
_All errors/exceptions pypdf raises and all of the warnings it uses._
- **classes:** DeprecationError, DependencyError, PyPdfError, PdfReadError, PageSizeNotDefinedError, PdfReadWarning, PdfStreamError, ParseError, FileNotDecryptedError, WrongPasswordError, EmptyFileError, EmptyImageDataError, LimitReachedError, XmpDocumentError

## `.local/lib/python3.13/site-packages/pypdf/filters.py`
_Implementation of stream filters; §7.4 Filters of the PDF 2.0 specification._
- **classes:** FlateDecode, ASCIIHexDecode, RunLengthDecode, LZWDecode, ASCII85Decode, DCTDecode, JPXDecode, CCITTParameters, CCITTFaxDecode, JBIG2Decode
- **functions:** `_decompress_with_limit(data) -> bytes`; `decompress(data) -> bytes`; `__create_old_class_instance(K, columns, rows) -> NoReturn`; `_deprecate_inline_image_filters(filter_name, old_name, new_name) -> None`; `decode_stream_data(stream) -> bytes`
- **imports:** _codecs._codecs, _utils, base64, binascii, constants, dataclasses, errors, generic, math, os, pathlib, shutil, struct, subprocess, tempfile, typing, zlib

## `.local/lib/python3.13/site-packages/pypdf/generic/__init__.py`
_Implementation of generic PDF objects (dictionary, number, string, ...)._
- **imports:** _base, _data_structures, _files, _fit, _link, _outline, _rectangle, _utils, _viewerpref, constants

## `.local/lib/python3.13/site-packages/pypdf/generic/_appearance_stream.py`
_(no summary)_
- **classes:** BaseStreamConfig, BaseStreamAppearance, TextAlignment, TextStreamAppearance
- **imports:** __future__, _codecs, _codecs.core_font_metrics, _font, _utils, constants, dataclasses, enum, errors, generic, generic._base, io, re, typing

## `.local/lib/python3.13/site-packages/pypdf/generic/_base.py`
_(no summary)_
- **classes:** PdfObject, NullObject, BooleanObject, IndirectObject, FloatObject, NumberObject, ByteStringObject, TextStringObject, NameObject
- **functions:** `encode_pdfdocencoding(unicode_string) -> bytes`; `is_null_or_none(x) -> TypeGuard[Union[None, NullObject, IndirectObject]]`
- **imports:** _codecs, _protocols, _utils, binascii, codecs, collections.abc, errors, hashlib, math, re, struct, sys, typing

## `.local/lib/python3.13/site-packages/pypdf/generic/_data_structures.py`
_(no summary)_
- **classes:** ArrayObject, DictionaryObject, TreeObject, StreamObject, DecodedStreamObject, EncodedStreamObject, ContentStream, Field, Destination
- **functions:** `_reset_node_tree_relationship(child_obj) -> None`; `read_object(stream, pdf, forced_encoding) -> Union[PdfObject, int, str, ContentStream]`
- **imports:** _base, _fit, _image_inline, _protocols, _utils, collections.abc, constants, errors, io, logging, math, os, re, sys, typing

## `.local/lib/python3.13/site-packages/pypdf/generic/_files.py`
_(no summary)_
- **classes:** EmbeddedFile
- **imports:** __future__, bisect, functools, pypdf._utils, pypdf.constants, pypdf.errors, pypdf.generic, typing

## `.local/lib/python3.13/site-packages/pypdf/generic/_fit.py`
_(no summary)_
- **classes:** Fit
- **imports:** _base, typing

## `.local/lib/python3.13/site-packages/pypdf/generic/_image_inline.py`
_(no summary)_
- **functions:** `_check_end_image_marker(stream) -> bool`; `extract_inline__ascii_hex_decode(stream) -> bytes`; `extract_inline__ascii85_decode(stream) -> bytes`; `extract_inline__run_length_decode(stream) -> bytes`; `extract_inline__dct_decode(stream) -> bytes`; `extract_inline_default(stream) -> bytes`; `is_followed_by_binary_data(stream, length) -> bool`
- **imports:** _utils, errors, io, logging, typing

## `.local/lib/python3.13/site-packages/pypdf/generic/_image_xobject.py`
_Functions to convert an image XObject to an image_
- **functions:** `_get_image_mode(color_space, color_components, prev_mode, depth) -> tuple[mode_str_type, bool]`; `bits2byte(data, size, bits) -> bytes`; `_image_from_bytes(mode, size, data) -> Image.Image`; `__handle_flate__indexed(color_space) -> tuple[Any, Any, Any, Any]`; `_handle_flate(size, data, mode, color_space, colors, obj_as_text) -> tuple[Image.Image, str, str, bool]`; `_handle_jpx(size, data, mode, color_space, colors) -> tuple[Image.Image, str, str, bool]`; `_apply_decode(img, x_object, lfilters, color_space, invert_color) -> Image.Image`; `_get_mode_and_invert_color(x_object, colors, color_space) -> tuple[mode_str_type, bool]`; `_xobj_to_image(x_object, pillow_parameters) -> tuple[Optional[str], bytes, Any]`
- **imports:** _utils, constants, errors, generic, io, sys, typing

## `.local/lib/python3.13/site-packages/pypdf/generic/_link.py`
_(no summary)_
- **classes:** NamedReferenceLink, DirectReferenceLink
- **functions:** `extract_links(new_page, old_page) -> list[tuple[ReferenceLink, ReferenceLink]]`; `_build_link(indirect_object, page) -> Optional[ReferenceLink]`; `_create_link(reference, source_pdf) -> Optional[ReferenceLink]`
- **imports:** _utils, typing

## `.local/lib/python3.13/site-packages/pypdf/generic/_outline.py`
_(no summary)_
- **classes:** OutlineItem
- **imports:** _base, _data_structures, _utils, typing

## `.local/lib/python3.13/site-packages/pypdf/generic/_rectangle.py`
_(no summary)_
- **classes:** RectangleObject
- **imports:** _base, _data_structures, typing

## `.local/lib/python3.13/site-packages/pypdf/generic/_utils.py`
_(no summary)_
- **functions:** `hex_to_rgb(value) -> tuple[float, float, float]`; `read_hex_string_from_stream(stream, forced_encoding) -> Union['TextStringObject', 'ByteStringObject']`; `read_string_from_stream(stream, forced_encoding) -> Union['TextStringObject', 'ByteStringObject']`; `create_string_object(string, forced_encoding) -> Union[TextStringObject, ByteStringObject]`; `decode_pdfdocencoding(byte_array) -> str`
- **imports:** _base, _codecs, _utils, codecs, errors, typing

## `.local/lib/python3.13/site-packages/pypdf/generic/_viewerpref.py`
_(no summary)_
- **classes:** ViewerPreferences
- **imports:** _base, _data_structures, typing

## `.local/lib/python3.13/site-packages/pypdf/pagerange.py`
_Representation and utils for ranges of PDF file pages._
- **classes:** PageRange
- **functions:** `parse_filename_page_ranges(args) -> list[tuple[str, PageRange]]`
- **imports:** errors, re, typing

## `.local/lib/python3.13/site-packages/pypdf/papersizes.py`
_Helper to get paper sizes._
- **classes:** Dimensions, PaperSize
- **imports:** typing

## `.local/lib/python3.13/site-packages/pypdf/types.py`
_Helpers for working with PDF types._
- **imports:** generic._base, generic._data_structures, generic._outline, sys, typing

## `.local/lib/python3.13/site-packages/pypdf/xmp.py`
_Anything related to Extensible Metadata Platform (XMP) metadata._
- **classes:** _XmpBuilder, XmpInformation
- **functions:** `_identity(value) -> K`; `_converter_date(value) -> datetime.datetime`; `_format_datetime_utc(value) -> str`; `_generic_get(element, self, list_type, converter) -> Optional[list[str]]`
- **imports:** _protocols, _utils, collections.abc, datetime, decimal, errors, generic, re, string, typing, xml.dom.expatbuilder, xml.dom.minidom, xml.dom.xmlbuilder, xml.parsers.expat

## `cognition/__init__.py`
_cognition — Phase P4.5: "Thinking + knowing-what-it-knows"._
- **imports:** cognition.active_inference, cognition.affect, cognition.calibration, cognition.embodiment, cognition.guardrails, cognition.identity, cognition.neuro_symbolic, cognition.reasoning, cognition.society, cognition.thinker

## `cognition/_sandbox_worker.py`
_cognition/_sandbox_worker.py — isolated fit+score worker for P4.7 self-coding._
- **functions:** `_run(req) -> dict`; `main() -> None`
- **imports:** __future__, json, sys, warnings

## `cognition/active_inference.py`
_cognition/active_inference.py — principled surprise + curiosity (Phase P4.5)._
- **classes:** ActiveInferenceModel
- **functions:** `_kl(p, q) -> float`; `_entropy(p) -> float`
- **imports:** __future__, math

## `cognition/affect.py`
_cognition/affect.py — the brain's affect/mood channel (Phase P4.8)._
- **classes:** _GoEmotions, Mood
- **functions:** `_stub_scores(text) -> dict`; `_nrclex_scores(text) -> dict | None`
- **imports:** __future__, os

## `cognition/calibration.py`
_cognition/calibration.py — knowing what it knows; abstain + ask for help (Phase P4.5)._
- **classes:** CalibratedAbstainer
- **imports:** __future__, numpy

## `cognition/embodiment.py`
_cognition/embodiment.py — the P4.8 orchestrator: a personality with senses._
- **classes:** Embodiment
- **imports:** __future__, cognition.affect, cognition.identity, cognition.multimodal, cognition.society

## `cognition/guardrails.py`
_cognition/guardrails.py — the constitution / self-audit rail (Phase P4.5)._
- **classes:** Constitution
- **imports:** __future__, re

## `cognition/identity.py`
_cognition/identity.py — persistent self-model / persona (Phase P4.8)._
- **classes:** Identity
- **imports:** __future__, json, os

## `cognition/multimodal.py`
_cognition/multimodal.py — see / hear / speak (Phase P4.8)._
- **classes:** Ears, Voice, Eyes
- **functions:** `_models_off() -> bool`; `status() -> dict`
- **imports:** __future__, os

## `cognition/neuro_symbolic.py`
_cognition/neuro_symbolic.py — traceable logic + causal reasoning (Phase P4.5)._
- **classes:** SymbolicReasoner, CausalAnalyzer
- **functions:** `_scallop_available() -> bool`
- **imports:** __future__, threading

## `cognition/reasoning.py`
_cognition/reasoning.py — deliberate reasoning: ReAct + Tree-of-Thoughts (Phase P4.5)._
- **classes:** ReActState, ReasoningGraph
- **functions:** `_terms(q) -> list[str]`
- **imports:** __future__, langgraph.graph, re, typing

## `cognition/self_coding.py`
_cognition/self_coding.py — P4.7 Autonomy + self-coding: invent nodes, gate, admit._
- **classes:** NodeProposer, Sandbox, BenchmarkGate, SelfCodingLoop
- **imports:** __future__, json, os, subprocess, sys

## `cognition/society.py`
_cognition/society.py — society of mind: internal debate → vote (Phase P4.8)._
- **classes:** InternalDebate
- **functions:** `_default_chat()`; `_vote_from_text(text) -> int`; `_heuristic_vote(role, question, ctx) -> tuple[str, int]`
- **imports:** __future__, re

## `cognition/stream_of_mind.py`
_cognition/stream_of_mind.py — Stream-of-Mind + Global Workspace (Phase P4.6)._
- **classes:** Thought, GlobalWorkspace, StreamOfMind
- **functions:** `_ga_importance(text) -> float`
- **imports:** __future__, collections, core, itertools

## `cognition/thinker.py`
_cognition/thinker.py — the P4.5 orchestrator: "thinks, stays calibrated, asks for help"._
- **classes:** Thinker
- **imports:** __future__, cognition.active_inference, cognition.calibration, cognition.guardrails, cognition.neuro_symbolic, cognition.reasoning

## `cognition/verifier.py`
_cognition/verifier.py — verifier-guided reasoning (Pillar 18, ThinkPRM-style)._
- **classes:** StepVerifier
- **functions:** `_default_chat()`; `_heuristic_step_score(step) -> tuple[int, str]`; `_parse_score(text) -> tuple[int, str]`; `best_of_n(candidates, verify) -> dict`
- **imports:** __future__, re

## `config.py`
_config.py — central, safe secrets/config loader._
- **classes:** Settings
- **imports:** __future__, os, pathlib

## `core/__init__.py`
_(no summary)_

## `core/algo_registry.py`
_Declarative algorithm registry — the scalable 'way' to add ANY ML algorithm._
- **classes:** AlgoSpec
- **functions:** `register() -> AlgoSpec`; `import_obj(path)`; `spec_importable(spec) -> bool`
- **imports:** __future__, dataclasses, importlib

## `core/brain.py`
_GrowingBrain — grows the network by keeping only nodes that help._
- **classes:** GrowingBrain
- **functions:** `_roughness(x) -> float`; `_mean(proba_list, idxs) -> Vector`
- **imports:** __future__, core.node_protocol, eval.golden, native

## `core/brain_agent.py`
_core/brain_agent.py — LangGraph brain agent: "talk to the brain" (Phase P4.1)._
- **classes:** BrainState, BrainAgent
- **functions:** `_default_llm()`
- **imports:** __future__, langgraph.graph, typing

## `core/chat_brain.py`
_core/chat_brain.py — P4.1: chat with the brain (RAG-grounded, cloud-LLM)._
- **functions:** `_brain_state() -> str`; `_build_brain()`; `_brain()`; `_boss_route(message, history)`; `_credential_route(message)`; `chat(message, history) -> dict`; `_build_messages(message, context, history) -> list[dict]`; `chat_stream(message, history)`
- **imports:** __future__, core, glob, os, threading

## `core/columns.py`
_Column taxonomy — the SINGLE SOURCE OF TRUTH that groups the ~320 nodes._
- **classes:** Column, ColumnLayout
- **functions:** `column_for(name, kind) -> str`; `get_column(key) -> Column`; `group_factories(factories, names, kinds) -> dict[str, list[tuple]]`; `layout_for(grouped) -> list[dict]`
- **imports:** __future__, dataclasses

## `core/drift.py`
_Drift monitoring (Tier-3 infra, group K of the model catalog)._
- **classes:** StreamingDriftDetector
- **functions:** `data_drift(reference, current, threshold) -> dict`; `_extract_evidently_share(d)`
- **imports:** __future__, numpy, warnings

## `core/heads.py`
_Output heads — the multi-output contract for the prediction-graph network._
- **classes:** OutputHead
- **imports:** __future__, dataclasses

## `core/hpo.py`
_Optuna-backed hyperparameter optimization (Tier-2/3 infra, group H of the model catalog)._
- **functions:** `_suggest(trial, name, spec)`; `_rand_sample(rng, spec)`; `_optimize_optuna(objective, space, n_trials, direction, seed)`; `_optimize_nevergrad(objective, space, n_trials, direction, seed)`; `_optimize_cmaes(objective, space, n_trials, direction, seed)`; `_optimize_random(objective, space, n_trials, direction, seed)`; `optimize(objective, space, n_trials, direction, seed, backend) -> dict`; `tune_node(node_factory, space, X, y, n_trials, val_frac, seed, task) -> dict`
- **imports:** __future__, numpy, typing

## `core/llm.py`
_core/llm.py — P4.1 cloud-LLM access (the brain's "mouth"), reuse-first via LiteLLM._
- **classes:** NoLLMConfigured
- **functions:** `_candidates(providers) -> list[tuple[str, dict]]`; `_local_vision_model() -> str`; `active_model() -> tuple[str, dict] | None`; `provider_name(model) -> str`; `_label_from_key(key) -> str`; `_governor_on() -> bool`; `_cache_ttl() -> float`; `_cache_key(messages, max_tokens, temperature) -> str`; `_cache_get(key) -> str | None`; `_cache_put(key, text) -> None`; `_skippable(prov) -> bool`; `chat(messages, max_tokens, temperature, timeout, total_timeout) -> str`; `_image_data_url(img, mime) -> str`; `vision_available() -> bool`; `vision_chat(prompt, images) -> str`; `vision_order() -> list[str]`; `_telemetry(_fn, provider, ok, latency_ms, err)`; `configured_order() -> list[str]`; `chat_stream(messages, max_tokens, temperature, timeout)`
- **imports:** __future__, base64, config, hashlib, json, os, threading, time

## `core/llm_telemetry.py`
_Per-provider cloud-LLM telemetry (real call stats for the dashboard)._
- **functions:** `_blank() -> dict`; `_load() -> dict`; `_save(d) -> None`; `_is_rate_limit(err) -> bool`; `_is_permanent(err) -> bool`; `cooling(provider) -> bool`; `record(provider, ok, latency_ms, error) -> None`; `snapshot(order) -> dict`; `reset() -> None`
- **imports:** __future__, json, os, tempfile, threading, time

## `core/node_protocol.py`
_Node interface contracts for the prediction-graph network._
- **classes:** IOSchema, NodeProtocol, NodeInfo, BaseNode
- **imports:** __future__, dataclasses, typing

## `core/observability.py`
_core/observability.py — P4.6 durable observability (the brain "watches itself") via Langfuse._
- **classes:** _Span
- **functions:** `enabled() -> bool`; `_export_keys() -> None`; `tracer()`; `trace(name)`; `flush() -> None`; `status() -> dict`
- **imports:** __future__, config, contextlib, logging

## `core/registry.py`
_Live node registry — the single source of truth the dashboard reads._
- **functions:** `register(node, summary, upstream) -> None`; `set_metrics(name, metrics, trained) -> None`; `reset() -> None`; `snapshot() -> dict`
- **imports:** __future__, core.node_protocol

## `core/segments.py`
_Market-segment taxonomy — the CORTEX overlay that tags every neuron with a_
- **classes:** Segment, SegmentLayout
- **functions:** `segment_for(name, kind) -> str`; `get_segment(key) -> Segment`; `group_by_segment(factories, names, kinds) -> dict[str, list[tuple]]`; `segment_layout(grouped) -> list[dict]`
- **imports:** __future__, dataclasses

## `core/system_map.py`
_System map — the WHOLE brain as a wired graph with honest live statuses._
- **functions:** `_registry_count() -> int`; `_age(path) -> float | None`; `_fmt_age(a) -> str`; `_json_len(path) -> int`; `_probe(port, path) -> bool`; `_proc_running(needle) -> bool`; `_env_on(name) -> bool`; `_node(id_, label, layer, status, evidence, inputs, outputs)`; `_fresh_status(age, window_s, standby_why)`; `system_map() -> dict`
- **imports:** __future__, glob, json, os, time

## `core/trust.py`
_TrustLedger — CORTEX T7: regret-bounded per-node trust (design §1 T7, stitch rows 20-21)._
- **classes:** _OnlineBOCD, TrustLedger
- **imports:** __future__, json, math, numpy, os

## `dashboard/brain_live.py`
_dashboard/brain_live.py — LIVE brain snapshots from REAL data._
- **functions:** `_cached(key, fn)`; `_ccxt_client()`; `_real_journal()`; `_real_ohlcv(symbol, tf, limit)`; `_experience() -> dict`; `_patterns() -> dict`; `_pipeline() -> dict`; `_news() -> dict`; `live_news() -> dict`; `_skills() -> dict`; `live_skills() -> dict`; `_ensure_warm()`; `_warming(extra) -> dict`; `live_experience() -> dict`; `live_patterns() -> dict`; `live_pipeline() -> dict`
- **imports:** __future__, threading, time

## `dashboard/routes/__init__.py`
_(no summary)_

## `dashboard/routes/brain_ext.py`
_Extracted brain HTTP routes (dashboard/server.py split — Wave0-⑤, first verified seam)._
- **functions:** `_srv(h)`; `handle_ops(h)`; `handle_mind_events(h)`; `handle_agent_status(h)`; `_state_json(name, default)`; `handle_memory_status(h)`; `handle_hybrid_status(h)`; `handle_librarian_status(h)`; `handle_quiz_status(h)`; `handle_thinking_status(h)`; `handle_stream_status(h)`; `handle_boss(h)`; `handle_autonomy_status(h)`; `handle_embodiment_status(h)`; `handle_activity(h)`; `handle_learning(h)`; `handle_worldmodel(h)`; `handle_hypotheses(h)`; `handle_evolve(h)`; `handle_generators(h)`; `handle_researcher(h)`; `handle_goal_score(h)`; `handle_surface(h)`; `handle_evidence(h)`; `handle_ui_data(h)`; `handle_scouts(h)`; `handle_track_record(h)`; `handle_briefing(h)`; `handle_connectivity(h)`; `handle_curiosity(h)`; `handle_ui_health(h)`
- **imports:** json, os, sys

## `dashboard/routes/network_ext.py`
_Extracted network / state / knowledge HTTP routes (dashboard/server.py split — Wave0-⑤ Group 3)._
- **functions:** `_srv(h)`; `handle_state(h)`; `handle_state_routing(h)`; `handle_network_state(h)`; `handle_network_trust(h)`; `handle_network_system(h)`; `handle_network_antioverfit(h)`; `handle_knowledge(h)`; `handle_llm_telemetry(h)`; `handle_network_refresh(h)`; `handle_network_autoload(h)`
- **imports:** json, os, sys, time

## `dashboard/routes/post_ext.py`
_Extracted POST HTTP routes (dashboard/server.py split — Wave0-⑤ Group 4)._
- **functions:** `_srv(h)`; `handle_practice_start(h)`; `handle_brain_discovery_run(h)`; `handle_credentials_post(h)`; `handle_brain_learn(h)`; `handle_brain_web(h)`; `handle_chat(h)`; `handle_brain_agent(h)`; `handle_brain_ultra_remember(h)`; `handle_chat_stream(h)`; `handle_agui(h)`; `handle_crypto_params(h)`; `handle_closedtrades_reset(h)`; `handle_crypto_mode(h)`; `handle_online_control(h)`; `handle_gui_action(h)`; `handle_broker_sense_post(h)`
- **imports:** json, os, sys, threading

## `dashboard/routes/trading_ext.py`
_Extracted trading HTTP routes (dashboard/server.py split — Wave0-⑤ Group 2)._
- **functions:** `_srv(h)`; `handle_practice(h)`; `handle_venues(h)`; `handle_brain_discovery(h)`; `handle_status(h)`; `handle_crypto_status(h)`; `handle_crypto_markets(h)`; `handle_crypto_ingest(h)`; `handle_execution_status(h)`; `handle_options_status(h)`; `handle_journal_status(h)`; `handle_alerts_status(h)`; `handle_strategy_status(h)`; `handle_foundry(h)`; `handle_credentials(h)`; `handle_strategy_library(h)`; `handle_evolution_status(h)`; `handle_experience_status(h)`; `handle_selfeval_status(h)`; `handle_crypto_trades(h)`; `handle_crypto_predictions(h)`; `handle_patterns_status(h)`; `handle_news_status(h)`; `handle_skills_status(h)`; `handle_brain_status(h)`; `handle_advintel_status(h)`; `handle_tickers(h)`; `handle_candles(h)`; `handle_forecast(h)`; `handle_orderbook(h)`; `handle_scorecard(h)`; `_tg_cells(locked, dist)`; `handle_opentrades(h)`; `handle_brain_predict(h)`; `handle_psychology(h)`; `handle_brain_ultra(h)`; `handle_brain_metacognition(h)`; `handle_brain_debate(h)`; `handle_brain_decisions(h)`; `handle_gui_status(h)`; `handle_closedtrades(h)`; `handle_confidence(h)`; `handle_dreams(h)`; `handle_gate_tuning(h)`; `handle_mirror_stream(h)`; `handle_direction_truth(h)`; `handle_learning_curve(h)`; `handle_context(h)`; `handle_pnl_demos(h)`; `handle_watchlist(h)`; `handle_online_loop(h)`; `handle_onchain(h)`; `handle_online_status(h)`; `_bs_funnel(market)`; `handle_broker_sense(h)`; `handle_app_school(h)`; `handle_memory_search(h)`; `handle_connectivity(h)`; `handle_sandbox(h)`; `handle_trade_columns(h)`; `handle_segments(h)`; `_segments_snapshot() -> dict`; `handle_broker_features(h)`; `handle_broker_sources(h)`; `handle_remote_login(h)`; `handle_mirror(h)`; `handle_binance_edge(h)`; `handle_handoff(h)`; `handle_mirror_frame(h)`; `handle_live_browser_frame(h)`; `handle_live_browser(h)`; `handle_ocular(h)`
- **imports:** json, os, sys, time

## `dashboard/server.py`
_dashboard/server.py — zero-dependency dashboard server (stdlib http.server)._
- **classes:** Handler, BoundedHTTPServer
- **functions:** `_network_state_payload(path, now) -> dict`; `_network_trust_payload(path) -> dict`; `_network_refresh_allowed(now, last, running, min_interval_s) -> tuple[bool, str]`; `_network_refresh_start(now) -> dict`; `_brain_agent()`; `_gui_agent()`; `_trading_session()`; `_crypto_session()`; `_execution_engine()`; `_options_chain()`; `_ft_entry_meta(t) -> dict`; `_ft_entry_psych(t)`; `_uq_cells(uq) -> dict`; `_psych_cells(ps) -> dict`; `_trade_outcome_net()`; `_confidence_book() -> dict`; `_swr_refresh_async(path) -> None`; `_get_cache_ttl(path)`; `_cached_body(key, ttl, producer)`; `_bg_snapshot(key, producer, ttl) -> bytes`; `_warm_snapshots()`; `_enrich_predictions() -> None`; `_ccxt_spot()`; `_pool_ohlcv(symbol, tf, limit) -> list`; `_pool_order_book(symbol, limit) -> dict`; `_openalgo_positions() -> list`; `_openalgo_tradebook() -> list`; `_trade_segment(r) -> tuple[str, str]`; `_scorecard() -> dict`; `_usdinr() -> float`; `_candles(symbol, market, tf, limit) -> list[dict]`; `_forecast_payload(candles, k, symbol, tf) -> dict`; `_open_trades_rows() -> list[dict]`; `_slotted(fn)`; `main() -> None`
- **imports:** __future__, base64, http.server, json, os, sys, threading, time

## `dashboard/verify_render.py`
_(no summary)_
- **imports:** playwright.sync_api, sys

## `data/__init__.py`
_(no summary)_

## `data/benchmarks.py`
_Synthetic benchmark datasets with KNOWN generating processes (stdlib only)._
- **functions:** `mackey_glass(n, tau, beta, gamma, x0, noise, seed) -> list[float]`; `logistic_map(n, r, x0, noise, seed) -> list[float]`; `noisy_xor_series(n, noise, seed) -> list[float]`; `make_regime_dataset(n, noise_hi, seed) -> dict`; `_tercile_regime(deltas) -> list[int]`; `make_benchmark_dataset(name, n, noise) -> dict`
- **imports:** __future__, data, math, random

## `data/binance.py`
_Binance public market data (no key): intraday klines + order-book snapshots._
- **functions:** `_get(url, timeout)`; `fetch_klines(symbol, interval, total) -> str`; `load_klines(symbol, interval) -> list[tuple]`; `_multi_horizon_dir(closes, n_rows, horizons) -> tuple[dict, int]`; `make_kline_dataset(symbol, interval, target) -> dict`; `_interval_ms(interval) -> int`; `_latest_completed_idx(open_times, t, interval_ms) -> int`; `make_mtf_dataset(symbol, base, context, target, loader, label) -> dict`
- **imports:** __future__, data, data.dataset, data.sources, json, os, urllib.request

## `data/dataset.py`
_Assemble per-node golden datasets from cached crypto data._
- **functions:** `ensure(coins, days) -> dict`; `make_combined(coins, target, days) -> dict`; `make_dataset(coin, target) -> dict`; `chrono_split(X, y, train_frac) -> tuple`
- **imports:** __future__, data, data.sources

## `data/downloads.py`
_CORTEX B6 — real market-data downloaders (research/ultra-network-data-plan.md)._
- **functions:** `_ensure_cache() -> str`; `cached_path(name) -> str`; `download_stooq_daily(symbol) -> dict`; `download_binance(symbol, interval, total) -> list[tuple]`; `download_dukascopy(instrument, year, month, day, hours) -> dict`; `download_nse_bhavcopy(year, month, day) -> dict`; `list_nse_dump_symbols() -> list[str]`; `load_nse_minute(symbol)`; `download_nse_history(symbol, interval, days)`; `locate_freqtrade_1m(base) -> list[str]`
- **imports:** __future__, csv, io, lzma, numpy, os, struct, urllib.error, urllib.parse, urllib.request, zipfile

## `data/external.py`
_External real-world datasets — multi-dataset evaluation (CONVENTIONS §14)._
- **functions:** `_rows_from_values(dates, values) -> list[tuple]`; `load_indian_equity(symbol, period) -> list[tuple]`; `load_klines_yf(symbol, interval, period) -> list[tuple]`; `make_mtf_indian(symbol) -> dict`; `load_sunspots() -> list[tuple]`; `load_weather(lat, lon, start, end) -> list[tuple]`; `load_energy() -> list[tuple]`; `load_ecg(record, n, every) -> list[tuple]`; `make_external_dataset(source) -> dict`
- **imports:** __future__, csv, data, io, os, urllib.request

## `data/features.py`
_Feature & target engineering for crypto price series (pure stdlib)._
- **functions:** `_returns(closes) -> list[float]`; `_sma(closes, i, n) -> float`; `_std(xs) -> float`; `_rsi(closes, i, n) -> float`; `build(rows) -> dict`
- **imports:** __future__

## `data/orderbook.py`
_Order-book (L2) microstructure input — the project's stated path to real edge._
- **functions:** `snapshot(symbol, levels) -> dict`; `collect(symbol, n, every) -> str`; `_targets_from_mid(mids) -> dict`; `make_orderbook_dataset(symbol) -> dict`
- **imports:** __future__, data.sources, json, os, time, urllib.request

## `data/panel.py`
_Multi-asset PANEL data — a universe of timestamp-aligned series._
- **functions:** `_load_one(symbol, source)`; `make_panel(source, target) -> dict`
- **imports:** __future__, numpy

## `data/sources.py`
_Crypto data sources (stdlib HTTP only)._
- **functions:** `_get_json(url, headers, timeout) -> dict`; `_write_csv(rows, path, header) -> None`; `coingecko_daily(coin, days, vs) -> list[tuple]`; `fetch_coin(coin, days) -> tuple[str, int]`; `load_coin(coin) -> list[tuple]`; `etherscan_gas_oracle() -> dict`; `coinalyze_funding(symbol) -> dict`
- **imports:** __future__, config, json, os, time, urllib.request

## `eval/__init__.py`
_(no summary)_

## `eval/golden.py`
_Golden datasets + evaluation — the 'known input->output first' discipline._
- **functions:** `make_golden_dataset(n, noise, seed) -> tuple[Matrix, Labels]`; `train_test_split(X, y, test_frac, seed) -> tuple[Matrix, Labels, Matrix, Labels]`; `accuracy(pred, y) -> float`; `argmax_labels(pred_output) -> Labels`; `_macro_f1(pred, y, n_classes) -> float`; `_r2(pred, y) -> float`; `score_head(head, pred_output, y) -> dict`; `baseline_for(head, y_train, y_test) -> dict`; `selective_accuracy(proba, y, coverages) -> list[dict]`
- **imports:** __future__, core.heads, core.node_protocol, numpy, random

## `memory/__init__.py`
_(no summary)_

## `memory/associative.py`
_memory/associative.py — associative "connect-the-dots" memory (brain ultra-upgrade, Phase A)._
- **classes:** Note, AssociativeMemory
- **functions:** `_words(text) -> list[str]`; `_jaccard(a, b) -> float`; `_parse_json(reply) -> dict | None`
- **imports:** __future__, dataclasses, json, memory.graph, pathlib, re, uuid

## `memory/brain.py`
_KnowledgeBrain — the Phase-4 brain/memory layer._
- **classes:** KnowledgeBrain
- **functions:** `_slug(s) -> str`; `_chunk(text, words) -> list[str]`; `_read_pdf(path) -> str`; `_html_to_text(raw) -> str`; `get_brain() -> KnowledgeBrain`
- **imports:** __future__, collections, html, itertools, math, memory.graph, memory.store, os, re, urllib.request

## `memory/file_memory.py`
_memory/file_memory.py — durable one-fact-per-file memory, Claude-Code style (Phase B)._
- **classes:** FileMemory
- **functions:** `_slug(text) -> str`
- **imports:** __future__, pathlib, re

## `memory/graph.py`
_KnowledgeGraph — concept graph backed by NetworkX (reuse-first)._
- **classes:** _NetworkxGraph, _DictGraph
- **functions:** `KnowledgeGraph()`
- **imports:** __future__

## `memory/human_memory.py`
_memory/human_memory.py — human-like memory: decay, tiers, dreaming (Phase P4.2)._
- **classes:** MemMeta, HumanMemory
- **imports:** __future__, dataclasses, math

## `memory/hybrid_memory.py`
_memory/hybrid_memory.py — hybrid human memory (Phase P4.2), wired to REAL projects._
- **classes:** HybridMemory
- **functions:** `_default_llm()`
- **imports:** __future__, dataclasses, memory.associative, memory.human_memory, re, vendor.generative_agents_memory

## `memory/knowledge_tracing.py`
_memory/knowledge_tracing.py — EduKTM Deep Knowledge Tracing mastery (Phase P4.4, 2nd model)._
- **classes:** KnowledgeTracer
- **imports:** __future__, dataclasses

## `memory/librarian.py`
_memory/librarian.py — self-feeding internet: the brain reads on its own (Phase P4.3)._
- **classes:** Librarian
- **functions:** `_ddgs_search(query, max_results) -> list[dict]`; `_rss_fetch(url, limit) -> list[dict]`; `_arxiv_search(query, max_results) -> list[dict]`; `_trafilatura_extract(url) -> str`; `_count_by(items, key) -> dict`
- **imports:** __future__, dataclasses, hashlib, json, os

## `memory/self_quiz.py`
_memory/self_quiz.py — proof the brain gets smarter (Phase P4.4)._
- **classes:** MasteryQuiz
- **functions:** `_salient_term(text) -> str | None`
- **imports:** __future__, dataclasses, datetime, fsrs, re

## `memory/store.py`
_VectorMemory — semantic chunk store with neural embeddings (reuse-first)._
- **classes:** VectorMemory
- **functions:** `tokenize(text) -> list[str]`; `_build_embedding_function()`
- **imports:** __future__, collections, math, os, re, uuid

## `native/__init__.py`
_(no summary)_

## `native/fastops.py`
_ctypes wrapper for native hot kernels, with pure-Python fallback._
- **functions:** `_flat(rows)`; `logreg_train(Xs, y, lr, epochs)`; `mlp_train(Xs, y, H, lr, epochs, seed)`; `sqdists(X, q) -> list[float]`; `prepare(X)`; `sqdists_prepared(prepared, q) -> list[float]`
- **imports:** __future__, ctypes, math, os, random

## `nodes/__init__.py`
_(no summary)_

## `nodes/active_subnet.py`
_HierarchicalGateNode — CORTEX T4: hierarchical per-input active subnetwork._
- **classes:** HierarchicalGateNode
- **functions:** `_igraph_communities(coact) -> list[int]`; `_nx_communities(coact) -> list[int]`; `detect_communities(coact) -> list[int]`
- **imports:** __future__, core.node_protocol, nodes.gated_node, numpy

## `nodes/advanced_ml_nodes.py`
_Sklearn-style estimator wrappers for advanced ML libraries that are NOT_
- **classes:** BayesianGMMClassifier, SurvivalForestClassifier, XGBoostLSSRegressor, XGBoostLSSClassifier, LightGBMLSSRegressor, MetricLearnKNN, BARTRegressor, BARTClassifier, MMDFeature
- **functions:** `_Xf(X) -> np.ndarray`; `_xgblss_train(Xa, ya, n_estimators, eta, seed)`
- **imports:** __future__, numpy, warnings

## `nodes/advanced_nodes.py`
_Advanced / newly-researched node families behind the project NodeProtocol._
- **classes:** HawkesNode, NVARNode, SignatureNode, EDMNode, SOMNode, ELMNode, CopulaNode, RocketNode, NystroemNode
- **functions:** `hawkes_node(name)`; `nvar_node(name)`; `signature_node(name)`; `edm_node(name)`; `som_node(name)`; `elm_node(name)`; `copula_node(name)`; `rocket_node(name)`; `nystroem_node(name)`
- **imports:** __future__, core.node_protocol, nodes.quant_nodes, numpy, warnings

## `nodes/autoload.py`
_pkgutil node auto-loader — the full generalization of ``nodes.pool._extra_candidates``._
- **functions:** `_base_node()`; `_no_required_args(obj) -> bool`; `_is_concrete_node_class(cls, base) -> bool`; `_sweep(exclude_names)`; `discover(exclude_names) -> list[tuple]`; `summary(exclude_names) -> dict`
- **imports:** __future__, importlib, inspect, nodes, pkgutil

## `nodes/automl_node.py`
_AutoGluonNode — the plan's Phase-1 *production* stacked-ensemble node._
- **classes:** AutoGluonNode
- **imports:** __future__, core.node_protocol, numpy, tempfile

## `nodes/base_learners.py`
_Base prediction nodes (pure-Python, CPU-only, zero deps)._
- **classes:** LogisticRegressionNode, KNNNode, DecisionStumpNode
- **functions:** `_sigmoid(z) -> float`
- **imports:** __future__, core.node_protocol, math, native

## `nodes/cascade_node.py`
_DeepCascadeNode — P3.6: the DEEP CASCADE (a deep, grown, gated model-network)._
- **classes:** DeepCascadeNode
- **imports:** __future__, core.node_protocol, eval.golden, nodes.gated_node, numpy

## `nodes/chaos_nodes.py`
_Step 3: chaos / nonlinear-dynamics node families (pure-Python)._
- **classes:** RecurrenceNode, ChaosFeatureNode
- **imports:** __future__, core.node_protocol, native, nodes.base_learners

## `nodes/column_network.py`
_ColumnNetwork — OPTIONS B, C, D + dynamic brain-driven I/O._
- **classes:** ColumnNetworkNode, ColumnNetwork
- **imports:** __future__, core.columns, core.node_protocol, nodes.cascade_node, nodes.column_node, nodes.gated_node, numpy

## `nodes/column_node.py`
_ColumnNode — OPTION A: the intra-column differentiable gate._
- **classes:** ColumnNode
- **imports:** __future__, core.columns, core.node_protocol, nodes.gated_node, numpy

## `nodes/cross_sectional_nodes.py`
_Cross-sectional / portfolio nodes — operate ACROSS a multi-asset panel._
- **classes:** _PanelNode, CrossSectionalRankNode, CrossSectionalZScoreNode, WorldQuant101CSNode, MarketFactorBetaNode, HRPWeightNode, MinCVaRWeightNode
- **functions:** `_readout(task)`; `_xs_rank(value, row) -> float`; `_xs_z(value, row) -> float`; `_mom(R, t, k) -> np.ndarray`; `_vol(R, t, k) -> np.ndarray`; `build_cross_sectional_nodes(panel) -> list`
- **imports:** __future__, core.node_protocol, numpy, warnings

## `nodes/denoise_nodes.py`
_Signal-from-noise separation / denoising nodes (behind the project_
- **classes:** _DenoiseFeat, RobustPCANode, SignalDecompNode, PicardICANode, VMDNode, EWTNode, FastICANode, DictLearnNode, SVDDenoiseNode, SavgolDenoiseNode, TVWaveletDenoiseNode
- **functions:** `_energy(x) -> float`; `_hankel(w, rows) -> np.ndarray`; `robust_pca_node() -> RobustPCANode`; `signal_decomp_node() -> SignalDecompNode`; `picard_ica_node() -> PicardICANode`; `vmd_node() -> VMDNode`; `ewt_node() -> EWTNode`; `fast_ica_node() -> FastICANode`; `dict_learn_node() -> DictLearnNode`; `svd_denoise_node() -> SVDDenoiseNode`; `savgol_denoise_node() -> SavgolDenoiseNode`; `tv_wavelet_denoise_node() -> TVWaveletDenoiseNode`
- **imports:** __future__, core.node_protocol, nodes.quant_nodes, numpy, warnings

## `nodes/detect_nodes.py`
_Detection / discovery nodes — "is the structure real, weak, or random?"._
- **classes:** SurrogateTestNode, MultitaperFtestNode, LombScargleFAPNode, MatchedFilterNode, BOCPDNode, ZeroOneChaosNode, NCDNode, StochResonanceNode, TslearnSAXNode, TslearnShapeletNode, RecurringStateNode
- **functions:** `_quiet()`; `_clean(vals, n) -> list[float]`; `_z(w) -> np.ndarray`; `surrogate_test_node() -> SurrogateTestNode`; `multitaper_ftest_node() -> MultitaperFtestNode`; `lombscargle_fap_node() -> LombScargleFAPNode`; `matched_filter_node() -> MatchedFilterNode`; `bocpd_node() -> BOCPDNode`; `zero_one_chaos_node() -> ZeroOneChaosNode`; `ncd_node() -> NCDNode`; `stoch_resonance_node() -> StochResonanceNode`; `tslearn_sax_node() -> TslearnSAXNode`; `tslearn_shapelet_node() -> TslearnShapeletNode`; `recurring_state_node() -> RecurringStateNode`
- **imports:** __future__, contextlib, core.node_protocol, nodes.quant_nodes, numpy, warnings

## `nodes/dl_nodes.py`
_CPU-practical deep-learning / transformer time-series PREDICTOR nodes._
- **classes:** _ARFallback, _DLForecastBase, NHiTSNode, TCNNode, NBEATSNode, TSMixerNode, GRUNode, LSTMNode, AEAnomalyNode, TabPFNNode
- **functions:** `_silence()`; `_timeseries(y)`; `tabpfn_node(name)`; `nhits_node(name)`; `tcn_node(name)`; `nbeats_node(name)`; `tsmixer_node(name)`; `gru_node(name)`; `lstm_node(name)`; `ae_anomaly_node(name)`
- **imports:** __future__, core.node_protocol, nodes.quant_nodes, numpy, time, warnings

## `nodes/dynamic_bus.py`
_DynamicBusNode — P3.7: the DYNAMIC I/O BUS (non-fixed inputs & outputs)._
- **classes:** DynamicBusNode
- **functions:** `_bus_module(widths, D, K, cls, seed)`
- **imports:** __future__, core.node_protocol, nodes.gated_node, numpy

## `nodes/dynamics_nodes.py`
_Nonlinear-dynamics / chaos / physics nodes — the reuse-first dynamics layer._
- **classes:** _Base, SINDyNode, RQANode, PermEntropyNode, AntropyNode, DMDNode, TransferEntropyNode
- **functions:** `sindy_node(name, col, W) -> SINDyNode`; `rqa_node(name, col, W) -> RQANode`; `permentropy_node(name, col, W) -> PermEntropyNode`; `antropy_node(name, col, W) -> AntropyNode`; `dmd_node(name, col, W) -> DMDNode`; `transfer_entropy_node(name, col, col2, W) -> TransferEntropyNode`
- **imports:** __future__, core.node_protocol, numpy, warnings

## `nodes/foundation_nodes.py`
_Tier-1 foundation / SOTA model nodes (groups A–F of research/model-catalog-22parts.md)._
- **classes:** _ExternalForecastBase, ChronosNode, TimesFMNode, TimeMoENode, TinyTimeMixerNode, MoiraiNode, LagLlamaNode, _NFForecastBase, PatchTSTNode, ITransformerNode, TFTNode, GPyTorchGPNode, _TorchLoadTrusted, GluonTSDeepARNode, CrossAssetGNNNode, TigramiteCausalNode, RiskfolioWeightNode, PyPortfolioOptWeightNode
- **functions:** `_add_vendor_path()`
- **imports:** __future__, core.node_protocol, nodes.cross_sectional_nodes, nodes.dl_nodes, nodes.quant_nodes, numpy, os, sys, warnings

## `nodes/frontier_nodes.py`
_Frontier nodes: quantum-inspired kernels, a reinforcement-learning policy, and_
- **classes:** QuantumKernelNode, RLPolicyNode, OptionIVNode
- **functions:** `_http_json(url, timeout) -> dict`; `quantum_kernel_node(name)`; `rl_policy_node(name)`; `option_iv_node(name)`
- **imports:** __future__, core.node_protocol, json, nodes.quant_nodes, numpy, os, ssl, time, urllib.request, warnings

## `nodes/gated_node.py`
_GatedMoENode — P3.5: the DIFFERENTIABLE GATE (the real neural-network loop)._
- **classes:** GatedMoENode
- **functions:** `kfold_indices(n, folds) -> list[list[int]]`; `standardize_fit(Xa) -> tuple[np.ndarray, np.ndarray]`; `_build_gate(d, E, use_kan)`; `gate_train(Xz, meta, y, cls, epochs, lr, balance_coef, noisy, top_k, seed, prior_bias, use_kan)`; `gate_weights(gate, noise, Xz, top_k, E, prior_bias) -> np.ndarray`; `gate_combine(w, meta, cls) -> np.ndarray`
- **imports:** __future__, core.node_protocol, numpy

## `nodes/github_feature_nodes.py`
_Feature-extractor nodes wrapping established GitHub/OSS projects._
- **classes:** TALibNode, NeuroKit2Node, LibrosaNode, EntropyHubNode, TSFELNode, FracDiffNode
- **functions:** `_clean(vals, n) -> list[float]`; `_last_finite(arr) -> float`; `_fracdiff_weights(d, size) -> np.ndarray`; `talib_node()`; `neurokit2_node()`; `librosa_node()`; `entropyhub_node()`; `tsfel_node()`; `fracdiff_node()`
- **imports:** __future__, core.node_protocol, nodes.quant_nodes, numpy, warnings

## `nodes/github_predict_nodes.py`
_GitHub-project predictor nodes — CatBoost, NGBoost, EBM, skforecast._
- **classes:** _DirectNode, CatBoostNode, NGBoostNode, EBMNode, _HeadBase, SkforecastNode
- **functions:** `_readout(task)`; `catboost_node() -> CatBoostNode`; `ngboost_node() -> NGBoostNode`; `ebm_node() -> EBMNode`; `skforecast_node() -> SkforecastNode`
- **imports:** __future__, core.node_protocol, numpy, warnings

## `nodes/github_t2_feature.py`
_GitHub tier-2 feature / anomaly nodes (signal • math • graph • ml)._
- **classes:** SSQueezeNode, ScikitDimNode, Node2VecGraphNode, FeatureEngineNode, StockStatsNode, PandasTAClassicNode, TANode, ADTKAnomalyNode
- **functions:** `_clean(vals, n) -> list[float]`; `_ohlc(win) -> 'object'`; `ssqueeze_node()`; `scikit_dim_node()`; `node2vec_graph_node()`; `feature_engine_node()`; `stockstats_node()`; `pandas_ta_classic_node()`; `ta_node()`; `adtk_anomaly_node()`
- **imports:** __future__, core.node_protocol, nodes.quant_nodes, numpy, time, warnings

## `nodes/github_t2_predict.py`
_GitHub-tier-2 predictor / probabilistic / dynamics nodes (T2)._
- **classes:** _HeadBase, _Aug, _ForecastBase, MLForecastNode, FunctimeNode, AutoTSNode, FLAMLNode, DeeptimeNode, PomegranateHMMNode, PgmpyBayesNetNode, EconMLNode, PykalmanNode, SimdKalmanNode
- **functions:** `_readout(task)`; `mlforecast_node()`; `functime_node()`; `flaml_node()`; `autots_node()`; `deeptime_node()`; `pomegranate_hmm_node()`; `pgmpy_bayesnet_node()`; `econml_node()`; `pykalman_node()`; `simdkalman_node()`
- **imports:** __future__, core.node_protocol, datetime, numpy, os, warnings

## `nodes/intermarket_gnn.py`
_AI-scientist idea #10 — Intermarket Graph Neural Net (PyG)._
- **classes:** IntermarketGNNNode
- **functions:** `_knn_edges(corr, k) -> np.ndarray`; `intermarket_gnn_node(name) -> IntermarketGNNNode`
- **imports:** __future__, core.node_protocol, numpy

## `nodes/llm_forecast_node.py`
_LLMForecastNode — cloud-LLM as a reasoning-based directional forecaster._
- **classes:** LLMForecastNode
- **imports:** __future__, json, nodes.quant_nodes, numpy, re, warnings

## `nodes/lob_transformer.py`
_AI-scientist idea #6 — LiT: Limit-Order-Book Transformer for short-horizon direction._
- **classes:** LOBTransformerNode
- **functions:** `lob_transformer_node(name) -> LOBTransformerNode`
- **imports:** __future__, core.node_protocol, math, numpy

## `nodes/loop_nodes.py`
_nodes/loop_nodes.py — autoload shims for the trading-side LOOP nodes (#13 fix)._
- **classes:** SelfEvolveLoopNode, RlExecPolicyNode
- **imports:** __future__, core.node_protocol

## `nodes/micro_transformer_node.py`
_nodes/micro_transformer_node.py — the brain's OWN micro-LLM (Phase C, clone-and-extend)._
- **classes:** StreamTokenizer, MicroTransformerNode, CInferenceKernel
- **imports:** __future__, core.node_protocol, math, pathlib, subprocess

## `nodes/ml_nodes.py`
_Advanced ML / topology / control nodes — the reuse-first expansion of the_
- **classes:** _HeadMixin, _FeatureBase, Catch22Node, TsfreshNode, TDANode, CausalSelectNode, GaussianProcessNode, _ForecastBase, DartsForecastNode, ControlSysIDNode
- **functions:** `_readout(task)`; `_ar_fit(s, p)`; `_ar_forecast_column(coef, c0, p, s_train, s_eval) -> np.ndarray`; `gaussian_process_node(max_rows, name) -> GaussianProcessNode`; `catch22_node(win, col, name) -> Catch22Node`; `tsfresh_node(win, col, name) -> TsfreshNode`; `tda_node(win, col, name) -> TDANode`; `causal_select_node(top_k, name) -> CausalSelectNode`; `darts_forecast_node(lags, col, name) -> DartsForecastNode`; `control_sysid_node(lags, col, name) -> ControlSysIDNode`
- **imports:** __future__, core.node_protocol, numpy, warnings

## `nodes/neat_lane.py`
_CORTEX B5 — Evolution lane (design §1 T6 signal 5, §6 B5)._
- **classes:** EvolveTelemetry, NeatLane, ReinforceEdgeLearner, GrowPruneController
- **functions:** `signals_from_scores(scores, enter, exit_) -> tuple[np.ndarray, np.ndarray]`; `zero_cost_triage(scores, close) -> tuple[bool, dict]`
- **imports:** __future__, dataclasses, numpy, os, tempfile, trading.fitness

## `nodes/noise_router.py`
_NoiseRegimeRouter (ii) — route by detected noise/chaos regime, learning which_
- **classes:** NoiseRegimeRouter
- **imports:** __future__, core.node_protocol, eval.golden

## `nodes/online_nodes.py`
_Online / incremental-learning nodes (River) — the growing-brain fit._
- **classes:** RiverNode
- **functions:** `_rows_to_dicts(X) -> list[dict]`; `_logreg_factory(task)`; `_hoeffding_factory(task)`; `_arf_factory(task)`; `river_logreg_node(name)`; `river_hoeffding_node(name)`; `river_arf_node(name)`
- **imports:** __future__, core.node_protocol, numpy, warnings

## `nodes/oss_nodes.py`
_OSS-backed prediction nodes — the reuse-first realignment of the node layer._
- **classes:** SklearnNode, SklearnRegressorNode, ReservoirPyNode, HMMRegimeNode, NoldsChaosNode, SklearnStackingNode
- **functions:** `logreg_node(name) -> SklearnNode`; `knn_node(k, name) -> SklearnNode`; `stump_node(name) -> SklearnNode`; `tree_node(depth, name) -> SklearnNode`; `mlp_node(hidden, name) -> SklearnNode`; `gaussnb_node(name) -> SklearnNode`; `rf_node(n_trees, depth, name) -> SklearnNode`; `gbdt_node(n_trees, name) -> SklearnNode`; `svm_node(name) -> SklearnNode`; `xgboost_node(n_trees, depth, name) -> SklearnNode`; `lightgbm_node(n_trees, leaves, name) -> SklearnNode`; `rf_multiclass_node(n_trees, depth, name) -> SklearnNode`; `logreg_multiclass_node(name) -> SklearnNode`; `ridge_reg_node(alpha, name) -> SklearnRegressorNode`; `rf_reg_node(n_trees, depth, name) -> SklearnRegressorNode`; `gbdt_reg_node(n_trees, name) -> SklearnRegressorNode`; `xgb_reg_node(n_trees, depth, name) -> SklearnRegressorNode`
- **imports:** __future__, core.node_protocol, numpy

## `nodes/phase2_nodes.py`
_Phase-2 node families (pure-Python, CPU-only) — more diverse 'neurons'._
- **classes:** MLPNode, ReservoirNode, GaussianNBNode
- **functions:** `_standardizer(X)`
- **imports:** __future__, core.node_protocol, math, native, nodes.base_learners, random

## `nodes/phase2b_nodes.py`
_Phase-2b node families (pure-Python): Random Forest + Regime-Gated._
- **classes:** _Tree, RandomForestNode, RegimeGatedNode
- **functions:** `_gini(pos, n) -> float`
- **imports:** __future__, core.node_protocol, nodes.base_learners, random

## `nodes/pool.py`
_Shared candidate pool of node families + hyperparameter variants._
- **functions:** `_oss_candidates()`; `_micro_llm_candidates()`; `_foundation_candidates()`; `foundation_panel_candidates(panel)`; `_foundation_candidates_cached()`; `foundation_factories()`; `foundation_names()`; `_extra_candidates()`; `autoload_report()`; `factories()`; `names()`
- **imports:** __future__, nodes.base_learners, nodes.chaos_nodes, nodes.phase2_nodes, nodes.phase2b_nodes, os

## `nodes/probabilistic_nodes.py`
_Uncertainty / probabilistic / symbolic / fuzzy / survival nodes._
- **classes:** _HeadBase, ConformalNode, ProphetNode, GplearnSymbolicNode, FuzzyTSNode, BayesianNode, SurvivalHazardNode
- **functions:** `_readout(task)`; `_base_matrix(X) -> np.ndarray`; `conformal_node()`; `prophet_node()`; `gplearn_symbolic_node()`; `fuzzy_ts_node()`; `bayesian_node()`; `survival_hazard_node()`
- **imports:** __future__, core.node_protocol, logging, numpy, os, time, warnings

## `nodes/quant_factor_nodes.py`
_Quant-finance FACTOR feature nodes — single-series (price/return) factor_
- **classes:** Alpha158Node, WQTimeSeriesAlphaNode, EmpyricalRiskNode
- **functions:** `_quiet()`; `_fin(v) -> float`; `alpha158_node() -> Alpha158Node`; `wq_timeseries_alpha_node() -> WQTimeSeriesAlphaNode`; `empyrical_risk_node() -> EmpyricalRiskNode`
- **imports:** __future__, contextlib, core.node_protocol, nodes.quant_nodes, numpy, warnings

## `nodes/quant_nodes.py`
_Quant / finance / math-structure nodes — OSS time-series & extreme-value_
- **classes:** _QBase, _FeatNode, _PredNode, GarchVolNode, EVTTailNode, StateSpaceNode, StatsForecastNode, ADFStationarityNode, CointSpreadNode, _HeadBase, _WindowFeat, EWMAVolNode
- **functions:** `_quiet()`; `garch_vol_node(col, win, name) -> GarchVolNode`; `evt_tail_node(col, win, name) -> EVTTailNode`; `state_space_node(col, win, name) -> StateSpaceNode`; `statsforecast_node(col, win, name) -> StatsForecastNode`; `adf_stationarity_node(col, win, name) -> ADFStationarityNode`; `coint_spread_node(col0, col1, win, name) -> CointSpreadNode`; `_compat_readout(task)`; `ewma_vol_node(name)`
- **imports:** __future__, contextlib, core.node_protocol, numpy, warnings

## `nodes/quant_signal_nodes.py`
_Quant-finance SIGNAL + LABELING nodes behind the project NodeProtocol._
- **classes:** TSMOMNode, OUMeanReversionNode, BollingerZNode, MetaLabelingNode, TripleBarrierNode
- **functions:** `_log_returns(win) -> np.ndarray`; `_realized_vol(win) -> float`; `tsmom_node() -> TSMOMNode`; `ou_meanrev_node() -> OUMeanReversionNode`; `bollinger_z_node() -> BollingerZNode`; `meta_labeling_node() -> MetaLabelingNode`; `triple_barrier_node() -> TripleBarrierNode`
- **imports:** __future__, nodes.quant_nodes, numpy, warnings

## `nodes/reflex.py`
_ReflexArc — CORTEX T3: conditional compute (compute routed like signal)._
- **classes:** ReflexArc
- **functions:** `ltt_threshold(conf, correct, alpha, min_support) -> float`
- **imports:** __future__, core.node_protocol, nodes.gated_node, numpy

## `nodes/regime_moe.py`
_AI-scientist idea #7 — Regime-conditioned MoE router (learned gating over frozen experts)._
- **classes:** RegimeMoERouter
- **functions:** `_default_experts()`; `regime_moe_node(name) -> RegimeMoERouter`
- **imports:** __future__, core.node_protocol, numpy

## `nodes/router_node.py`
_LearnedRouterNode — Phase 3: dynamic routing between full-model nodes._
- **classes:** LearnedRouterNode, HellsembleRouterNode, DeepRouterNode
- **functions:** `_roughness(x) -> float`; `_argmax(row) -> int`; `_split_groups(items, g) -> list[list]`
- **imports:** __future__, core.node_protocol, native

## `nodes/routing_advanced.py`
_Ultra-advanced routing/combination nodes — the reuse-first Phase-3 frontier._
- **classes:** DESRouterNode, ConformalGatedRouterNode, CaruanaEnsembleNode
- **functions:** `_apply_sklearn_compat() -> None`; `_sklearn_adapter()`; `_split(X, y, frac)`; `_argmax_rows(out) -> Labels`
- **imports:** __future__, core.node_protocol, numpy, warnings

## `nodes/scratch_core.py`
_From-scratch NumPy pedagogical core — CANON-11..15 (GRC + NNM videos)._
- **classes:** ScratchNet, ScratchRNN, ScratchNetNode, ScratchRNNNode
- **functions:** `validate_forward(net, weights, X, y) -> float`; `scratch_net_node(name) -> ScratchNetNode`; `scratch_rnn_node(name) -> ScratchRNNNode`; `run_mnist_check(max_samples, epochs) -> float`
- **imports:** __future__, core.node_protocol, numpy

## `nodes/signal_nodes.py`
_Signal-in-noise / pattern-detection nodes — the reuse-first signal layer._
- **classes:** _Base, StumpyMatrixProfileNode, PyODAnomalyNode, WaveletEnergyNode, EMDEnergyNode, SSANode, KalmanLevelNode, RMTSignalNode, NISTRandomnessNode
- **functions:** `stumpy_matrix_profile_node(col, W, name) -> StumpyMatrixProfileNode`; `pyod_anomaly_node(col, W, name) -> PyODAnomalyNode`; `wavelet_energy_node(col, W, name) -> WaveletEnergyNode`; `emd_energy_node(col, W, name) -> EMDEnergyNode`; `ssa_node(col, W, name) -> SSANode`; `kalman_level_node(col, W, name) -> KalmanLevelNode`; `rmt_signal_node(W, name) -> RMTSignalNode`; `nist_randomness_node(col, W, name) -> NISTRandomnessNode`
- **imports:** __future__, core.node_protocol, numpy, warnings

## `nodes/spectral_nodes.py`
_Spectral / manifold / functional / regime nodes (OSS behind NodeProtocol)._
- **classes:** _HeadBase, _WindowFeat, SpectralNode, LombScargleNode, HilbertNode, ManifoldNode, FunctionalDataNode, RegimeNode
- **functions:** `_readout(task)`; `spectral_node()`; `lombscargle_node()`; `hilbert_node()`; `manifold_node()`; `functional_data_node()`; `regime_node()`
- **imports:** __future__, core.node_protocol, numpy, warnings

## `nodes/stacking_node.py`
_StackingEnsembleNode — the Phase-1 'models as nodes' core._
- **classes:** StackingEnsembleNode
- **functions:** `_kfold_indices(n, folds) -> list[list[int]]`
- **imports:** __future__, core.node_protocol, nodes.base_learners

## `nodes/structure_nodes.py`
_Structure / graph / topology nodes — visibility graphs, multifractal spectrum,_
- **classes:** VisibilityGraphNode, MultifractalNode, OptimalTransportNode, TensorDecompNode
- **functions:** `visibility_graph_node(name)`; `multifractal_node(name)`; `optimal_transport_node(name)`; `tensor_decomp_node(name)`
- **imports:** __future__, nodes.quant_nodes, numpy, warnings

## `nodes/structure_search.py`
_StructureSearchNode — P3.9: LEARN THE WIRING (differentiable architecture search)._
- **classes:** StructureSearchNode
- **imports:** __future__, core.node_protocol, nodes.gated_node, numpy

## `nodes/symbolic_node.py`
_PySRNode — the plan's Phase-5 equation-discovery node._
- **classes:** PySRNode
- **imports:** __future__, core.node_protocol, numpy

## `nodes/tier2_nodes.py`
_Tier-2 model nodes (groups G/J/K of research/model-catalog-22parts.md)._
- **classes:** KANNode, XLSTMNode, LiquidLTCNode, NeuralCDENode, QuantLibGreeksNode, MarkovRegimeNode
- **functions:** `_standardize(A)`
- **imports:** __future__, core.node_protocol, nodes.quant_nodes, numpy, warnings

## `nodes/tier2b_nodes.py`
_Remaining catalog ADDs (the MED/LOW-priority nodes skipped in passes 1–4)._
- **classes:** TiDENode, TimesNetNode, TimeMixerNode, MambaNode, NormFlowNode, BayesianTorchNode, LiNGAMNode
- **imports:** __future__, core.node_protocol, nodes.foundation_nodes, nodes.quant_nodes, numpy, warnings

## `nodes/tier3_nodes.py`
_Tier-3 infra nodes (groups D/I/J of research/model-catalog-22parts.md)._
- **classes:** SB3RLExecNode, Alpha360Node, PyGODAnomalyNode, TemporalGraphNode
- **imports:** __future__, core.node_protocol, nodes.quant_nodes, numpy, warnings

## `nodes/tsfm_ensemble.py`
_AI-scientist idea #5 — TSFM ensemble + conformal calibration._
- **classes:** TSFMEnsembleNode
- **functions:** `_member_classes()`; `tsfm_ensemble_node(name) -> TSFMEnsembleNode`
- **imports:** __future__, core.node_protocol, nodes.foundation_nodes, numpy

## `nodes/universal_node.py`
_UniversalNode — builds a NodeProtocol node from any AlgoSpec (core/algo_registry)._
- **classes:** UniversalNode
- **functions:** `build_nodes(task) -> list`
- **imports:** __future__, core.algo_registry, core.node_protocol, numpy, os, warnings

## `nodes/vae_factor.py`
_AI-scientist idea #9 — VAE synthetic factors + scenario generator (CPU torch)._
- **classes:** VAEFactorNode, SyntheticScenarioGenerator
- **functions:** `vae_factor_node(name) -> VAEFactorNode`
- **imports:** __future__, core.node_protocol, numpy

## `nodes/video_lanes.py`
_Video framework lanes — faithful implementations, every one a neuron._
- **classes:** _LaneBase, TCNProbNode, EncoderTransformerNode, LSTMLaneNode, SkMLPLaneNode, TorchMLPLaneNode, DLinearNode
- **functions:** `build_windows(X_2d, lookback, target_col, horizon)`; `_build_dlinear(seq_len, pred_len, kernel_size)`; `tcn_prob_node(name) -> TCNProbNode`; `encoder_transformer_node(name) -> EncoderTransformerNode`; `lstm_lane_node(name) -> LSTMLaneNode`; `mlp_lane_sklearn_node(name) -> SkMLPLaneNode`; `mlp_lane_torch_node(name) -> TorchMLPLaneNode`; `dlinear_node(name) -> DLinearNode`
- **imports:** __future__, core.node_protocol, numpy

## `run_active.py`
_run_active.py — P3.8: PER-INPUT ACTIVE SUBNETWORK + sigma.js dashboard state._
- **functions:** `_experts()`; `_split(X, y, frac, seed)`; `_communities(coact) -> list[int]`; `main() -> dict`
- **imports:** __future__, data.benchmarks, eval.golden, json, nodes, nodes.gated_node, numpy, os, random, time

## `run_advintel.py`
_run_advintel.py — Trading Phase T8 (DEFERRED) Advanced-Intelligence offline demo._
- **functions:** `_hdr(title) -> None`; `_to_jsonable(obj)`; `_seeded_returns(n, seed) -> pd.DataFrame`; `_stress_positions() -> list`; `_stub_fiidii_fetcher()`; `_stub_announcements_fetcher()`; `_stub_onchain_fetcher(kind) -> dict`; `_stub_liquidations_fetcher(symbol) -> dict`; `_stub_price_source(exchange, symbol) -> dict`; `_stub_funding_source(exchange, symbol) -> float`; `_stub_searcher(query) -> list`; `_stub_summarizer(prompt) -> str`; `_exit_trajectories() -> list`; `build_demo_advintel() -> dict`; `main() -> int`
- **imports:** __future__, json, numpy, pandas, sys, trading.advintel.arbitrage, trading.advintel.fii_dii, trading.advintel.liquidations, trading.advintel.nse_announcements, trading.advintel.onchain, trading.advintel.portfolio_risk, trading.advintel.stress, trading.brain.researcher, trading.brain.rl_exit, warnings

## `run_alerts_t7.py`
_run_alerts_t7.py — Trading Phase T7 (Alerts + Automation, Telegram-only) offline demo._
- **classes:** _FakeTransport
- **functions:** `_hdr(title) -> None`; `build_demo_dispatcher() -> AlertDispatcher`; `_demo_positions() -> list`; `_demo_pnl() -> dict`; `_demo_kill(reason) -> dict`; `_live_message() -> int`; `main(argv) -> int`
- **imports:** __future__, datetime, json, sys, trading.alerts

## `run_brain.py`
_run_brain.py — Step 1: let the brain GROW the network from a candidate pool._
- **functions:** `_split3(X, y, a, b)`; `_split3_shuffled(X, y, seed)`; `_split4(X, y, a, b, c)`; `_split4_shuffled(X, y, seed)`; `main(benchmark) -> dict`
- **imports:** __future__, core, core.brain, data.benchmarks, eval.golden, json, nodes.pool, os, random, sys, time

## `run_brain_agent.py`
_run_brain_agent.py — Phase P4.1 (Talk to the brain) OFFLINE demo._
- **functions:** `_build_demo_brain() -> KnowledgeBrain`; `_stub_llm(messages) -> str`; `build_demo_brain_agent() -> dict`; `main() -> int`
- **imports:** __future__, core.brain_agent, json, memory.brain, sys, warnings

## `run_brain_t8.py`
_run_brain_t8.py — Trading Phase T8.4 (Episodic Experience Bank + Semantic Memory) offline demo._
- **functions:** `_hdr(title) -> None`; `build_extra_trades() -> list`; `_build_bank(use_lancedb, uri) -> ExperienceBank`; `build_demo_experience() -> dict`; `_learnable_stream(n, rng) -> list`; `_concept_flip_stream(n, rng) -> list`; `_trim_curve(curve, k) -> list`; `build_demo_selfeval() -> dict`; `_synthetic_ohlcv(seed) -> pd.DataFrame`; `_picking_training_set(seed)`; `_demo_universe(seed) -> dict`; `_to_jsonable(obj)`; `build_demo_brain_t86() -> dict`; `build_demo_news_items() -> list`; `build_demo_news() -> dict`; `_entryexit_fitness(params) -> float`; `_det_clock()`; `_build_skill_library() -> tuple`; `build_demo_skills() -> dict`; `_pipeline_ohlcv(seed) -> pd.DataFrame`; `_pipeline_news_items(news_symbol) -> list`; `_new_safety() -> tuple`; `_build_pipeline(market) -> BrainTradingPipeline`; `build_demo_pipeline() -> dict`; `main() -> int`
- **imports:** __future__, json, numpy, pandas, run_journal_t5, sys, tempfile, trading.alerts, trading.alerts.config, trading.brain.continual, trading.brain.entryexit, trading.brain.experience, trading.brain.metalearn, trading.brain.news, trading.brain.observability, trading.brain.patterns, trading.brain.picking, trading.brain.pipeline, trading.brain.regime, trading.brain.selfeval, trading.brain.selfimprove, trading.brain.semantic, trading.brain.sentiment, trading.brain.skills, trading.execution, trading.journal, trading.strategy, warnings

## `run_chaos_compare.py`
_Step 3 evidence: do chaos-feature nodes hold accuracy better under noise?_
- **functions:** `main() -> dict`
- **imports:** __future__, data.benchmarks, data.dataset, eval.golden, nodes.chaos_nodes, nodes.phase2_nodes

## `run_columns.py`
_run_columns.py — render the COLUMN NETWORK (A→B→C→D) into state.json._
- **functions:** `_pool()`; `_split(X, y, frac, seed)`; `main() -> dict`; `_node_json(name, kind, head, summary, metrics, upstream, task)`; `full_render() -> dict`
- **imports:** __future__, core, core.columns, data.benchmarks, eval.golden, json, nodes, nodes.column_network, nodes.gated_node, numpy, os, random, time

## `run_crypto.py`
_run_crypto.py — train the prediction-graph network on REAL crypto data._
- **functions:** `main(coin, days) -> dict`
- **imports:** __future__, core, data.dataset, eval.golden, json, nodes.base_learners, nodes.phase2_nodes, nodes.stacking_node, os, time

## `run_crypto_trading.py`
_run_crypto_trading.py — Trading Phase T2 (Crypto) smoke test + status._
- **functions:** `_hdr(t) -> None`; `main() -> int`
- **imports:** __future__, argparse, json, sys, time, trading.crypto.config, trading.crypto.session

## `run_dev.py`
_run_dev.py — train the growing network on a synthetic benchmark (default data)._
- **functions:** `noise_sweep(levels) -> list[dict]`; `main(benchmark) -> dict`
- **imports:** __future__, core, data.benchmarks, data.dataset, eval.golden, json, nodes.base_learners, nodes.phase2_nodes, nodes.phase2b_nodes, nodes.router_node, nodes.stacking_node, os, sys, time

## `run_embodiment_p48.py`
_run_embodiment_p48.py — Phase P4.8 (Multimodal + identity + society + affect) demo._
- **functions:** `build_demo_embodiment() -> dict`; `demo_snapshot() -> dict`; `main() -> None`
- **imports:** __future__, cognition.embodiment, json, os, tempfile, warnings

## `run_full_network.py`
_run_full_network.py — THE FULL trainable network over the ENTIRE node catalog._
- **functions:** `_head_graph(ss, Xte, yte, head_name, head_value, comm_base) -> dict`; `main() -> dict`
- **imports:** __future__, data.benchmarks, eval.golden, json, nodes.structure_search, numpy, os, run_active, run_multi, time

## `run_human_memory.py`
_run_human_memory.py — Phase P4.2 (Human-like memory) OFFLINE demo._
- **classes:** _StubMem, _StubBrain
- **functions:** `_build() -> HumanMemory`; `build_demo_human_memory() -> dict`; `main() -> int`
- **imports:** __future__, json, memory.human_memory, sys, warnings

## `run_hybrid_memory.py`
_run_hybrid_memory.py — Phase P4.2 Hybrid human memory OFFLINE demo._
- **classes:** _StubMem, _StubBrain, _StubLLM
- **functions:** `_build() -> HybridMemory`; `build_demo_hybrid_memory() -> dict`; `main() -> int`
- **imports:** __future__, datetime, json, memory.hybrid_memory, sys, warnings

## `run_intradaywf.py`
_Walk-forward (chronological) on Binance INTRADAY klines — more samples/structure._
- **functions:** `eval_symbol(symbol, interval, target)`; `main(target, interval, total) -> dict`
- **imports:** __future__, core.brain, data.binance, eval.golden, json, nodes.pool, os, run_realwf, sys

## `run_journal_t5.py`
_run_journal_t5.py — Trading Phase T5 (Brain Confidence + Trade Journal) offline demo + status._
- **functions:** `_hdr(title) -> None`; `build_demo_journal() -> TradeJournal`; `_print_trade(t) -> None`; `main() -> int`
- **imports:** __future__, json, os, sys, tempfile, trading.journal, trading.journal.behavior, trading.journal.tearsheet

## `run_knowledge.py`
_Phase 4 demo: build the knowledge brain, ingest docs, and recall._
- **functions:** `_wiki(title) -> str | None`; `main() -> dict`
- **imports:** __future__, json, memory.brain, os, urllib.request

## `run_librarian.py`
_run_librarian.py — Phase P4.3 (Self-feeding internet) OFFLINE demo._
- **classes:** _StubMem, _StubBrain
- **functions:** `_stub_web_search(query, max_results) -> list[dict]`; `_stub_arxiv_search(query, max_results) -> list[dict]`; `_stub_extractor(url) -> str`; `build_demo_librarian() -> dict`; `main() -> int`
- **imports:** __future__, json, memory.librarian, sys, warnings

## `run_multi.py`
_run_multi.py — the MULTI-OUTPUT network: an output layer of several heads._
- **classes:** _MetaView
- **functions:** `_load_dotenv() -> None`; `cls_pool()`; `reg_pool()`; `domain_pool()`; `_combine(outputs, task)`; `_load_synthetic(benchmark, n)`; `_load_crypto(train_frac)`; `_split_dataset(ds, cap, train_frac)`; `_load_external(source)`; `_load_panel(source, cap, train_frac)`; `main(arg, n, pool) -> dict`
- **imports:** __future__, core, core.heads, data.benchmarks, eval.golden, json, nodes, numpy, os, sys, time, warnings

## `run_network.py`
_run_network.py — CORTEX B7: unified network-state generator → network_state.json._
- **functions:** `_split(X, y, frac, seed)`; `_split_chrono(X, y, frac)`; `_pair_block(path, n_rows, tf_min, horizon_bars) -> dict | None`; `_real_dataset_multi(rows_per_pair, max_pairs, tf_min, horizon_bars) -> dict`; `_real_dataset(n_rows, tf_min, horizon_bars) -> dict`; `_deep_lane_factories() -> list[tuple]`; `_trust_ledger()`; `main() -> dict`
- **imports:** __future__, argparse, collections, core.columns, core.segments, data.benchmarks, eval.golden, json, nodes.active_subnet, nodes.reflex, numpy, os, random, run_columns, time

## `run_noise_router.py`
_(ii) Demonstrate the noise-regime router beating either single expert._
- **functions:** `_split(X, y, reg, frac, seed)`; `_by_regime(pred, y, reg)`; `main() -> dict`
- **imports:** __future__, core, data.benchmarks, eval.golden, json, nodes.base_learners, nodes.chaos_nodes, nodes.noise_router, nodes.phase2_nodes, os, random, time

## `run_online.py`
_run_online.py — Trading Phase ONLINE (O1–O5) OFFLINE demo._
- **classes:** _StubCryptoPrice
- **functions:** `_hdr(title) -> None`; `_seeded_nse_ohlcv(seed, n) -> pd.DataFrame`; `_decide_fn(market, symbol, window_or_price) -> dict`; `build_supervisor() -> OnlineSupervisor`; `build_demo_online() -> dict`; `main() -> int`
- **imports:** __future__, datetime, json, numpy, pandas, sys, trading.online, trading.online.session, trading.online.supervisor

## `run_options_t4.py`
_run_options_t4.py — Trading Phase T4 (Options Intelligence) offline demo + status._
- **functions:** `_hdr(title) -> None`; `build_demo_chain() -> OptionsChain`; `_seed_iv_history(chain) -> IVHistory`; `main() -> int`
- **imports:** __future__, json, math, sys, trading.options.chain, trading.options.greeks, trading.options.iv

## `run_oss.py`
_run_oss.py — train the REUSE-FIRST (OSS-backed) node layer and emit state.json._
- **functions:** `main(benchmark, with_autogluon) -> dict`
- **imports:** __future__, core, data.benchmarks, data.dataset, eval.golden, json, nodes, nodes.stacking_node, numpy, os, sys, time, warnings

## `run_phase1.py`
_run_phase1.py — train the Phase-1 prediction-graph network and emit state.json._
- **functions:** `main() -> dict`
- **imports:** __future__, core, eval.golden, json, nodes.base_learners, nodes.stacking_node, os, time

## `run_phase3.py`
_run_phase3.py — the LEARNED-ROUTING frontier (Phase 3), validated honestly._
- **functions:** `_experts() -> tuple[list, list]`; `_split(X, y, frac, seed)`; `_naive(y) -> float`; `_combiners(factories, names, Xtr, ytr, Xte, yte, regime_aware, full)`; `_best_router(res) -> tuple[str, float]`; `_synthetic_headline(factories, names)`; `_noise_sweep(factories, names, levels)`; `_multiseed(factories, names, seeds)`; `_crypto(factories, names)`; `_register_dashboard(hell, names, Xte, yte, headline)`; `main() -> dict`
- **imports:** __future__, core, data.benchmarks, eval.golden, json, nodes, nodes.cascade_node, nodes.dynamic_bus, nodes.gated_node, nodes.router_node, nodes.routing_advanced, nodes.stacking_node, nodes.structure_search, os, random, time

## `run_real.py`
_Run the grown + routed + guarded brain on REAL multi-asset crypto data._
- **functions:** `main(days) -> dict`
- **imports:** __future__, core, core.brain, data.dataset, eval.golden, json, nodes.pool, os, run_brain, time

## `run_realwf.py`
_Walk-forward (chronological) evaluation on real crypto — the HONEST protocol._
- **functions:** `chrono_folds(n, n_folds, init)`; `_split_history(Xh, yh, vfrac, gfrac)`; `eval_coin(coin, target)`; `main(coins, target) -> dict`
- **imports:** __future__, core.brain, data.dataset, eval.golden, json, nodes.pool, os

## `run_robust.py`
_Harden: multi-seed robustness of the router-grown brain._
- **functions:** `_one(seed) -> dict`; `main(seeds) -> dict`
- **imports:** __future__, core.brain, data.benchmarks, eval.golden, json, nodes.pool, os, run_brain

## `run_self_coding_p47.py`
_run_self_coding_p47.py — Phase P4.7 (Autonomy + self-coding) OFFLINE demo._
- **functions:** `build_demo_self_coding() -> dict`; `demo_snapshot() -> dict`; `main() -> None`
- **imports:** __future__, cognition.self_coding, json, warnings

## `run_self_quiz.py`
_run_self_quiz.py — Phase P4.4 Self-quiz mastery tracker OFFLINE demo._
- **classes:** _KnowBrain, _BlankBrain
- **functions:** `_silenced()`; `_run_curve(brain) -> tuple[list[dict], dict, MasteryQuiz]`; `build_demo_self_quiz() -> dict`; `main() -> int`
- **imports:** __future__, contextlib, datetime, json, memory.self_quiz, os, sys, warnings

## `run_strategy_library.py`
_run_strategy_library.py — run the curated institutional Strategy Library (active T8 feature)._
- **imports:** __future__, sys, trading.strategy.library.run

## `run_strategy_t8.py`
_run_strategy_t8.py — Trading Phase T8.1 (Strategy genome + operators + walk-forward_
- **functions:** `_hdr(title) -> None`; `synth_ohlcv(n, seed) -> pd.DataFrame`; `_oos_slice(feats) -> tuple[pd.DataFrame, list[dict]]`; `_score(strategy, oos_feats) -> dict`; `_load_markets() -> dict`; `_fold_returns(strategy, market_data, n_folds) -> list[float]`; `build_demo_population() -> dict`; `build_demo_evolution() -> dict`; `_rank_key(m) -> tuple`; `_fmt_metrics(m) -> str`; `_fmt_fitness(p) -> str`; `main() -> int`
- **imports:** __future__, json, numpy, pandas, sys, trading.strategy, warnings

## `run_stream_of_mind.py`
_run_stream_of_mind.py — Phase P4.6 (Stream-of-Mind + observability) OFFLINE demo._
- **classes:** _DemoBrain
- **functions:** `_abstainer()`; `_build() -> tuple`; `build_demo_thinking() -> dict`; `demo_snapshot() -> dict`; `live_stream(query)`; `main() -> None`
- **imports:** __future__, cognition, cognition.stream_of_mind, json, warnings

## `run_thinking_p45.py`
_run_thinking_p45.py — Phase P4.5 (Thinking + knowing-what-it-knows) OFFLINE demo._
- **classes:** _Graph, _DemoBrain
- **functions:** `_calibrated_abstainer() -> CalibratedAbstainer`; `_causal_demo() -> dict`; `build_demo_thinking() -> dict`; `demo_snapshot() -> dict`; `main() -> None`
- **imports:** __future__, cognition, cognition.reasoning, json, numpy, warnings

## `run_trading.py`
_run_trading.py — Trading Phase T1 (NSE) smoke test + status._
- **functions:** `_hdr(title) -> None`; `main() -> int`
- **imports:** __future__, argparse, json, sys, time, trading.config, trading.openalgo_client, trading.session

## `run_trading_t3.py`
_run_trading_t3.py — Trading Phase T3 (Trade Execution Engine) offline demo + status._
- **functions:** `_hdr(title) -> None`; `_demo_happy_path() -> ExecutionEngine`; `_demo_kill_switch() -> None`; `_demo_circuit_breaker() -> None`; `main() -> int`
- **imports:** __future__, json, sys, trading.execution

## `run_trainable.py`
_run_trainable.py — render the P3.5–3.7 TRAINABLE NETWORK on the dashboard._
- **functions:** `_experts()`; `_split(X, y, frac, seed)`; `main() -> dict`
- **imports:** __future__, core, data.benchmarks, eval.golden, json, nodes, nodes.cascade_node, nodes.dynamic_bus, nodes.gated_node, nodes.stacking_node, os, random, time

## `run_unified_router.py`
_(2) Fold regime-routing into the main learned_router._
- **functions:** `_split(X, y, reg, frac, seed)`; `_by_regime(pred, y, reg)`; `main() -> dict`
- **imports:** __future__, core, data.benchmarks, eval.golden, json, nodes.base_learners, nodes.chaos_nodes, nodes.phase2_nodes, nodes.phase2b_nodes, nodes.router_node, os, random, time

## `scratchpad/discover_aiselect.py`
_(no summary)_
- **imports:** asyncio, json, playwright.async_api

## `scratchpad/qa_binance_panel.py`
_(no summary)_
- **imports:** pathlib, playwright.sync_api

## `scratchpad/qa_handoff_panel.py`
_Targeted render QA: does the Human Handoff panel land in the Trading view?_
- **imports:** os, pathlib, playwright.sync_api, sys

## `scratchpad/relaunch_funnel.py`
_Restart the crypto funnel loop with its EXACT current env (captured from /proc), so the_
- **functions:** `find_pid()`
- **imports:** os, signal, subprocess, sys, time

## `scratchpad/verify_llm_creds.py`
_Verify each configured cloud LLM credential in isolation via the core/llm.py chain._
- **functions:** `_err_class(e) -> str`; `probe(cands, kind)`
- **imports:** core, json, litellm, os, sys, time

## `tests/__init__.py`
_Test package init._
- **imports:** os

## `tests/test_account_watchlist.py`
_Tests for the Brain-Open account-watchlist sync + human-UI JSON parsing (pure logic)._
- **classes:** TestPlanSync, TestVisionJsonParse, TestBinanceFavoritesMirror
- **imports:** trading.brain.vision.human_ui, trading.broker_sense.account_watchlist, unittest

## `tests/test_advintel.py`
_Trading Phase T8 (Advanced Intelligence) acceptance tests — fully offline._
- **classes:** TestPortfolioRisk, TestStress, TestFiiDii, TestNseAnnouncements, TestOnChain, TestLiquidations, TestArbitrage
- **functions:** `_seeded_returns(n, k) -> pd.DataFrame`
- **imports:** __future__, json, numpy, pandas, trading.advintel.arbitrage, trading.advintel.fii_dii, trading.advintel.liquidations, trading.advintel.nse_announcements, trading.advintel.onchain, trading.advintel.portfolio_risk, trading.advintel.stress, unittest, warnings

## `tests/test_alerts_t7.py`
_Trading Phase T7 (Telegram Alerts & Automation) acceptance tests — fully offline._
- **classes:** _RecordingTransport, TestEvents, TestDedup, TestConfig, TestFormatter, TestChannel, TestDispatcher, TestCommands, TestScheduler
- **functions:** `_disabled_config() -> AlertConfig`; `_enabled_config() -> AlertConfig`; `_utc(y, mo, d, h, mi) -> float`
- **imports:** __future__, datetime, trading.alerts.channels, trading.alerts.commands, trading.alerts.config, trading.alerts.dedup, trading.alerts.dispatcher, trading.alerts.events, trading.alerts.formatter, trading.alerts.scheduler, unittest

## `tests/test_antioverfit_p20.py`
_Pillar 20 — anti-overfitting backbone: CPCV, meta-labeling, and the mandatory_
- **classes:** TestCPCV, TestMetaLabel, TestFoundryGate
- **imports:** numpy, os, pandas, tempfile, unittest

## `tests/test_app_school.py`
_Tests for the App Driving School (trading/broker_sense/app_school) — offline, no browser._
- **classes:** _IsolatedState, TestAppMap, TestRouteTo, TestRanking, _FakePage, _FakeCortex, _FakeRegistry, _FakeRecorder, TestExplore, TestFastMovers, TestAccountScreenWiring
- **imports:** __future__, pathlib, tempfile, trading.broker_sense, trading.state, unittest

## `tests/test_associative_memory.py`
_Tests for memory/associative.py — HippoRAG PPR recall + A-MEM evolution (offline path)._
- **functions:** `_seed(mem)`; `test_add_links_related_notes()`; `test_recall_is_associative_multihop()`; `test_persistence_across_instances(tmp_path)`; `test_llm_path_used_when_available()`
- **imports:** json, memory.associative

## `tests/test_attribution_fast_path.py`
_tests/test_attribution_fast_path.py — the hot-path attribution must be cheap._
- **classes:** _CountingNet, TestAttributionFastPath
- **imports:** trading.brain, unittest

## `tests/test_autoload.py`
_Node auto-loader (nodes/autoload.py) — pkgutil sweep recovers built-but-unpooled families._
- **classes:** TestAutoload
- **imports:** core.node_protocol, nodes, unittest

## `tests/test_autoresearch.py`
_Tests for trading/strategy/autoresearch.py — the live autoresearch driver (#5)._
- **classes:** _IsolatedState, TestRunCycle, TestStatus, TestUiDataSnapshot
- **functions:** `_rows(n, base)`
- **imports:** __future__, os, pathlib, tempfile, time, trading.state, unittest

## `tests/test_binance_ai_select.py`
_tests/test_binance_ai_select.py — Binance built-in AI Select recommendations._
- **classes:** TestAISelect
- **functions:** `_fake(url)`
- **imports:** trading.broker_sense, unittest

## `tests/test_binance_catalysts.py`
_tests/test_binance_catalysts.py — Binance-native listing catalysts._
- **classes:** TestCatalysts
- **imports:** pathlib, tempfile, time, trading.broker_sense, trading.broker_sense.binance_stream, unittest

## `tests/test_binance_options.py`
_tests/test_binance_options.py — Binance options IV/skew regime gauge._
- **classes:** TestOptions
- **imports:** trading.broker_sense, unittest

## `tests/test_binance_orderflow.py`
_tests/test_binance_orderflow.py — Binance-computed order-flow feature pack._
- **classes:** TestOrderFlow
- **functions:** `_fake_rest(url)`
- **imports:** time, trading.broker_sense, trading.broker_sense.binance_stream, unittest

## `tests/test_binance_sectors.py`
_tests/test_binance_sectors.py — Binance-native sector taxonomy + rotation._
- **classes:** TestSectors
- **imports:** time, trading.broker_sense, trading.broker_sense.binance_stream, unittest

## `tests/test_binance_stream.py`
_tests/test_binance_stream.py — Binance all-market in-RAM mirror._
- **classes:** TestBinanceMirror, TestScreenerMirrorMigration
- **functions:** `_mark_frame(rows)`; `_ticker_frame(rows)`; `_liq_frame(sym, side, qty, price, ts_ms)`
- **imports:** time, trading.broker_sense.binance_stream, unittest

## `tests/test_boss_command.py`
_Boss command engine (trading/brain/boss.py) + mind-event bus (mind_events.py) + R&D drive_
- **classes:** _IsolatedState, TestMindEvents, TestDeterministicParser, TestDirectivesAndPolicy, TestRnd, TestChatRouting
- **imports:** pathlib, tempfile, trading.state, unittest

## `tests/test_brain_agent.py`
_Phase P4.1 (LangGraph Brain Agent) acceptance tests — fully OFFLINE + deterministic._
- **classes:** StubBrain, RecorderChat, TestLLMPath, TestHistory, TestOfflineFallback, TestRecallK, TestStatus, TestDeterminism
- **functions:** `_agent(brain, llm_chat, recall_k, force_no_llm)`
- **imports:** __future__, core.brain_agent, json, unittest, warnings

## `tests/test_brain_engines_t8.py`
_Trading Phase T8 (Brain engines, deferred A2/A3) acceptance tests — fully offline._
- **classes:** TestAutonomousResearcher, TestQLearningExit
- **functions:** `_stub_searcher(query)`; `_stub_summarizer(prompt)`; `_raising_summarizer(prompt)`; `_empty_summarizer(prompt)`; `_trajectories()`
- **imports:** __future__, json, trading.brain.researcher, trading.brain.rl_exit, unittest, warnings

## `tests/test_brain_forcing.py`
_Forcing tests for brain paths the audit (2026-07-03) found under-exercised._
- **functions:** `test_file_memory_recall_keyword_fallback(tmp_path)`; `_planted_trades(n, seed) -> list[dict]`; `test_gui_agent_experiment_runs_hypothesis_cycle()`; `test_knowledge_brain_recall_without_embeddings()`; `test_online_node_drift_then_replay_retrain_adapts()`; `test_c_inference_kernel_available()`; `test_knowledge_brain_persists_across_instances(monkeypatch, tmp_path)`
- **imports:** numpy, pathlib, pytest, tempfile, trading.state

## `tests/test_brain_segment_cycles.py`
_Unit tests for BrainExecutor's options/prediction segment cycles (audit gap 4)._
- **classes:** FakeClient, FakeDecider, TestOptionParse, TestOptionsCycle, TestPredictionCycle, TestPerSegmentMaxOpenTrades
- **functions:** `_candles(closes)`
- **imports:** trading.crypto.freqtrade.brain_executor, unittest

## `tests/test_broker_features.py`
_Tests for the broker built-in-feature exploitation subsystem (trading/broker_sense/broker_features)._
- **classes:** _Isolated, TestCatalog, TestFusion, TestPerfStacking, TestNewEntry, TestPresetInvention, TestWatchlistGated
- **imports:** __future__, pathlib, tempfile, trading.state, unittest

## `tests/test_broker_login.py`
_Tests for the broker login flow (trading/broker_sense/sessions) — multi-step aware, offline._
- **classes:** _IsolatedState, _El, _FakeBinance, TestLoginDetection, TestChallengeDetection, TestClickLoginSelectivity, TestChallengeNoFalsePositive, TestMultiStepLogin
- **imports:** __future__, pathlib, tempfile, trading.broker_sense, trading.state, unittest

## `tests/test_broker_sense.py`
_Tests for the Broker-Sense Funnel (trading/broker_sense) — offline, STATE_DIR-isolated._
- **classes:** _IsolatedState, TestBrokerRoles, TestVaultMerge, TestWatchlist, TestLearningColumns, TestChartVision, TestBookMonitor, TestExecAdapter, TestFunnelCycle, TestCnnModel, TestOtpBoxDetection, TestWedgeRegressions, TestExecutorPerSegment
- **imports:** __future__, os, pathlib, tempfile, time, trading.state, unittest

## `tests/test_calibration_truth.py`
_tests/test_calibration_truth.py — calibration honesty + error-driven learning (2026-07-10)._
- **functions:** `_trade(symbol, net_pnl, conf)`; `test_zero_and_negative_confidence_are_missing_not_perfect()`; `test_ece_and_reliability_from_real_pairs()`; `test_no_forecasts_means_null_not_fake(monkeypatch)`; `test_mistake_topics_from_loss_clusters(monkeypatch, tmp_path)`; `test_small_or_winning_groups_do_not_trigger(monkeypatch, tmp_path)`
- **imports:** __future__, json, trading.journal.confidence, types

## `tests/test_candle_updater.py`
_candle_updater throttle — batched, de-prioritised OHLCV refresh._
- **classes:** TestCandleUpdaterThrottle
- **imports:** __future__, trading.crypto.freqtrade.candle_updater, unittest, warnings

## `tests/test_challenger.py`
_tests/test_challenger.py — TradeOutcomeNet champion/challenger duel (2026-07-10)._
- **functions:** `_xy(n, seed)`; `test_oof_eval_protocol_scores_learnable_signal()`; `test_duel_honest_when_too_few_rows(monkeypatch, tmp_path)`; `test_tabpfn_fit_predict_shapes()`; `test_engine_flag_promotes_tabpfn(monkeypatch)`
- **imports:** __future__, numpy, os, pytest, trading.brain.challenger

## `tests/test_champion_bandit.py`
_Tests for invent-beyond #3 — regime-contextual champion bandit allocator + its wiring._
- **classes:** _StateSandbox, TestChampionBandit, TestCloseLearnOnce
- **imports:** __future__, pathlib, tempfile, trading.state, unittest

## `tests/test_champion_lineage.py`
_W5 champion lineage + leak tripwire tests — isolated STATE_DIR._
- **classes:** ChampionLineageTest
- **imports:** pathlib, tempfile, unittest

## `tests/test_chart_render.py`
_Tests for trading/broker_sense/chart_render.py + chart_vision vision-escalation wiring._
- **classes:** TestPlain, TestAnnotated, TestVisionEscalate
- **functions:** `_rows(n)`
- **imports:** __future__, math, os, trading.broker_sense, unittest

## `tests/test_chart_vlm.py`
_Tests for trading/broker_sense/chart_vlm.py — Lane B VLM chart reader._
- **classes:** TestParse, TestNorm, TestReadChart, TestNode
- **imports:** __future__, trading.broker_sense, unittest

## `tests/test_chart_yolo.py`
_Tests for trading/broker_sense/chart_yolo.py — Lane C YOLOv8 pattern detection._
- **classes:** _Boxes, _Arr, _Result, TestDetect, TestCache, TestNode
- **functions:** `_fake_model(cls, conf)`
- **imports:** __future__, pathlib, tempfile, time, trading, trading.broker_sense, unittest

## `tests/test_chat.py`
_P4.1 acceptance tests: the brain-chat plumbing is well-formed and degrades gracefully._
- **classes:** TestChat
- **imports:** __future__, core, os, unittest

## `tests/test_columns.py`
_Column-architecture acceptance tests (A → B → C → D + dynamic brain I/O)._
- **classes:** TestColumnTaxonomy, TestColumnA, TestColumnNetworkB, TestColumnNetworkC, TestColumnNetworkD, TestDynamicBrainOutputs
- **functions:** `_pool(want)`; `_reg_factories()`; `_reg_names()`; `_split(X, y, frac, seed)`; `_naive(y)`
- **imports:** __future__, core.columns, core.heads, core.node_protocol, data.benchmarks, eval.golden, nodes, nodes.column_network, nodes.column_node, os, unittest

## `tests/test_computer_use.py`
_tests/test_computer_use.py — the brain's computer-use / GUI agent (trading/brain/gui)._
- **functions:** `isolated_state(tmp_path, monkeypatch)`; `test_default_targets_are_own_and_freqtrade(isolated_state)`; `test_html_controls_parse()`; `test_chart_reader_reads_trend()`; `test_dry_run_plans_without_firing(isolated_state)`; `test_live_affecting_refused_unless_armed(isolated_state)`; `test_skill_retrieval_and_success_compounding(isolated_state)`; `test_reflector_distils_and_recalls(isolated_state)`; `test_agent_step_and_practice(isolated_state)`; `test_agent_aborts_into_halted_market(isolated_state, monkeypatch)`; `test_node_conforms_and_registers(isolated_state)`
- **imports:** __future__, core.node_protocol, pytest

## `tests/test_concept_discovery.py`
_Concept Discovery Engine (trading/brain/discovery/) — pure-self feature invention._
- **classes:** TestConceptDiscovery
- **functions:** `_ohlcv(n, seed)`
- **imports:** __future__, numpy, os, tempfile, unittest, warnings

## `tests/test_continual_learning.py`
_Tests for Phase E — Avalanche ContinualLearner + world-model continual update._
- **functions:** `_regime(seed, w, n)`; `test_learns_sequential_regimes_without_forgetting()`; `_ohlcv(seed, n, drift)`; `test_worldmodel_updates_online_with_replay()`
- **imports:** numpy, pandas, pytest, trading.brain.continual, trading.brain.worldmodel

## `tests/test_continual_t8.py`
_Trading Phase T8.5 (Continual Learning + Auto-Quiz + Meta-Init + Reflexion) tests._
- **classes:** TestOnlineNode, TestReplayBuffer, TestReplayRetrain, TestAutoQuiz, TestMetaLearner, TestReflexion
- **functions:** `learnable_stream(n, seed)`; `unlearnable_stream(n, seed)`; `_xy(samples)`
- **imports:** __future__, core.node_protocol, json, numpy, trading.brain.continual, trading.brain.metalearn, trading.brain.selfeval, trading.brain.semantic, trading.journal.schema, unittest, warnings

## `tests/test_cortex_b1.py`
_CORTEX B1 (Foundations) acceptance tests — segments + labels + fitness._
- **classes:** TestSegmentTaxonomy, TestBarrierLabels, TestFitnessEngine
- **functions:** `_trending_market(n_cycles, up_len, dn_len, up, dn)`
- **imports:** __future__, core.segments, numpy, pandas, trading.fitness, trading.labels, unittest

## `tests/test_cortex_b2.py`
_CORTEX B2 tests — video lanes, scratch core, risk overlay, rollout, TA._
- **classes:** TestBuildWindows, TestVideoLanes, TestScratchCore, TestRiskOverlay, TestRollout, TestFeaturesTA
- **functions:** `_sine_data(n, f, seed)`
- **imports:** __future__, core.node_protocol, numpy, unittest

## `tests/test_cortex_b3.py`
_CORTEX B3 acceptance tests — reflex arc + hierarchical gates + trust._
- **classes:** TestTrustLedger, TestGatePriorBias, TestHierarchicalGateNode, TestReflexArc
- **functions:** `_pool(want)`; `_split(X, y, frac, seed)`; `_naive(y)`; `_fresh_path(name)`; `_gate_problem(seed, n, d)`; `_easy_data(n, seed)`; `_xor_data(n, seed)`; `_noise_data(n, seed)`
- **imports:** __future__, core.trust, data.benchmarks, nodes, nodes.active_subnet, nodes.gated_node, nodes.reflex, numpy, os, random, tempfile, unittest

## `tests/test_cortex_b4.py`
_CORTEX B4 acceptance tests — brain hub meta-controller._
- **classes:** TestDFABroadcaster, TestJumpRegime, TestDriftSentry, TestChampionManager, TestBrainHub
- **functions:** `_trust_path(name) -> str`
- **imports:** __future__, numpy, os, tempfile, trading.brain, trading.brain.regime_hub, unittest, vendor.dfa

## `tests/test_cortex_b5.py`
_CORTEX B5 acceptance tests — evolution lane + SimLab._
- **classes:** TestSignals, TestZeroCostTriage, TestNeatLane, TestReinforceEdgeLearner, TestGrowPruneController, TestSimLab
- **functions:** `_sim_close(seed, n)`
- **imports:** __future__, nodes.neat_lane, numpy, trading.simlab, unittest

## `tests/test_cortex_b6.py`
_CORTEX B6 acceptance tests — forecast heads + data downloaders._
- **classes:** TestRolloutHead, TestEvaluateHead, TestBuildFoundationHeads, TestDownloads
- **functions:** `_windows(series, L, k, n)`
- **imports:** __future__, data, io, numpy, trading.heads, unittest

## `tests/test_cortex_b7.py`
_CORTEX B7 tests — run_network.py generator + /api/network/* server helpers._
- **classes:** TestRunNetwork, TestServerHelpers
- **functions:** `_load_server()`
- **imports:** importlib.util, json, os, subprocess, sys, tempfile, unittest

## `tests/test_cortex_b8.py`
_CORTEX B8 acceptance tests — final integration (CANON-51/42)._
- **classes:** TestCortexSignalSource, _StubDecider, TestShadowMode, TestValidationHoldout, TestTrustFeedback
- **functions:** `_ohlcv(n, seed, trend)`
- **imports:** __future__, json, numpy, os, pandas, pathlib, tempfile, trading, trading.state, unittest

## `tests/test_cortex_b9_gaps.py`
_CORTEX B9 — the 13 PARTIAL→FULL canon gap-closers._
- **classes:** TestGapMap, TestPatternLevels, TestOneHot, TestArbitrate, TestClassificationEval, TestSweep, TestAntiOverfit, TestSelectiveAccuracy, TestFeatureBus, TestDownloadersImportable, TestNSEPractice
- **imports:** numpy, os, pandas, tempfile, unittest

## `tests/test_created_strategies.py`
_tests/test_created_strategies.py — the strategy-creator loop is closed._
- **functions:** `isolated_state(tmp_path, monkeypatch)`; `_admit_one_genome(seed, metric) -> str`; `_full_feature_df(n) -> pd.DataFrame`; `test_created_strategy_wrapped_and_executable(isolated_state)`; `test_created_reaches_registry_and_executor(isolated_state)`; `test_signal_is_feature_guarded(isolated_state)`; `test_registry_auto_refreshes_on_store_change(isolated_state)`; `test_min_metric_gate(isolated_state)`
- **imports:** __future__, numpy, pandas, pytest, trading.strategy.features

## `tests/test_credential_chat.py`
_Tests for capturing a credential answer typed into Brain Chat (trading/brain/credential_chat)._
- **classes:** _IsolatedState, TestCapture, TestChatRouting
- **imports:** __future__, pathlib, tempfile, trading.state, unittest

## `tests/test_credential_requests.py`
_Tests for the credential-request → Brain Chat flow (cross-process) + proactive login ask._
- **classes:** _IsolatedState, TestCrossProcessPending, TestProactiveAsk
- **imports:** __future__, pathlib, tempfile, time, trading.state, unittest

## `tests/test_crypto_t2.py`
_Trading Phase T2 (Crypto Foundation) acceptance tests — fully offline._
- **classes:** TestConfig, TestLiquidation, TestOrderBookFill, TestPaperEngine, TestFundingSpread, TestCryptoWatchlist
- **imports:** __future__, pathlib, tempfile, trading.crypto.config, trading.crypto.funding, trading.crypto.liquidation, trading.crypto.paper_engine, trading.crypto.watchlist, trading.state, unittest

## `tests/test_curiosity.py`
_Curiosity-driven feature discovery tests (invent-beyond #1) — isolated STATE_DIR._
- **classes:** CuriosityTest
- **imports:** pathlib, tempfile, time, unittest

## `tests/test_data_sources.py`
_Tests for the per-broker public↔account data-source switch (data_sources + screen_all gating)._
- **classes:** _IsolatedState, TestSwitch, TestScreenAllGating, TestAccountScreenRequiresLogin
- **imports:** __future__, pathlib, tempfile, trading.broker_sense, trading.state, unittest

## `tests/test_debate_verifier_p18.py`
_Pillar 18 — adversarial debate + verifier-guided reasoning. Deterministic via injected_
- **classes:** TestVerifier, TestDebateGate
- **functions:** `_yes_chat(msgs)`; `_no_chat(msgs)`
- **imports:** unittest

## `tests/test_decision_memory.py`
_Decision-memory subsystem (trading/brain/decision_memory.py + attribution.py) and the_
- **classes:** _IsolatedState, TestDecisionMemory, TestAttribution, TestFreqtradeIngestFixes
- **imports:** datetime, pathlib, tempfile, time, trading.state, unittest

## `tests/test_dir_exit.py`
_Tests for trading/direction/dir_exit — the directional EXIT oracle (Pillar 27)._
- **classes:** _Iso, TestRead, TestEvaluate
- **functions:** `_seed(buckets) -> None`; `_snap(votes)`
- **imports:** json, os, pathlib, tempfile, trading.state, unittest

## `tests/test_direction_equation.py`
_Tests for trading/strategy/direction_equation.py — P2 Rank-IC equation orchestrator._
- **classes:** TestForwardReturn, TestScoreEquation, TestDiscover, TestCpcvGate, TestPersist
- **functions:** `_trending_ohlcv(n, seed)`
- **imports:** __future__, numpy, pandas, pathlib, tempfile, trading, trading.strategy, trading.strategy.generators.expression, unittest

## `tests/test_direction_equation_deploy.py`
_Tests for trading/strategy/direction_equation_deploy.py — P4 live deploy._
- **classes:** DeployTest
- **functions:** `_rows(n, seed)`
- **imports:** __future__, numpy, pandas, pathlib, tempfile, trading, trading.strategy, unittest

## `tests/test_direction_regime.py`
_Tests for trading/direction/regime — D5 direction regime classifier._
- **classes:** _Iso, TestClassifyCloses, TestClassifyIO
- **imports:** math, pathlib, tempfile, time, trading.state, unittest

## `tests/test_discovery_signal.py`
_Live discovery signal + trade-decision integration (trading/brain/discovery/signal.py)._
- **classes:** TestLiveSignal, TestExecutorBlend
- **functions:** `_series(n, seed)`
- **imports:** __future__, numpy, time, types, unittest, warnings

## `tests/test_dl_nodes.py`
_DL-node acceptance tests: the darts neural forecasters, the PyTorch_
- **classes:** TestDartsForecastNodes, TestAutoencoderNode, TestTabPFNNode, TestPoolRegistration
- **functions:** `_data(n)`; `_split(X, y, frac)`; `_naive(y) -> float`; `_assert_protocol(tc, node, X)`
- **imports:** __future__, core.node_protocol, data.benchmarks, nodes, unittest

## `tests/test_domain_nodes.py`
_Acceptance test: the PhD-domain node modules import and conform to NodeProtocol._
- **classes:** TestDomainNodes
- **imports:** __future__, core.node_protocol, data.benchmarks, data.dataset, unittest

## `tests/test_dream_replay.py`
_tests/test_dream_replay.py — Dream-Trainer phase-2 worldmodel replay (2026-07-10)._
- **functions:** `_df(n, drift, seed)`; `test_imagine_replay_pre_entry_only(monkeypatch, tmp_path)`; `test_old_trades_skipped_never_replayed_on_future_data(monkeypatch, tmp_path)`
- **imports:** __future__, datetime, json, numpy, pandas

## `tests/test_dreamer.py`
_tests/test_dreamer.py — Counterfactual Dream-Trainer (2026-07-10)._
- **functions:** `_rows()`; `test_regret_decomposition(monkeypatch, tmp_path)`; `test_study_topics_follow_dominant_regret(monkeypatch, tmp_path)`; `test_rows_without_excursions_are_skipped_not_faked(monkeypatch, tmp_path)`
- **imports:** __future__, json

## `tests/test_embodiment_p48.py`
_Phase P4.8 (Multimodal + identity + society + affect) acceptance tests._
- **classes:** TestAffect, TestIdentity, TestSociety, TestSensesDegrade, TestEmbodiment, TestDemo
- **imports:** __future__, cognition.affect, cognition.embodiment, cognition.identity, cognition.society, os, tempfile, unittest, warnings

## `tests/test_entry_meta_cache.py`
_Regression: entry_meta.lookup must parse the sidecar file ONCE per file change._
- **classes:** EntryMetaCacheTest
- **imports:** __future__, pathlib, tempfile, trading.state, unittest

## `tests/test_evidence_lane.py`
_W3 evidence lane tests — isolated STATE_DIR, synthetic cycles._
- **classes:** EvidenceLaneTest
- **functions:** `_sig(direction, price)`
- **imports:** pathlib, tempfile, time, unittest

## `tests/test_evolve_t8.py`
_Trading Phase T8.3 (DEAP NSGA-II evolution loop + promotion) acceptance tests — offline._
- **classes:** TestEvolveRuns, TestEvolveDeterminism, TestPromotionNodeProtocol, TestRegistry
- **functions:** `_make_ohlcv(n, seed) -> pd.DataFrame`; `_run_evolve() -> EvolutionResult`
- **imports:** __future__, core.node_protocol, json, numpy, pandas, trading.strategy.control, trading.strategy.evolve, trading.strategy.features, trading.strategy.operators, trading.strategy.registry, unittest, warnings

## `tests/test_exchange_pool.py`
_Multi-venue market-data pool (trading/crypto/exchange_pool.py) — ban-proofing._
- **classes:** _FakeCcxt
- **functions:** `_pool(specs)`; `test_round_robin_spreads_calls()`; `test_failover_skips_broken_venue()`; `test_ban_error_triggers_long_cooldown_and_budget_is_hard()`; `test_transient_error_gets_short_backoff_only()`; `test_norm_appends_settle_for_swap()`; `test_all_venues_down_raises()`; `test_crypto_options_screener_drops_expiring_contracts()`
- **imports:** pathlib, tempfile, time, trading.crypto.exchange_pool, trading.state

## `tests/test_execution_t3.py`
_Trading Phase T3 (Trade Execution Engine) acceptance tests — fully offline._
- **classes:** TestOrderState, TestMAEMFE, TestTrailing, TestProfitBooking, TestCircuitBreaker, TestMargin, TestBracketCover, TestKillSwitch, TestExecutionEngine
- **imports:** __future__, trading.execution.bracket, trading.execution.circuit_breaker, trading.execution.engine, trading.execution.kill_switch, trading.execution.mae_mfe, trading.execution.margin, trading.execution.order_state, trading.execution.profit_booking, trading.execution.trailing, unittest

## `tests/test_experience_t8.py`
_Trading Phase T8.4 (episodic experience bank + semantic memory) acceptance tests._
- **classes:** TestTradeVector, TestExperienceBankMemory, TestCBRDiscrimination, TestRecallSerialisation, TestFromJournal, TestLanceDBPath, TestSemanticMemory
- **functions:** `_trade() -> ClosedTrade`; `_long_low_vix_winner(i) -> ClosedTrade`; `_long_high_vix_loser(i) -> ClosedTrade`
- **imports:** __future__, json, tempfile, trading.brain.experience, trading.brain.semantic, trading.journal.journal, trading.journal.schema, unittest, warnings

## `tests/test_fast_candles.py`
_Tests for fast candle direction (trading/broker_sense/fast_candles) + crypto order type._
- **classes:** TestDirection, TestRead, TestOrderType
- **functions:** `_uptrend(n, start, step)`; `_downtrend(n, start, step)`
- **imports:** __future__, trading.broker_sense, unittest

## `tests/test_fast_nav.py`
_tests/test_fast_nav.py — fast-nav planner over learned app-school state (2026-07-10)._
- **functions:** `_seed(tmp_path, skills)`; `test_plan_prefers_learned_url_then_explore(monkeypatch, tmp_path)`; `test_skill_outranks_goto(monkeypatch, tmp_path)`; `test_two_strikes_demotes_below_explore_ranking(monkeypatch, tmp_path)`; `test_unknown_target_only_explores(monkeypatch, tmp_path)`
- **imports:** __future__, json

## `tests/test_fast_nav_wiring.py`
_HumanUI.navigate() — the fast_nav wiring (ledger #10): plan → try → record._
- **classes:** _FakeLocator, _FakePage, FastNavWiringTest
- **functions:** `_ui(page)`
- **imports:** pathlib, unittest

## `tests/test_file_memory.py`
_Tests for memory/file_memory.py — Claude-style durable file memory (Phase B)._
- **functions:** `test_write_creates_note_and_index(tmp_path)`; `test_persists_across_processes_and_recalls(tmp_path)`; `test_keyword_fallback_without_associative(tmp_path)`
- **imports:** memory.associative, memory.file_memory

## `tests/test_foundation_nodes.py`
_Tier-1 foundation / SOTA model nodes (nodes/foundation_nodes.py, groups A–F)._
- **classes:** TestFoundationNodes
- **functions:** `_synth(n, seed)`; `_panel(T, N, seed)`; `_try_import()`
- **imports:** __future__, numpy, unittest, warnings

## `tests/test_free_eyes.py`
_Tests for the FREE eyes' deterministic matcher + OCR-row parsing (pure, no browser/LLM)._
- **classes:** TestMatcher, TestOcrRow, TestGlanceText
- **imports:** trading.brain.vision.free_eyes, unittest

## `tests/test_free_eyes_ocr_timeout.py`
_tests/test_free_eyes_ocr_timeout.py — the OCR read must never block the caller forever._
- **classes:** TestOCRTimeout
- **imports:** os, time, trading.brain.vision, unittest

## `tests/test_futures_options_symbols.py`
_Regression: NSE futures/options screeners must emit BROKER-TRADABLE symbols._
- **classes:** _FakeClient
- **functions:** `test_ltp_uses_rest_quotes_not_websocket_get_ltp()`; `test_nse_futures_resolve_to_near_month_contract(monkeypatch)`; `test_min_open_legacy_fno_key_lands_on_futures()`; `test_lot_size_prefers_real_master_contract_over_segment_default()`; `test_lot_size_falls_back_when_openalgo_unreachable()`
- **imports:** pathlib, tempfile, trading.state

## `tests/test_gate_tuner.py`
_tests/test_gate_tuner.py — counterfactual gate-threshold sweeps (2026-07-10)._
- **functions:** `_rows(n_low, n_high)`; `test_sweep_finds_profitable_threshold(monkeypatch, tmp_path)`; `test_min_support_rail(monkeypatch, tmp_path)`; `test_too_few_scored_rows_is_honest(monkeypatch, tmp_path)`
- **imports:** __future__, json

## `tests/test_generators.py`
_tests/test_generators.py — the Strategy-Generator Portfolio (offline/CPU parts)._
- **classes:** TestScaffold, TestGenerators, TestFamilyWise
- **functions:** `_synth(n, seed)`
- **imports:** numpy, pandas, pathlib, tempfile, trading.state, unittest

## `tests/test_goal_scoreboard.py`
_W1 goal scoreboard tests — synthetic journal rows in an isolated STATE_DIR._
- **classes:** GoalScoreboardTest
- **functions:** `_row(pnl, days_ago, exchange, seg, it, sym)`
- **imports:** os, tempfile, time, unittest

## `tests/test_grounded_eyes.py`
_Tests for invent-beyond #1 — local grounded eyes (OmniParser icon grounding)._
- **classes:** TestGrounding, TestAvailability
- **functions:** `_png(w, h)`; `_eyes(boxes)`
- **imports:** __future__, io, os, unittest

## `tests/test_guardrails_t8.py`
_Trading Phase T8.2 acceptance tests — journal-fitness + overfitting guardrails._
- **classes:** TestProbabilisticDeflatedSharpe, TestPBO, TestInformationCoefficient, TestFitness, TestGuardrailGate
- **functions:** `_make_ohlcv(n, seed) -> pd.DataFrame`
- **imports:** __future__, json, numpy, pandas, trading.strategy.features, trading.strategy.fitness, trading.strategy.genome, trading.strategy.guardrails, trading.strategy.operators, unittest, warnings

## `tests/test_hotpath_metalabel.py`
_Regression: the numba triple_barrier_labels hot path (Pillar 9) must EXACTLY equal the_
- **classes:** TestTripleBarrierHotPath
- **functions:** `_reference(ohlcv, signal)`; `_make(n, seed)`
- **imports:** numpy, pandas, trading.strategy.metalabel, unittest

## `tests/test_hpo.py`
_Optuna HPO utility (core/hpo.py, Tier-2/3 infra group H)._
- **classes:** TestHPO
- **imports:** __future__, core.hpo, numpy, unittest, warnings

## `tests/test_human_handoff.py`
_tests/test_human_handoff.py — mid-session human-CAPTCHA handoff._
- **classes:** FakePage, TestHumanHandoff
- **functions:** `_fresh_module(tmp_state)`
- **imports:** importlib, os, unittest

## `tests/test_human_memory.py`
_Phase P4.2 (human-like memory layer) acceptance tests — fully offline + deterministic._
- **classes:** _StubMem, StubBrain, TestDecay, TestStability, TestRecall, TestTiers, TestDream, TestStatus
- **functions:** `_brain()`
- **imports:** __future__, json, math, memory.human_memory, unittest, warnings

## `tests/test_hybrid_memory.py`
_Phase P4.2 HybridMemory acceptance tests — fully OFFLINE + deterministic._
- **classes:** StubBrain, TestAdd, TestRecall, TestReflect, TestDream, TestMem0Gating, TestStatus, TestDeterminism
- **functions:** `stub_llm(messages)`; `_hybrid()`; `_seed(hm, n)`
- **imports:** __future__, datetime, json, memory.hybrid_memory, unittest, warnings

## `tests/test_hypothesis.py`
_tests/test_hypothesis.py — the brain's hypothesis→experiment→belief loop._
- **functions:** `isolated_state(tmp_path, monkeypatch)`; `_trades(n, seed) -> list[dict]`; `test_confirms_true_edge_and_refutes_false(isolated_state)`; `test_reflect_promotes_and_archives(isolated_state)`; `test_persists_and_reloads(isolated_state)`; `test_node_protocol_and_registry(isolated_state)`; `test_pipeline_integration_with_ledger(isolated_state)`
- **imports:** __future__, core.node_protocol, numpy, pytest

## `tests/test_indicator_fusion.py`
_Tests for the ultra-advanced multi-timeframe indicator-fusion engine (offline, no network)._
- **classes:** TestIndicators, TestBarriers, TestMetaLabel, TestFuse
- **functions:** `_series(trend, n, start, noise) -> list`
- **imports:** __future__, math, trading.broker_sense, unittest

## `tests/test_interception.py`
_Tests for the network-interception recorder + endpoint registry (offline, no browser)._
- **classes:** _IsolatedState, TestUrlPattern, TestClassify, TestRegistry, _FakeRequest, _FakeResponse, TestRecorder
- **imports:** __future__, pathlib, tempfile, time, trading.broker_sense, trading.state, unittest

## `tests/test_intermarket_gnn.py`
_AI-scientist idea #10 — Intermarket GNN (PyG GCN over the cross-feature graph)._
- **classes:** TestIntermarketGNN
- **functions:** `_graph_dataset(n, seed)`
- **imports:** core.node_protocol, nodes.intermarket_gnn, numpy, unittest

## `tests/test_journal_t5.py`
_Trading Phase T5 (Trade Journal & Brain-Confidence) acceptance tests — fully offline._
- **classes:** TestSchema, TestCharges, TestQuality, TestAnalytics, TestBehavior, TestConfidence, TestTearsheet, TestJournalEndToEnd
- **imports:** __future__, json, os, tempfile, trading.journal.analytics, trading.journal.behavior, trading.journal.charges, trading.journal.confidence, trading.journal.journal, trading.journal.quality, trading.journal.schema, trading.journal.tearsheet, unittest

## `tests/test_knowledge.py`
_Acceptance tests for the Phase-4 knowledge brain: ingest -> recall works._
- **classes:** TestKnowledge
- **imports:** __future__, memory.brain, unittest

## `tests/test_knowledge_tracing.py`
_Phase P4.4 (2nd mastery model) acceptance tests — EduKTM Deep Knowledge Tracing._
- **classes:** _StubBrain, TestTracerFit, TestNoInteractions, TestAddSequence, TestBaselineRanking, TestDKTEasyVsHard, TestDeterminism, TestQuizIntegration
- **functions:** `_muted()`; `_quiet_fit(tracer)`
- **imports:** __future__, contextlib, io, json, memory.knowledge_tracing, memory.self_quiz, unittest, warnings

## `tests/test_learn_loop.py`
_Continuous learning loop (trading/brain/learn_loop.py) — deterministic unit tests._
- **classes:** _StubLearner
- **functions:** `_fresh_loop()`; `test_queue_topic_learned_first_then_curriculum()`; `test_errors_recorded_and_status_honest()`; `test_self_eval_fires_on_schedule()`; `test_enabled_flag_persists_across_instances()`
- **imports:** pathlib, tempfile, trading.state

## `tests/test_librarian.py`
_Phase P4.3 (self-feeding Librarian) acceptance tests — fully offline & deterministic._
- **classes:** StubBrain, TestDiscover, TestIngestItem, TestDedup, TestFeed, TestPersistence, TestStatusAndDeterminism
- **functions:** `make_web(items, recorder)`; `make_arxiv(items, recorder)`; `make_rss(items, recorder)`; `make_extractor(text, recorder)`; `_lib(brain)`
- **imports:** __future__, json, memory.librarian, os, tempfile, unittest, warnings

## `tests/test_live_chain.py`
_tests/test_live_chain.py — real-broker option chain → T4 analytics (2026-07-10)._
- **functions:** `_raw(expiry_days, spot, atm)`; `test_to_chain_builds_real_analytics()`; `test_expiry_day_still_has_time_value()`; `test_empty_chain_raises_not_fakes()`
- **imports:** __future__, datetime, pytest, trading.options.live_chain

## `tests/test_llm_governor.py`
_tests/test_llm_governor.py — LLM budget governor (2026-07-10)._
- **functions:** `gov(monkeypatch, tmp_path)`; `test_rate_limited_provider_skipped_while_cooling(gov)`; `test_permanent_error_gets_hour_cooldown(gov)`; `test_response_cache_hits_within_ttl(gov)`; `test_blackout_guard_single_attempt_when_all_cooling(gov)`; `test_governor_kill_switch(gov, monkeypatch)`
- **imports:** __future__, pytest, time

## `tests/test_llm_telemetry.py`
_Cloud-LLM telemetry (core/llm_telemetry.py) + LLMForecastNode (nodes/llm_forecast_node.py)._
- **classes:** TestLLMTelemetry, TestLLMForecastNode
- **imports:** __future__, numpy, os, tempfile, unittest, warnings

## `tests/test_lob_transformer.py`
_AI-scientist idea #6 — LiT order-book transformer node._
- **classes:** TestLOBTransformer
- **functions:** `_microstructure_dataset(n, d, seed)`
- **imports:** core.node_protocol, nodes.lob_transformer, numpy, unittest

## `tests/test_loop_keeper.py`
_tests/test_loop_keeper.py — runtime self-heal keeper (2026-07-10)._
- **functions:** `_fresh_keeper(monkeypatch, tmp_path)`; `test_all_alive_no_restart(monkeypatch, tmp_path)`; `test_dead_loop_triggers_start_all(monkeypatch, tmp_path)`; `test_off_flag_blocks_restart(monkeypatch, tmp_path)`
- **imports:** __future__, importlib, sys

## `tests/test_memory_assoc.py`
_P4.2 acceptance: human-like ASSOCIATIVE recall (Personalized-PageRank + RRF fusion)._
- **classes:** TestAssociativeRecall
- **imports:** __future__, memory.brain, unittest

## `tests/test_memory_search.py`
_Tests for trading/brain/memory_search.py — FTS5 full-text memory search (offline, isolated)._
- **classes:** TestMemorySearch
- **imports:** __future__, json, pathlib, tempfile, trading.brain, trading.state, unittest

## `tests/test_meta_challenger.py`
_Tests for trading/direction/meta_challenger — the TabPFN duel for the D6 meta-labeler._
- **classes:** _Iso, TestMetaChallenger
- **functions:** `_seed_train(n, sep)`
- **imports:** json, pathlib, tempfile, trading.state, unittest

## `tests/test_meta_labeler.py`
_Tests for trading/direction/meta_labeler — D6 direction meta-labeler._
- **classes:** _Iso, TestMetaLabeler
- **functions:** `_write_examples(n)`
- **imports:** json, pathlib, random, tempfile, trading.state, unittest

## `tests/test_micro_features.py`
_Tests for trading/direction/micro_features — D4 microstructure direction lanes._
- **classes:** _Iso, TestFundingExtreme, TestMtfAgree, TestRecordClaims
- **functions:** `_feather(root, rel, col_open, closes, hours)`
- **imports:** pathlib, tempfile, time, trading.state, unittest

## `tests/test_micro_policy.py`
_Tests for invent-beyond #4 — distilled entry micro-policy (teacher table + student)._
- **classes:** _Sandbox, _StubDecider, TestCheapFeatures, TestDistillAndDecide
- **functions:** `_df(n, seed)`
- **imports:** __future__, numpy, pathlib, tempfile, time, trading.state, unittest

## `tests/test_micro_transformer.py`
_Tests for nodes/micro_transformer_node.py — cloned-LLM node (Phase C)._
- **functions:** `_toy(n, seed)`; `test_tokenizer_handles_any_data()`; `test_satisfies_node_protocol_and_learns()`; `test_c_kernel_generates_with_own_weights(tmp_path)`
- **imports:** core.node_protocol, nodes.micro_transformer_node, pytest, random

## `tests/test_mirror_gate.py`
_Tests for trading/direction/mirror_gate — D2 of the Direction Accuracy Program._
- **classes:** _Iso, TestMirrorGate
- **functions:** `_seed(buckets) -> None`
- **imports:** pathlib, tempfile, trading.state, unittest

## `tests/test_mlnb_engine_native.py`
_Tests for the fork's brain-native layer (E-workstreams 2026-07-10):_
- **classes:** _TmpState, TestSidecarEnrich, TestDecisionInbox, TestInEngineTailgate
- **imports:** json, pathlib, tempfile, time, unittest

## `tests/test_multihead.py`
_Acceptance test (multi-output): every output head must beat its task baseline._
- **classes:** TestMultiHead
- **imports:** __future__, run_multi, unittest

## `tests/test_multisegment.py`
_Tests for the multi-segment Freqtrade fork (vendor/freqtrade) + its glue._
- **classes:** TestSegmentIsolation, TestOptionRank, TestSegmentConfigFanout
- **imports:** datetime, os, unittest

## `tests/test_news_ingest.py`
_tests/test_news_ingest.py — free-RSS → symbol-linked brain news memory (2026-07-10)._
- **functions:** `_fetcher(url, limit)`; `_seed_journal(tmp_path)`; `test_ingest_links_symbols_and_dedupes(monkeypatch, tmp_path)`; `test_items_for_symbol_lookup(monkeypatch, tmp_path)`; `test_min_gap_rate_limit(monkeypatch, tmp_path)`; `test_dead_feed_never_kills_cycle(monkeypatch, tmp_path)`
- **imports:** __future__, json, trading.brain.news

## `tests/test_news_t8.py`
_Trading Phase T8.7 (Autonomous news research + sentiment) acceptance tests — fully offline._
- **classes:** TestSentimentScorer, TestNewsItem, TestNewsResearcher, TestNewsSentimentNode
- **imports:** __future__, core.node_protocol, os, trading.brain.news, trading.brain.sentiment, unittest, warnings

## `tests/test_ocular_cortex.py`
_Tests for the Ocular Cortex (trading/brain/vision/ocular_cortex) — offline, no browser._
- **classes:** _IsolatedState, TestPerceptualFrame, TestLayoutMemory, TestOcularCortex
- **functions:** `_controls(labels)`
- **imports:** __future__, pathlib, tempfile, trading.brain.vision, trading.state, unittest

## `tests/test_ocular_perception.py`
_Tests for OcularPerception (trading/broker_sense/ocular_perception) — funnel eyes, offline._
- **classes:** _IsolatedState, TestSummarizeBook, TestEnrich, TestVisionSink, TestLinkage
- **functions:** `_perception(network)`
- **imports:** __future__, pathlib, tempfile, trading.brain.vision.ocular_cortex, trading.broker_sense, trading.broker_sense.learning_columns, trading.state, unittest

## `tests/test_offpolicy_lanes.py`
_Tests for invent-beyond #6 — off-policy (counterfactual) lane-weight learning._
- **classes:** TestCounterfactualWeights
- **imports:** __future__, pathlib, tempfile, trading.state, unittest

## `tests/test_onchain_altdata.py`
_AI-scientist idea #11 — on-chain + whale alt-data lane (hermetic, injected fetchers)._
- **classes:** TestOnChainAltData
- **functions:** `_stub_fetchers(fg, avg_tx, mempool)`
- **imports:** trading.altdata.onchain, unittest

## `tests/test_online.py`
_Trading Phase O1–O4 (Always-Online Supervisor) acceptance tests — fully offline._
- **classes:** TestMarketSession, TestPriceQuoteExchange, TestTradingState, TestPaperWallet, TestReplay, TestOnlineSupervisor
- **functions:** `_ohlcv(seed, n) -> pd.DataFrame`
- **imports:** __future__, datetime, json, numpy, pandas, trading, trading.online.replay, trading.online.session, trading.online.state, trading.online.supervisor, trading.online.wallet, unittest, warnings

## `tests/test_options_screener.py`
_Phase 2: pure CE/PE generation logic (no live broker/market needed)._
- **functions:** `_chain(expiry)`; `test_atm_strike_picks_nearest_listed()`; `test_nearest_expiry()`; `test_atm_mode_gives_one_ce_one_pe_at_atm()`; `test_ladder_mode_adds_otm_strikes()`; `test_chain_mode_returns_capped_chain()`; `test_picks_only_nearest_expiry()`; `test_norm_rows_derives_opt_type_from_symbol_suffix()`; `test_no_broker_returns_empty(monkeypatch)`
- **imports:** pathlib, tempfile, trading.screener, trading.state

## `tests/test_options_segment.py`
_Options-segment regressions (2026-07-10)._
- **classes:** TestOptionsTradeabilityGuard, TestOptionsCycleHonesty, TestOptionBookGuard
- **functions:** `_bare_executor()`
- **imports:** __future__, unittest

## `tests/test_options_t4.py`
_Trading Phase T4 (Options Intelligence) acceptance tests — fully offline._
- **classes:** TestBlack76Greeks, TestImpliedVol, TestIVRankPercentile, TestMaxPain, TestPCR, TestGEX, TestOI, TestPayoff, TestOptionsChain
- **imports:** __future__, math, trading.options.chain, trading.options.gex, trading.options.greeks, trading.options.iv, trading.options.max_pain, trading.options.oi, trading.options.payoff, trading.options.pcr, unittest

## `tests/test_patterns_t8.py`
_Trading Phase T8.6 acceptance tests — fully offline + deterministic._
- **classes:** TestSyntheticData, TestPatterns, TestRegime, TestPicking, TestEntryExit
- **functions:** `_synthetic_ohlcv(n, seed) -> pd.DataFrame`
- **imports:** __future__, numpy, pandas, trading.brain.continual, trading.brain.entryexit, trading.brain.patterns, trading.brain.picking, trading.brain.regime, unittest, warnings

## `tests/test_perception_research.py`
_Tests for trading/brain/perception.py + researcher.deep_research (Phase D, offline)._
- **functions:** `test_read_any_plain_and_csv(tmp_path)`; `test_read_any_feeds_memory(tmp_path)`; `test_perception_status_reports_engines()`; `test_deep_research_falls_back_offline()`
- **imports:** memory.associative, trading.brain.perception, trading.brain.researcher

## `tests/test_percoin_decider.py`
_tests/test_percoin_decider.py — brain picks the best strategy PER COIN (offline, no network)._
- **classes:** _Strat
- **functions:** `_trend_df(n, up)`; `_make_decider(df, strategies)`; `test_picks_the_profitable_strategy_on_an_uptrend()`; `test_stays_flat_when_no_strategy_clears_threshold()`; `test_high_threshold_forces_flat_even_with_a_winner()`; `test_exit_when_best_strategy_turns_negative_while_in_position()`; `test_backtest_is_causal_no_lookahead()`
- **imports:** __future__, numpy, pandas, trading.crypto.freqtrade.percoin_decider

## `tests/test_phase3.py`
_Phase-3 acceptance tests: Hellsemble + deep (L2/L3) routing._
- **classes:** TestPhase3Routing
- **functions:** `_factories()`; `_reg_factories()`; `_split(X, y, frac, seed)`; `_naive(y)`
- **imports:** __future__, core.heads, core.node_protocol, data.benchmarks, eval.golden, nodes, nodes.cascade_node, nodes.dynamic_bus, nodes.gated_node, nodes.router_node, nodes.routing_advanced, nodes.structure_search, unittest

## `tests/test_pipeline.py`
_Phase-0/1 acceptance tests: interface enforcement + the learning loop works._
- **classes:** TestPipeline
- **imports:** __future__, core.node_protocol, eval.golden, nodes.base_learners, nodes.stacking_node, unittest

## `tests/test_pipeline_t8.py`
_Trading Phase T8.9 (end-to-end brain trading pipeline + safety) acceptance tests._
- **classes:** TestDecideContract, TestTracing, TestSafetyGate, TestSafetyReview, TestDeterminism, TestSerialization, TestBothMarkets
- **functions:** `_make_ohlcv(n, seed) -> pd.DataFrame`; `_stub_news()`; `_strategy(market, seed)`; `_full_pipeline(market)`; `_assert_no_numpy(case, obj, path)`
- **imports:** __future__, json, numpy, pandas, trading.brain.entryexit, trading.brain.experience, trading.brain.news, trading.brain.observability, trading.brain.patterns, trading.brain.pipeline, trading.brain.regime, trading.execution.circuit_breaker, trading.execution.kill_switch, trading.strategy.genome, trading.strategy.operators, unittest, warnings

## `tests/test_profit_tailgate.py`
_Tests for profit tailgating (trading/execution/profit_tailgate) — the ratcheting profit lock._
- **classes:** _Iso, TestRatchet
- **imports:** pathlib, tempfile, trading.state, unittest

## `tests/test_psychology.py`
_Trader-psychology engine (order-book depth) — pure-computation tests._
- **classes:** TestSnapshots, TestSignals, TestJournalWiring, TestDeepLob
- **functions:** `_snap(mid, bid_boost, ask_boost, ts, levels)`; `_ring(n, bid_boost, ask_boost, seed)`
- **imports:** collections, pathlib, random, tempfile, time, trading.brain.psychology, trading.state, unittest

## `tests/test_pullback.py`
_Tests for trading/direction/pullback — D3 pullback entries._
- **classes:** _Iso, TestPullback
- **imports:** pathlib, tempfile, time, trading.state, unittest

## `tests/test_reflex.py`
_Tests for trading/direction/reflex — R2 Reflex fast lane (tick → order)._
- **classes:** _Iso, TestCrossed, TestVenueMapping, TestTickToOrder
- **imports:** pathlib, tempfile, trading.state, unittest

## `tests/test_regime_moe.py`
_AI-scientist idea #7 — Regime-conditioned MoE router (learned gate over frozen experts)._
- **classes:** TestRegimeMoE
- **functions:** `_regime_dataset(n, d, seed)`
- **imports:** core.node_protocol, nodes.regime_moe, numpy, unittest

## `tests/test_reset_closed.py`
_tests/test_reset_closed.py — closed-trade reset is brain-safe + isolated._
- **classes:** _FakeRest, _FakeClient
- **functions:** `isolated_state(tmp_path, monkeypatch)`; `test_bad_confirm_deletes_nothing(isolated_state)`; `test_reset_clears_journal_and_freqtrade_and_backs_up(isolated_state)`; `test_case_insensitive_confirm(isolated_state)`; `test_empty_journal_no_backup_no_crash(isolated_state)`
- **imports:** __future__, json, pytest, trading, trading.journal.reset

## `tests/test_rl_exec_policy.py`
_W6 RL execution-policy tests — tiny synthetic data, isolated STATE_DIR._
- **classes:** RlExecPolicyTest
- **functions:** `_ohlcv(n, seed, drift)`
- **imports:** numpy, os, pathlib, tempfile, unittest

## `tests/test_rl_execution.py`
_AI-scientist idea #8 — RL execution agent (SB3-PPO order slicing beats TWAP)._
- **classes:** TestExecutionEnv, TestRLExecutionAgent
- **imports:** trading.execution.rl_exec_env, trading.execution.rl_execution, unittest

## `tests/test_robust.py`
_Acceptance test (hardening): the router-grown brain must beat the naive_
- **classes:** TestRobust
- **imports:** __future__, run_robust, unittest

## `tests/test_scorecard.py`
_Regression tests for the segment scorecard's (market, segment) derivation_
- **classes:** TestTradeSegment
- **functions:** `_load_server()`
- **imports:** importlib.util, os, unittest

## `tests/test_scouts_consensus.py`
_W4 scout swarm + consensus oracle tests — isolated STATE_DIR._
- **classes:** ScoutsConsensusTest
- **imports:** os, pathlib, tempfile, unittest

## `tests/test_screen_mirror.py`
_Tests for trading/broker_sense/screen_mirror.py — the Brain Screen Mirror store._
- **classes:** FakePage, ScreenMirrorTest
- **imports:** pathlib, tempfile, trading, unittest

## `tests/test_screener.py`
_tests/test_screener.py — per-segment screener: offline-safe, deterministic._
- **classes:** FakeNSESource, FakeCryptoSource, FakeMCXClient
- **functions:** `test_percent_change_filter_sorts_and_clips()`; `test_volume_filter_ranks_desc_with_min()`; `test_relative_volume_detects_spike()`; `test_realized_volatility_and_range_stability()`; `test_oi_buildup_classification()`; `test_apply_technical_filters_on_synthetic_ohlc()`; `test_apply_technical_filters_handles_garbage()`; `test_screen_nse_movers_ranks_and_scores()`; `test_screen_crypto_spot_filters_quote_and_ranks()`; `test_candidates_uses_live_source_when_available()`; `test_candidates_falls_back_to_stub_when_source_empty(monkeypatch)`; `test_invalid_segment_returns_empty()`; `test_demo_screener_is_pure_offline_stub_all_segments()`; `test_stub_candidates_known_symbols()`; `test_watchlist_dedupes_and_sorts_across_segments()`; `test_status_snapshot_shape()`; `test_resolve_near_month_fut_picks_nearest_and_exact_base(monkeypatch)`; `test_screen_mcx_commodities_emits_dated_fut_symbols(monkeypatch)`
- **imports:** __future__, math, pytest, trading.screener, trading.screener.screener

## `tests/test_segment_split.py`
_Phase 1 regression: NSE `fno` segment split into `futures` + `options`._
- **functions:** `test_nse_segments_are_split()`; `test_legacy_fno_normalizes_to_futures()`; `test_marketstate_migrates_saved_fno()`; `test_loop_maps_cover_futures_and_options()`; `test_max_leverage_is_market_aware()`; `test_screener_routes_options()`
- **imports:** pathlib, tempfile, trading.state

## `tests/test_self_coding_p47.py`
_Phase P4.7 (Autonomy + self-coding) acceptance tests — fully offline & sandboxed._
- **classes:** TestProposer, TestSandbox, TestGate, TestLoop, TestDemo
- **imports:** __future__, cognition.self_coding, unittest, warnings

## `tests/test_self_evolve.py`
_tests/test_self_evolve.py — lifelong self-evolving strategy loop._
- **functions:** `isolated_state(tmp_path, monkeypatch)`; `_ohlcv(seed, n) -> pd.DataFrame`; `test_gated_off_by_default(isolated_state, monkeypatch)`; `test_force_runs_and_persists(isolated_state)`; `test_admission_grows_library(isolated_state)`; `test_reevaluate_retires_weak_skill(isolated_state)`; `test_node_protocol_and_registry(isolated_state)`
- **imports:** __future__, core.node_protocol, numpy, pandas, pytest

## `tests/test_self_quiz.py`
_Phase P4.4 (FSRS self-quiz mastery tracker) acceptance tests — fully offline._
- **classes:** KnowBrain, BlankBrain, TestMakeCloze, TestQuizOne, TestRunRound, TestMasteryCurve, TestInjectedHooks, TestStatus
- **imports:** __future__, datetime, json, memory.self_quiz, unittest, warnings

## `tests/test_sizing.py`
_Tests for trading/sizing -- per-trade position/capital sizer._
- **functions:** `test_atr_risk_respects_max_risk_pct()`; `test_atr_risk_uses_stop_distance_when_no_atr()`; `test_atr_risk_scales_with_max_risk_pct()`; `test_atr_risk_zero_when_no_stop_or_atr()`; `test_kelly_fraction_known_values()`; `test_kelly_fraction_between_0_and_1()`; `test_kelly_no_edge_gives_nonpositive_size()`; `test_kelly_missing_inputs_zero()`; `test_afml_bet_size_zero_at_half()`; `test_afml_bet_size_grows_to_one()`; `test_ai_meta_zero_at_half_and_caps_near_one()`; `test_ai_meta_monotonic_in_prob()`; `test_vol_target_formula()`; `test_max_position_pct_cap_binds()`; `test_kelly_cap_binds()`; `test_short_flips_sign_atr()`; `test_short_flips_sign_ai_meta()`; `test_auto_blend_takes_min_of_edge_and_atr()`; `test_auto_drawdown_reduces_size()`; `test_auto_falls_back_when_no_signal()`; `test_zero_capital_returns_empty()`; `test_return_keys_present()`; `test_invalid_method_raises()`; `test_status_shape()`; `test_build_demo_sizing_deterministic()`
- **imports:** __future__, math, pytest, trading.sizing

## `tests/test_skill_learnings.py`
_Tests for tools/skill_learnings.py — the self-improving-skills learning loop (isolated tmp dir)._
- **classes:** TestSkillLearnings
- **imports:** __future__, pathlib, tempfile, tools, unittest

## `tests/test_skills_t8.py`
_Trading Phase T8.8 (skill library + observability + self-improvement) tests — offline._
- **classes:** TestSkillRoundTrip, TestSkillLibraryGate, TestSkillLibraryRetrieval, TestAdmitStrategy, TestSkillPersistence, TestBrainTracer, TestSelfImprover, TestDSPyOptimizerGatedOff
- **functions:** `_skill(name, market, metric)`
- **imports:** __future__, itertools, numpy, os, trading, trading.brain.observability, trading.brain.selfimprove, trading.brain.skills, trading.strategy.control, unittest, warnings

## `tests/test_state_update_json.py`
_state.update_json — locked cross-process merge (2026-07-10 review fix)._
- **classes:** UpdateJsonTest
- **functions:** `_writer(state_dir, key, n) -> None`
- **imports:** multiprocessing, pathlib, tempfile, unittest

## `tests/test_stock_xray.py`
_Tests for the Stock X-Ray pure analytics (no network): exchange routing, zones, depth, candles._
- **classes:** TestExchangeRouting, TestCandleConversion, TestZones, TestDepthAndCircuit
- **imports:** trading.broker_sense.stock_xray, unittest

## `tests/test_strategy_t8.py`
_Trading Phase T8.1 (Strategy-Evolution Engine) acceptance tests — fully offline._
- **classes:** TestFeatures, TestGenome, TestOperators, TestBacktest, TestWalkForward
- **functions:** `_make_ohlcv(n, seed) -> pd.DataFrame`
- **imports:** __future__, math, numpy, pandas, trading.strategy.backtest, trading.strategy.features, trading.strategy.genome, trading.strategy.operators, unittest, warnings

## `tests/test_stream_of_mind_p46.py`
_Phase P4.6 (Stream-of-Mind + observability) acceptance tests — fully offline._
- **classes:** _Brain, TestGlobalWorkspace, TestStreamOfMind, TestObservability, TestAGUI, TestDemo
- **functions:** `_abstainer()`; `_som(brain)`
- **imports:** __future__, cognition, cognition.stream_of_mind, itertools, numpy, unittest, warnings

## `tests/test_surface_rails.py`
_W2 scientific-method rails tests — isolated STATE_DIR._
- **classes:** SurfaceRailsTest
- **imports:** pathlib, tempfile, unittest

## `tests/test_thinking_p45.py`
_Phase P4.5 (Thinking + knowing-what-it-knows) acceptance tests — fully offline._
- **classes:** _Graph, _Brain, TestActiveInference, TestReasoning, TestSymbolic, TestCausal, TestCalibration, TestConstitution, TestThinker, TestBrainAgentIntegration, TestDemo
- **functions:** `_abstainer(level)`
- **imports:** __future__, cognition, cognition.reasoning, numpy, unittest, warnings

## `tests/test_tier2_nodes.py`
_Tier-2 model nodes (nodes/tier2_nodes.py, groups G/J/K)._
- **classes:** TestTier2Nodes
- **functions:** `_synth(n, seed)`; `_imp()`
- **imports:** __future__, numpy, unittest, warnings

## `tests/test_tier2b_nodes.py`
_Remaining catalog-ADD nodes (nodes/tier2b_nodes.py) — the MED/LOW ADDs completed._
- **classes:** TestTier2bNodes
- **functions:** `_synth(n, seed)`; `_imp()`
- **imports:** __future__, numpy, unittest, warnings

## `tests/test_tier3_nodes.py`
_Tier-3 infra nodes (nodes/tier3_nodes.py) + drift utility (core/drift.py)._
- **classes:** TestTier3Nodes, TestDrift
- **functions:** `_synth(n, seed)`; `_imp()`
- **imports:** __future__, numpy, unittest, warnings

## `tests/test_track_record.py`
_W7 track record + rule-of-three tests — isolated STATE_DIR._
- **classes:** TrackRecordTest
- **imports:** pathlib, tempfile, unittest

## `tests/test_trade_features.py`
_tests/test_trade_features.py — the trade-row → node-network bridge (TradeOutcomeNet)._
- **functions:** `_closed(win, i) -> dict`; `test_feature_row_length_matches_schema()`; `test_network_trains_and_predicts(monkeypatch)`; `test_degrades_honestly_when_undersampled()`
- **imports:** random, trading.brain.trade_features

## `tests/test_trading_t1.py`
_Trading Phase T1 (NSE Foundation) acceptance tests._
- **classes:** _IsolatedState, TestConfig, TestSquareoff, TestMasterToggle, _FakeFeed, TestWatchlist, TestInstrumentParsing
- **imports:** __future__, datetime, pathlib, tempfile, trading, trading.config, trading.instruments, trading.market_toggle, trading.state, trading.watchlist, unittest

## `tests/test_trailing_exits.py`
_Tests for trading/exits/ — four trailing-exit components over one signed engine._
- **functions:** `_first_exit(engine, path)`; `test_long_stop_trail_exits_on_drop_from_peak()`; `test_long_stop_trail_ratchets_up_only()`; `test_long_stop_no_exit_while_rising()`; `test_long_profit_trail_arms_only_after_offset()`; `test_long_profit_trail_ratchets_after_arming()`; `test_short_loss_trail_exits_on_rise_from_trough()`; `test_short_profit_trail_ratchets_down()`; `test_short_profit_arms_only_after_offset()`; `test_long_stop_trail_matches_vectorbt_tsl()`; `test_short_trail_matches_vectorbt()`; `test_atr_mode_produces_volatility_scaled_stop()`; `test_chandelier_mode_uses_pandas_ta_classic()`; `test_supertrend_mode_uses_pandas_ta_classic()`; `test_make_exit_returns_correct_wrappers()`; `test_make_exit_passes_config_through()`; `test_make_exit_rejects_unknown_purpose()`; `test_reset_re_arms_for_new_position()`; `test_status_snapshot_shape()`; `test_build_demo_trailing_snapshot()`; `test_engine_signed_core_direct_construction()`
- **imports:** __future__, numpy, pandas, pytest, trading.exits

## `tests/test_truth_ledger.py`
_Tests for trading/direction/truth_ledger — D1 of the Direction Accuracy Program._
- **classes:** _Iso, TestRecord, TestTickLabeling, TestWilson, TestBackfill
- **functions:** `_write_feather(root, rel, t0, closes) -> None`
- **imports:** json, pathlib, tempfile, time, trading.state, unittest

## `tests/test_tsfm_ensemble.py`
_AI-scientist idea #5 — TSFM ensemble + conformal calibration._
- **classes:** TestTSFMEnsemble, TestTimeMoENode
- **functions:** `_dataset(n, d, seed)`
- **imports:** core.node_protocol, nodes.tsfm_ensemble, numpy, os, unittest

## `tests/test_ui_only_data.py`
_UI-only data mode tests (owner 2026-07-07) — capture parsing + honest misses._
- **classes:** UiOnlyDataTest, AutoFlipGovernorTest, TestCrawlUrlNormalization, TestGovernorFlipBack
- **functions:** `_klines(n, t0, tf_ms, price)`
- **imports:** os, pathlib, tempfile, time, unittest

## `tests/test_ui_skill_cache.py`
_Tests for the hand skill-cache (invent-beyond #2) + free-eyes glance cache (#5)._
- **classes:** _IsolatedState, TestSkillCache, TestGlanceCache
- **functions:** `_ui(name)`
- **imports:** __future__, pathlib, tempfile, time, trading.state, unittest

## `tests/test_uq_conformal.py`
_Pillar 17 — conformal calibrated uncertainty (trading/uq) + sizing gate tests._
- **classes:** TestSelfUncertainty, TestTradeUQ, TestSizerConsumesUQ, TestJournalColumns
- **functions:** `_synth_trades(n, seed) -> list[dict]`
- **imports:** __future__, math, numpy, pathlib, tempfile, unittest

## `tests/test_vae_factor.py`
_AI-scientist idea #9 — VAE factor node + synthetic scenario generator._
- **classes:** TestVAEFactor
- **functions:** `_dataset(n, d, seed)`
- **imports:** core.node_protocol, nodes.vae_factor, numpy, unittest

## `tests/test_visible_controls.py`
_Regression tests for the 2026-07-10 phantom-click fixes._
- **classes:** _IsolatedState, TestCoveredControls, TestDismissModalsProgress
- **functions:** `_eyes()`
- **imports:** __future__, pathlib, tempfile, trading.state, unittest

## `tests/test_vision_computer_use.py`
_Tests for the FREE computer-use loop (trading/brain/vision/computer_use) — offline._
- **classes:** _IsolatedState, _FakeElement, _FakePage, TestActionParsing, TestGuard, TestLoop, TestPaidBackendOff
- **imports:** __future__, pathlib, tempfile, trading.brain.vision, trading.brain.vision.ocular_cortex, trading.state, unittest

## `tests/test_vision_engine.py`
_Tests for the free vision engine (core.llm.vision_chat) — the brain's FREE eyes._
- **classes:** TestImageDataUrl, TestVisionChat, TestLocalVisionBackstop
- **imports:** __future__, base64, core, os, tempfile, unittest

## `tests/test_vision_worker.py`
_Tests for trading/broker_sense/vision_worker.py — async deep chart-vision worker._
- **classes:** VWTest
- **functions:** `_rows(bar_ts)`
- **imports:** __future__, os, tempfile, time, trading, trading.broker_sense, unittest

## `tests/test_volume_profile.py`
_Tests for trading/broker_sense/volume_profile.py — VP / Value-Area engine._
- **classes:** TestProfile, TestSessionKey, TestMigration, TestFailedAuction, TestAbsorption, TestOrderPlan, TestFeatures
- **functions:** `_bar(ts, o, h, l, c, v)`; `_flat_at(price, n, vol, ts0, step)`
- **imports:** __future__, trading.broker_sense, unittest

## `tests/test_watchlist_study.py`
_Tests for trading/broker_sense/watchlist_study — W watchlist study funnel._
- **classes:** _FakeReader, _Iso, TestPropose, TestStudyRound, TestFuse, TestPatterns
- **imports:** pathlib, tempfile, time, trading.state, unittest

## `tests/test_worldmodel.py`
_tests/test_worldmodel.py — world-model + MuZero imagination planner._
- **functions:** `_series(drift, n, seed) -> pd.DataFrame`; `test_features_shape()`; `test_node_protocol_and_registry()`; `test_world_model_learns_dynamics()`; `test_planner_prefers_long_on_uptrend()`; `test_planner_manages_open_position()`; `test_pipeline_integration_with_planner()`
- **imports:** __future__, core.node_protocol, numpy, pandas, pytest, trading.brain.worldmodel

## `tools/gen_index.py`
_gen_index.py — auto-generate INDEX.md from the source tree (AST, stdlib only)._
- **functions:** `_sig(fn) -> str`; `_summarize(path) -> dict`; `_iter_py() -> list[str]`; `build() -> str`
- **imports:** __future__, ast, os

## `tools/gen_upstox_census.py`
_tools/gen_upstox_census.py — compile the Upstox discovered-features inventory._
- **functions:** `_load(name, default)`; `main() -> int`
- **imports:** __future__, datetime, json, pathlib, sys

## `tools/loop_keeper.py`
_tools/loop_keeper.py — RUNTIME self-heal for the trading stack (2026-07-10)._
- **functions:** `_alive(pattern) -> bool`; `_check() -> dict`; `_save_state(state) -> None`; `run_once() -> int`; `install_cron() -> None`
- **imports:** __future__, json, os, subprocess, sys, time

## `tools/orderbook_collector.py`
_Live Binance L2 order-book snapshot collector (no key)._
- **functions:** `snapshot(symbol, levels)`; `main(symbol, every)`
- **imports:** __future__, json, os, sys, time, urllib.request

## `tools/remote_login_browser.py`
_tools/remote_login_browser.py — a HEADFUL chromium the operator drives over VNC to complete_
- **functions:** `_on_term(_sig, _frame)`; `main() -> int`
- **imports:** __future__, os, pathlib, signal, sys, time, trading, trading.broker_sense.brokers

## `tools/skill_learnings.py`
_tools/skill_learnings.py — self-improving skills (Hermes-Agent / "self-improving Claude skills")._
- **functions:** `_path(skill) -> Path`; `skill_exists(skill) -> bool`; `read(skill) -> str`; `record(skill) -> dict`; `_count_entries(text) -> int`; `all_skills() -> list[str]`; `status() -> dict`; `_main() -> int`
- **imports:** __future__, argparse, os, pathlib, time

## `tools/test_runner.py`
_Parallel sharded test runner — runs each tests/test_*.py module in its OWN subprocess, N in_
- **functions:** `run_module(mod, timeout)`; `main()`
- **imports:** __future__, argparse, concurrent.futures, os, pathlib, re, subprocess, sys, time

## `trading/__init__.py`
_trading/ — Trading Execution Phase (T1+)._
- **imports:** __future__, trading.config

## `trading/advintel/__init__.py`
_trading/advintel/ — Advanced Intelligence (original Phase-T8 deferred items)._
- **imports:** __future__, trading.advintel.arbitrage, trading.advintel.fii_dii, trading.advintel.liquidations, trading.advintel.nse_announcements, trading.advintel.onchain, trading.advintel.portfolio_risk, trading.advintel.stress

## `trading/advintel/arbitrage.py`
_trading/advintel/arbitrage.py — Phase-T8 cross-exchange arbitrage scanner +_
- **classes:** CostModel, ArbitrageScanner
- **imports:** __future__, dataclasses, typing

## `trading/advintel/fii_dii.py`
_NSE FII/DII cash-market flows (Phase-T8 advanced intelligence)._
- **classes:** FiiDiiFlows
- **functions:** `_live_fetch() -> List[Dict]`; `_to_float(value) -> float`; `_normalize(row) -> Dict`
- **imports:** __future__, typing

## `trading/advintel/liquidations.py`
_Leverage liquidation heatmap aggregation._
- **classes:** LiquidationHeatmap
- **functions:** `_safe_float(value) -> Optional[float]`; `_default_live_fetcher(symbol) -> Dict[str, Any]`
- **imports:** __future__, os, requests, typing

## `trading/advintel/nse_announcements.py`
_NSE corporate announcements / corporate actions (Phase-T8 adv intel)._
- **classes:** NseAnnouncements
- **functions:** `_live_fetch() -> List[Dict]`; `classify(subject) -> str`; `_normalize(row) -> Dict`
- **imports:** __future__, typing

## `trading/advintel/onchain.py`
_Crypto on-chain intelligence: SOPR, MVRV (z-score), Fear & Greed._
- **classes:** OnChainMetrics
- **functions:** `_safe_float(value) -> Optional[float]`; `_default_live_fetcher(kind) -> Dict[str, Any]`
- **imports:** __future__, os, requests, typing

## `trading/advintel/portfolio_risk.py`
_Phase-T8: Portfolio risk & optimization (Riskfolio-Lib + PyPortfolioOpt)._
- **classes:** PortfolioRisk
- **functions:** `_as_returns_df(returns) -> pd.DataFrame`; `_portfolio_series(returns, weights) -> pd.Series`; `_is_degenerate(df) -> bool`; `var(returns, alpha, weights, per_asset)`; `cvar(returns, alpha, weights, per_asset)`; `kelly_fraction(returns, cap, half) -> dict`; `hrp_weights(returns) -> dict`; `max_drawdown(equity_or_returns) -> Optional[float]`; `portfolio_heat(positions, total_capital) -> dict`; `optimize(returns, objective) -> dict`
- **imports:** __future__, math, numpy, pandas, typing

## `trading/advintel/stress.py`
_trading/advintel/stress.py — Phase-T8: portfolio stress testing & scenario analysis._
- **classes:** Position, Scenario, StressTester
- **functions:** `_norm_asset_class(ac) -> str`; `_dir_sign(direction) -> int`; `_coerce_all(positions) -> list[Position]`; `list_scenarios() -> list[str]`; `custom_scenario(name, shocks) -> Scenario`; `_resolve_scenario(scenario) -> Scenario`; `_position_impact(p, shock) -> dict`; `_capital(positions) -> float`; `stress_test(positions, scenario) -> dict`; `scenario_analysis(positions, scenarios) -> dict`; `what_if(positions, asset_class_shocks) -> dict`; `_exposure_by_class(positions) -> dict`
- **imports:** __future__, dataclasses, json, numpy, typing

## `trading/alerts/__init__.py`
_trading/alerts/ — Alerts + Automation (Phase T7, Telegram-only)._
- **imports:** __future__, trading.alerts.channels, trading.alerts.commands, trading.alerts.config, trading.alerts.dedup, trading.alerts.dispatcher, trading.alerts.events, trading.alerts.formatter, trading.alerts.scheduler

## `trading/alerts/bot.py`
_trading/alerts/bot.py — live Telegram command bot (T7 §1)._
- **functions:** `build_application(router, config)`; `run_bot(router, config) -> None`
- **imports:** __future__, trading.alerts.commands, trading.alerts.config

## `trading/alerts/channels.py`
_trading/alerts/channels.py — TelegramChannel (T7 §1)._
- **classes:** TelegramChannel
- **functions:** `_requests_transport(url, payload) -> dict`
- **imports:** __future__, dataclasses, trading.alerts.config, trading.alerts.formatter, typing

## `trading/alerts/commands.py`
_trading/alerts/commands.py — Telegram command router (T7 §1)._
- **classes:** CommandRouter
- **functions:** `_fmt_positions(positions) -> str`; `_fmt_pnl(pnl) -> str`
- **imports:** __future__, typing

## `trading/alerts/config.py`
_trading/alerts/config.py — Telegram alert configuration (T7)._
- **classes:** AlertConfig
- **functions:** `_redact(secret) -> str`
- **imports:** __future__, dataclasses, os

## `trading/alerts/dedup.py`
_trading/alerts/dedup.py — smart alert deduplication (T7 §5)._
- **classes:** Deduplicator
- **imports:** __future__, dataclasses

## `trading/alerts/dispatcher.py`
_trading/alerts/dispatcher.py — AlertDispatcher (T7)._
- **classes:** AlertDispatcher
- **imports:** __future__, trading.alerts.dedup

## `trading/alerts/events.py`
_trading/alerts/events.py — the AlertEvent model + builders (T7)._
- **classes:** AlertEvent
- **functions:** `fill_event() -> AlertEvent`; `daily_pnl_event() -> AlertEvent`; `signal_event() -> AlertEvent`; `circuit_breaker_event() -> AlertEvent`; `kill_event() -> AlertEvent`
- **imports:** __future__, dataclasses, hashlib

## `trading/alerts/formatter.py`
_trading/alerts/formatter.py — render an AlertEvent to Telegram markdown (T7)._
- **functions:** `_fmt_value(v) -> str`; `to_telegram_markdown(event) -> str`
- **imports:** __future__

## `trading/alerts/scheduler.py`
_trading/alerts/scheduler.py — scheduled reports (T7 §3, §4)._
- **classes:** Report, ReportScheduler
- **imports:** __future__, dataclasses, datetime, typing

## `trading/altdata/__init__.py`
_(no summary)_

## `trading/altdata/onchain.py`
_AI-scientist idea #11 — on-chain + whale alt-data lane (live, free, keyless)._
- **classes:** OnChainAltData
- **functions:** `_get_json(url, timeout)`; `_get_text(url, timeout) -> str`; `_fetch_fear_greed() -> dict`; `_fetch_network() -> dict`; `_fetch_whale() -> dict`; `_default_fetchers() -> dict`; `_sat(x) -> float`; `_composite(fg, net, whale) -> float`
- **imports:** __future__, json, math, urllib.request

## `trading/antioverfit.py`
_Anti-overfit telemetry (CANON-43 / NNM-30)._
- **functions:** `_read_counter() -> dict`; `register_backtest(n) -> int`; `backtest_count() -> int`; `param_count(state) -> dict`; `_load_state() -> dict`; `telemetry(state, now) -> dict`
- **imports:** __future__, json, os, time

## `trading/brain/__init__.py`
_trading/brain/ — Brain upgrades (Phase T8.4+)._
- **imports:** __future__, trading.brain.continual, trading.brain.entryexit, trading.brain.experience, trading.brain.metalearn, trading.brain.news, trading.brain.observability, trading.brain.patterns, trading.brain.picking, trading.brain.pipeline, trading.brain.regime, trading.brain.researcher, trading.brain.rl_exit, trading.brain.selfeval, trading.brain.selfimprove, trading.brain.semantic, trading.brain.sentiment, trading.brain.skills

## `trading/brain/activity_feed.py`
_trading/brain/activity_feed.py — the brain's EPHEMERAL transparency feed (cross-process)._
- **functions:** `_load() -> dict`; `_save(d) -> None`; `_expire(events) -> list`; `emit(kind, title, detail) -> dict`; `peek(limit) -> list[dict]`; `drain(limit) -> list[dict]`; `status() -> dict`
- **imports:** __future__, threading, time

## `trading/brain/attribution.py`
_Per-trade feature attribution — WHICH data led to this decision and HOW MUCH._
- **functions:** `_background(closed_rows) -> list[list[float]]`; `explain_trade(trade, closed_rows) -> dict`
- **imports:** __future__, trading.brain.trade_features

## `trading/brain/boss.py`
_trading/brain/boss.py — the BOSS COMMAND ENGINE: talk to the brain like a boss._
- **classes:** BossRegistry
- **functions:** `directives() -> dict`; `_save(d) -> None`; `segment_enabled(market, segment) -> bool | None`; `all_segments(market) -> tuple`; `active_segments(market) -> list`; `segment_focus_active(market, segment) -> bool`; `target_for(market, segment) -> int`; `is_paused(market) -> bool`; `focus_of(market) -> str | None`; `mode() -> str`; `intensity() -> float`; `entry_policy(market, segment) -> dict`; `report_progress(market, segment, open_now) -> None`; `_norm_market(market) -> str`; `_bg(fn) -> None`; `set_segments(market, enable, disable) -> dict`; `_engine_segments() -> list`; `navigate_app(app, target) -> dict`; `set_target_open_trades(market, segment, target) -> dict`; `focus_segment(market, segment) -> dict`; `set_mode(mode) -> dict`; `set_intensity(level) -> dict`; `pause_trading(market) -> dict`; `resume_trading(market) -> dict`; `_set_paused(market, val) -> dict`; `research_online(topic) -> dict`; `add_goal(text) -> dict`; `get_status() -> dict`; `_looks_like_command(msg) -> bool`; `_market_in(msg) -> str`; `parse_deterministic(msg) -> list[dict]`; `parse_llm(msg) -> list[dict] | None`; `handle(message, history) -> dict | None`
- **imports:** __future__, json, re, threading, time, trading.brain

## `trading/brain/briefing.py`
_trading/brain/briefing.py — W8 daily morning briefing (owner goal 2026-07-07;_
- **functions:** `_ist_now() -> dt.datetime`; `due(hour_ist, minute_ist) -> bool`; `generate(deliver) -> dict`; `latest() -> dict`
- **imports:** __future__, datetime, time, trading

## `trading/brain/challenger.py`
_trading/brain/challenger.py — TabPFN-v2 challenger for the TradeOutcomeNet (2026-07-10)._
- **functions:** `_fold_indices(n, k)`; `_oof_eval(fit_predict, X, y) -> dict`; `_champion_fit_predict(Xtr, ytr, Xte, engine_used)`; `_tabpfn_fit_predict(Xtr, ytr, Xte)`; `duel(max_rows) -> dict`; `status() -> dict`
- **imports:** __future__, time

## `trading/brain/connectivity_monitor.py`
_trading/brain/connectivity_monitor.py — a light, always-on wiring watchdog._
- **functions:** `_py_files(sub) -> list`; `scan_async() -> dict`; `scan() -> dict`; `rebaseline() -> dict`
- **imports:** __future__, os, re, time

## `trading/brain/continual.py`
_trading/brain/continual.py — online/continual learning + experience replay (T8.5)._
- **classes:** OnlineNode, ReplayBuffer, ContinualLearner
- **functions:** `_row_dict(features, row) -> dict`; `_new_model()`; `replay_retrain(features, new_samples, buffer, rng) -> OnlineNode`; `clone_model(model)`
- **imports:** __future__, copy, core.node_protocol, dataclasses, numpy, river

## `trading/brain/credential_chat.py`
_trading/brain/credential_chat.py — capture a credential answer typed into Brain Chat._
- **functions:** `_secret_like(message) -> bool`; `_cred_shaped(value, message) -> bool`; `_pick(pending, message) -> dict`; `_synthesize(message) -> dict | None`; `_lone_value(message) -> str | None`; `_parse(message, fields) -> dict`; `try_capture(message, pending)`
- **imports:** __future__, re

## `trading/brain/credentials.py`
_trading/brain/credentials.py — the brain's ENCRYPTED credential vault + chat-request flow._
- **classes:** CredentialVault
- **functions:** `_fernet()`; `get_vault() -> CredentialVault`
- **imports:** __future__, os, stat, time

## `trading/brain/debate_gate.py`
_trading/brain/debate_gate.py — adversarial debate + verifier gate for trades (Pillar 18)._
- **classes:** DebateGate
- **functions:** `_proposition(symbol, direction, features) -> str`; `_rationale_steps(symbol, direction, features) -> list[str]`; `get_debate_gate() -> DebateGate`
- **imports:** __future__, cognition.society, cognition.verifier

## `trading/brain/decision_memory.py`
_Decision memory — every trade is a fully-provenanced EPISODE the brain recalls and learns from._
- **classes:** DecisionMemory
- **functions:** `_tokens(text) -> set`; `get_memory() -> DecisionMemory`
- **imports:** __future__, math, random, time, trading

## `trading/brain/discovery/__init__.py`
_Concept Discovery Engine — pure-self market-feature invention (idea-discovery mode)._
- **imports:** engine

## `trading/brain/discovery/encoders.py`
_Self-supervised market-window encoder — the net that INVENTS its own features._
- **classes:** WindowEncoder
- **functions:** `make_windows(series, w, stride) -> np.ndarray`
- **imports:** __future__, numpy, warnings

## `trading/brain/discovery/engine.py`
_Concept Discovery Engine — "idea discovery mode" (pure-self feature invention)._
- **classes:** ConceptDiscoveryEngine
- **imports:** __future__, encoders, json, manifold, namer, numpy, os, probe, time

## `trading/brain/discovery/manifold.py`
_Concept-space manifold: project the invented-feature space to 2-D and cluster it._
- **functions:** `project(Z, seed) -> dict`
- **imports:** __future__, numpy, warnings

## `trading/brain/discovery/namer.py`
_Name the discovered concepts — the auto-interp step._
- **functions:** `_window_stats(win) -> dict`; `_fallback_name(stats, fid) -> dict`; `name_feature(fid, windows, use_llm) -> dict`
- **imports:** __future__, json, numpy, re

## `trading/brain/discovery/probe.py`
_Read out the self-invented features: sparse-autoencoder probe over the encoder latent._
- **classes:** SAEProbe
- **imports:** __future__, numpy, warnings

## `trading/brain/discovery/signal.py`
_Live discovery signal registry — feeds self-invented features into trade decisions._
- **functions:** `_fit_bg(symbol, closes) -> None`; `signal(symbol, closes) -> dict`; `status() -> dict`
- **imports:** __future__, engine, numpy, threading, time

## `trading/brain/dreamer.py`
_trading/brain/dreamer.py — Counterfactual Dream-Trainer (invented 2026-07-10)._
- **functions:** `_pct(x) -> float | None`; `_dream_trade(r) -> dict | None`; `dream_once(lookback) -> dict`; `study_topics(max_topics) -> list[str]`; `status() -> dict`; `_candles_before(symbol, entry_ts, timeframe, limit)`; `imagine_replay(n_trades, timeframe) -> dict`
- **imports:** __future__, time

## `trading/brain/entryexit.py`
_trading/brain/entryexit.py — regime/pattern-gated entry + learned exit (T8.6)._
- **classes:** EntryExitPolicy
- **imports:** __future__, dataclasses, trading.brain.continual

## `trading/brain/experience.py`
_trading/brain/experience.py — episodic experience bank + CBR recall (T8.4)._
- **classes:** Recall, ExperienceBank
- **functions:** `_num(v) -> float`; `_as_dict(trade) -> dict`; `trade_vector(trade) -> list[float]`; `_outcome(trade) -> dict`
- **imports:** __future__, dataclasses, datetime, math, numpy

## `trading/brain/gate_tuner.py`
_trading/brain/gate_tuner.py — off-policy gate threshold tuning (2026-07-10)._
- **functions:** `_current_levers() -> dict`; `_dig(r)`; `_score_of(row, signal)`; `sweep(rows, signal) -> dict | None`; `tune_once(lookback) -> dict`; `status() -> dict`
- **imports:** __future__, time

## `trading/brain/gui/__init__.py`
_trading/brain/gui — the brain's computer-use / GUI-agent capability._
- **imports:** __future__, trading.brain.gui.actions, trading.brain.gui.agent, trading.brain.gui.perception, trading.brain.gui.reflection, trading.brain.gui.skills, trading.brain.gui.targets

## `trading/brain/gui/actions.py`
_trading/brain/gui/actions.py — the ACT layer of the computer-use agent._
- **classes:** ActionResult, ActionExecutor
- **imports:** __future__, dataclasses, json, urllib.error, urllib.request

## `trading/brain/gui/agent.py`
_trading/brain/gui/agent.py — the computer-use agent loop + its NodeProtocol face._
- **classes:** ComputerUseAgent, ComputerUseNode
- **functions:** `register_computer_use_agent(agent) -> ComputerUseNode`
- **imports:** __future__, core.node_protocol, numpy, trading.brain.gui.actions, trading.brain.gui.perception, trading.brain.gui.reflection, trading.brain.gui.skills, trading.brain.gui.targets

## `trading/brain/gui/perception.py`
_trading/brain/gui/perception.py — the SEE layer of the computer-use agent._
- **classes:** _ButtonHarvester, ChartReading, ChartReader, DomReader, OcrReader, Perception, DashboardPerception
- **functions:** `_has(mod) -> bool`; `capabilities() -> dict`; `_get(url, timeout) -> tuple[int, str]`; `_get_json(url, timeout) -> dict | None`; `read_html_controls(url) -> list[dict]`
- **imports:** __future__, dataclasses, html.parser, importlib.util, json, urllib.error, urllib.request

## `trading/brain/gui/reflection.py`
_trading/brain/gui/reflection.py — the LEARN layer: Reflexion-style self-critique._
- **classes:** Lesson, GuiReflector
- **functions:** `_tokens(text) -> set[str]`
- **imports:** __future__, dataclasses

## `trading/brain/gui/skills.py`
_trading/brain/gui/skills.py — the LEARN layer: a growing library of GUI macros._
- **classes:** GuiSkill, GuiSkillLibrary
- **functions:** `_tokens(text) -> set[str]`
- **imports:** __future__, dataclasses

## `trading/brain/gui/targets.py`
_trading/brain/gui/targets.py — the dashboards the computer-use agent operates._
- **classes:** DashboardTarget, TargetRegistry
- **functions:** `_own_base() -> str`; `_freq_base() -> str`; `default_targets() -> list[DashboardTarget]`
- **imports:** __future__, dataclasses, os

## `trading/brain/gui/web_screener.py`
_trading/brain/gui/web_screener.py — the brain's autonomous READ-ONLY web screener._
- **classes:** WebScreener
- **functions:** `_domain(url) -> str`; `get_screener() -> WebScreener`
- **imports:** __future__, os, re, time, urllib.parse

## `trading/brain/hypothesis.py`
_trading/brain/hypothesis.py — the brain's hypothesis → experiment → belief loop._
- **classes:** Hypothesis, ExperimentRunner, HypothesisLedger, HypothesisNode
- **functions:** `_metric_values(trades, metric) -> np.ndarray`; `_win_rate(vals) -> float`; `_bayes_ab(cond, ctrl, draws, seed) -> float`; `register_hypothesis_ledger(ledger) -> HypothesisNode`
- **imports:** __future__, core.node_protocol, dataclasses, hashlib, numpy

## `trading/brain/learn_loop.py`
_trading/brain/learn_loop.py — CONTINUOUS autonomous learning loop._
- **classes:** LearnLoop
- **functions:** `get_learn_loop() -> LearnLoop`; `ensure_started() -> None`
- **imports:** __future__, os, threading, time

## `trading/brain/learner.py`
_trading/brain/learner.py — the brain's self-directed LEARNING + SELF-EVALUATION._
- **classes:** KnowledgeLearner
- **functions:** `get_learner() -> KnowledgeLearner`
- **imports:** __future__, time

## `trading/brain/memory_search.py`
_trading/brain/memory_search.py — cross-session FULL-TEXT search over the brain's whole memory._
- **classes:** MemorySearch
- **functions:** `_rows_associative(d)`; `_rows_episodes(d)`; `_rows_reflections(d)`; `_rows_mind(d)`; `_rows_learnlog(d)`; `_md_sources()`; `_corpus_mtime() -> float`; `get_search() -> MemorySearch`
- **imports:** __future__, json, os, pathlib, sqlite3, time, trading

## `trading/brain/metalearn.py`
_trading/brain/metalearn.py — MAML-style meta-init for sample-efficiency (T8.5)._
- **classes:** MetaLearner
- **imports:** __future__, dataclasses, trading.brain.continual

## `trading/brain/mind_events.py`
_trading/brain/mind_events.py — the brain-wide ULTRA event bus behind Stream of Mind._
- **functions:** `_load() -> dict`; `_save(d) -> None`; `_expire(events) -> list`; `emit(kind, text) -> dict`; `since(last_id, limit) -> list[dict]`; `peek(limit) -> list[dict]`; `status() -> dict`
- **imports:** __future__, threading, time

## `trading/brain/news.py`
_trading/brain/news.py — autonomous news research + sentiment nodes (T8.7)._
- **classes:** NewsItem, NewsResearcher, NewsSentimentNode
- **functions:** `fetch_rss(url) -> list[NewsItem]`
- **imports:** __future__, core.node_protocol, dataclasses, os, re, trading.brain.sentiment

## `trading/brain/news_ingest.py`
_trading/brain/news_ingest.py — scheduled FREE-news ingestion into the brain (2026-07-10)._
- **functions:** `_feeds() -> list[str]`; `_universe() -> set[str]`; `_link_symbols(text, universe) -> list[str]`; `_hash(item) -> str`; `ingest_once(fetcher, force) -> dict`; `items_for(symbol, limit) -> list[dict]`; `status() -> dict`
- **imports:** __future__, hashlib, os, re, time

## `trading/brain/observability.py`
_trading/brain/observability.py — brain reasoning tracing (T8.8)._
- **classes:** Span, BrainTracer
- **imports:** __future__, contextlib, dataclasses, os, time

## `trading/brain/patterns.py`
_trading/brain/patterns.py — pattern + anomaly discovery (T8.6, reuse-first)._
- **classes:** PatternScanner
- **functions:** `matrix_profile(series, m)`; `find_anomalies(series, m, k) -> list[dict]`; `find_motifs(series, m, k) -> list[dict]`; `anomaly_score(series, m) -> float`; `candlestick_patterns(ohlcv, names) -> dict`; `candles_firing(ohlcv) -> dict`
- **imports:** __future__, numpy, pandas

## `trading/brain/perception.py`
_trading/brain/perception.py — read ANY document/image into structured text (Phase D)._
- **functions:** `_docling_convert(path) -> dict | None`; `_plain_read(path) -> dict | None`; `read_any(source) -> dict`; `status() -> dict`
- **imports:** __future__, json, pathlib

## `trading/brain/picking.py`
_trading/brain/picking.py — cross-sectional asset picking (T8.6)._
- **classes:** CrossSectionalRanker, GPLearnFactorMiner, AssetPicker
- **functions:** `_zscores(values) -> dict[str, np.ndarray]`
- **imports:** __future__, dataclasses, numpy, trading.strategy.guardrails, vendor.gplearn.genetic

## `trading/brain/pipeline.py`
_trading/brain/pipeline.py — end-to-end brain trading pipeline (T8.9 finale)._
- **classes:** BrainTradingPipeline
- **imports:** __future__, dataclasses, pandas, trading.brain.entryexit, trading.brain.experience, trading.brain.hypothesis, trading.brain.news, trading.brain.observability, trading.brain.patterns, trading.brain.regime, trading.brain.worldmodel, trading.strategy.features

## `trading/brain/psych_deeplob.py`
_DeepLOB price-direction prediction from recorded depth snapshots (CPU)._
- **functions:** `_snapshot_vec(row) -> list[float] | None`; `load_series(path) -> np.ndarray`; `make_samples(series) -> tuple[np.ndarray, np.ndarray]`; `_model()`; `train(epochs, lr, batch) -> dict`; `predict_prob_up(ring) -> float | None`
- **imports:** __future__, json, logging, numpy, pathlib

## `trading/brain/psychology.py`
_Trader-psychology engine: crowd sentiment from live order-book depth._
- **classes:** BookSnapshot, StoikovMicroprice, TraderPsychology
- **functions:** `_load_lob_features()`; `ring_to_frame(ring, levels) -> pd.DataFrame`; `detect_walls(snap, band, min_frac) -> dict`; `gap_map(snap, depths) -> dict`; `depth_slope_bias(snap) -> float`; `snapshot_features(snap) -> list[float]`; `load_depth_features(pair, market, segment) -> tuple`; `evaluate_ring(ring, micro, weights) -> dict | None`; `get_engine() -> TraderPsychology`; `psych_columns(result) -> dict`
- **imports:** __future__, collections, dataclasses, importlib.util, json, logging, math, numpy, pandas, pathlib, threading, time, typing

## `trading/brain/regime.py`
_trading/brain/regime.py — market-regime detection + regime-gated activation (T8.6)._
- **classes:** RegimeModel, RegimeGate
- **functions:** `_observations(ohlcv) -> np.ndarray`
- **imports:** __future__, dataclasses, hmmlearn, numpy, pandas

## `trading/brain/regime_hub.py`
_CORTEX B4 — Brain hub: the meta-controller (design §1 T7)._
- **classes:** JumpRegime, DriftSentry, _EwmaDrift, ChampionManager, HubDecision, BrainHub
- **functions:** `_feed(det, x) -> bool`
- **imports:** __future__, core.trust, dataclasses, numpy, vendor.dfa, warnings

## `trading/brain/researcher.py`
_trading/brain/researcher.py — Phase-T8 (deferred A2): lightweight autonomous web research._
- **classes:** AutonomousResearcher
- **functions:** `_default_searcher(query) -> list[dict]`; `_default_summarizer(prompt) -> str`
- **imports:** __future__

## `trading/brain/rl_exit.py`
_trading/brain/rl_exit.py — Phase-T8 deferred A3: RL exit policy (tabular Q-learning)._
- **classes:** QLearningExit
- **functions:** `_r_bucket(unrealized_r) -> int`; `_bars_bucket(bars_held) -> int`; `_state_key(unrealized_r, bars_held, anomaly_high) -> tuple`; `deep_rl_available() -> dict`
- **imports:** __future__, numpy

## `trading/brain/rnd.py`
_trading/brain/rnd.py — the AUTONOMOUS R&D DRIVE: the brain invents its own new_
- **functions:** `_load() -> dict`; `_save(d) -> None`; `_interval() -> float`; `_pick_topic(d) -> tuple[str, str]`; `_invent_from(topic, summary) -> dict`; `run_once() -> dict`; `maybe_run() -> dict | None`; `status() -> dict`
- **imports:** __future__, json, os, random, re, time, trading.brain

## `trading/brain/selfeval.py`
_trading/brain/selfeval.py — auto-quiz + Reflexion self-critique (T8.5)._
- **classes:** QuizResult, AutoQuiz
- **functions:** `reflect(trade, predicted_label, actual_label) -> str`; `reflect_and_store(trade, predicted_label, actual_label, semantic_memory) -> dict`
- **imports:** __future__, dataclasses, numpy, trading.brain.continual

## `trading/brain/selfimprove.py`
_trading/brain/selfimprove.py — self-improvement (T8.8)._
- **classes:** SelfImprover, DSPyOptimizer
- **imports:** __future__, dataclasses, numpy, os

## `trading/brain/semantic.py`
_trading/brain/semantic.py — semantic (text) memory via mem0 (T8.4)._
- **classes:** SemanticMemory
- **functions:** `_env_truthy(name) -> bool`
- **imports:** __future__, dataclasses, os, re

## `trading/brain/sentiment.py`
_trading/brain/sentiment.py — financial news sentiment scoring (T8.7)._
- **classes:** SentimentScorer
- **imports:** __future__, dataclasses, vendor.vaderSentiment.vaderSentiment

## `trading/brain/skills.py`
_trading/brain/skills.py — growing skill library (T8.8, Voyager pattern)._
- **classes:** Skill, SkillLibrary
- **imports:** __future__, dataclasses, trading

## `trading/brain/surface.py`
_trading/brain/surface.py — W2 scientific-method rails for EVERY self-tuning optimizer._
- **functions:** `owner_of(knob) -> str | None`; `can_write(optimizer, knob) -> tuple[bool, str]`; `mode(optimizer) -> str`; `set_mode(optimizer, new_mode) -> dict`; `_window_days() -> float`; `_one_variable_enabled() -> bool`; `_scope_of(knob) -> str`; `_recent_changes(optimizer, since_s) -> list[dict]`; `_append_ledger(entry) -> None`; `record_change(optimizer) -> dict`; `status() -> dict`
- **imports:** __future__, fnmatch, time, trading

## `trading/brain/track_record.py`
_trading/brain/track_record.py — W7 track records + rule-of-three + meta-articles._
- **functions:** `_store() -> dict`; `bump(actor) -> dict`; `mark_supervised_success(actor) -> dict`; `rule_of_three(actor) -> dict`; `trust(actor) -> dict`; `meta_note(actor) -> bool`; `drain_meta_queue(max_items) -> int`; `report_card() -> dict`
- **imports:** __future__, time, trading

## `trading/brain/trade_features.py`
_trading/brain/trade_features.py — trade rows → ML network inputs → outcome output._
- **classes:** _NumpyLogReg, _TabPFNWrap, TradeOutcomeNet
- **functions:** `_f(v, default)`; `_is_crypto(trade) -> bool`; `_brain_telemetry(trade) -> dict`; `_entry_hour(trade) -> int | None`; `_regime(trade) -> str`; `trade_feature_row(trade) -> list[float]`; `_won(trade) -> int`; `get_outcome_net(closed_rows) -> TradeOutcomeNet`
- **imports:** __future__, datetime, math

## `trading/brain/ultra.py`
_trading/brain/ultra.py — glue singleton for the brain ultra-upgrade (Phases A–E)._
- **functions:** `file_memory()`; `remember(name, description, body, type) -> dict`; `recall(query, k) -> list[dict]`; `set_llm_node(node) -> None`; `status() -> dict`
- **imports:** __future__, pathlib

## `trading/brain/vision/__init__.py`
_trading/brain/vision — the brain's ultra-advanced eyes + visual memory (Ocular Cortex)._

## `trading/brain/vision/computer_use.py`
_trading/brain/vision/computer_use.py — the FREE computer-use loop (cloned, read-only)._
- **classes:** GuardViolation, Action, ComputerUseAgent
- **functions:** `_control_forbidden(text) -> bool`; `_parse_action(text) -> Action`; `_is_forbidden(action) -> bool`; `_find_control(page, target)`; `get_agent() -> ComputerUseAgent`
- **imports:** __future__, dataclasses, json, os, re, time, trading.brain.vision.ocular_cortex

## `trading/brain/vision/fast_nav.py`
_trading/brain/vision/fast_nav.py — FAST + ACCURATE navigation planner (2026-07-10)._
- **functions:** `_tokens(s) -> set[str]`; `_state(name, default)`; `_score(target_toks, text, url, seen) -> float`; `_method_fails(stats, app, target, method, key) -> int`; `plan(app, target, max_candidates) -> list[dict]`; `record(app, target, method, key, ok, latency_ms) -> None`; `status() -> dict`
- **imports:** __future__, math, re, time

## `trading/brain/vision/free_eyes.py`
_trading/brain/vision/free_eyes.py — the brain's FREE, 24/7, never-rate-limited eyes._
- **classes:** Glance, FreeEyes
- **functions:** `_ocr_pool()`; `_ocr_safe(shot) -> list`; `_ocr_engine()`; `_ocr_read(png_bytes) -> list[dict]`; `_ocr_row(box, txt) -> Optional[dict]`; `_norm(s) -> str`; `_tok_hit(tok, pool) -> bool`; `_score_match(target, label) -> float`
- **imports:** __future__, dataclasses, re, time, typing

## `trading/brain/vision/grounded_eyes.py`
_trading/brain/vision/grounded_eyes.py — LOCAL grounded eyes (invent-beyond #1)._
- **classes:** GroundedEyes
- **functions:** `_weights_path() -> Optional[str]`; `get_grounded() -> Optional[GroundedEyes]`; `status() -> dict`
- **imports:** __future__, io, os, threading, time, typing

## `trading/brain/vision/human_ui.py`
_trading/brain/vision/human_ui.py — the brain's human-like eyes→brain→hand→memory loop._
- **classes:** Perception, HumanUI
- **functions:** `_extract_json(raw) -> Any`
- **imports:** __future__, dataclasses, json, re, time, trading.brain.vision.computer_use, typing

## `trading/brain/vision/ocular_cortex.py`
_trading/brain/vision/ocular_cortex.py — the Ocular Cortex: ultra-advanced eyes + memory._
- **classes:** PerceptualFrame, LayoutMemory, OcularCortex
- **functions:** `_norm_label(s) -> str`; `_label_set(controls) -> set[str]`; `_jaccard(a, b) -> float`; `_fingerprint(controls) -> str`; `_vision_online() -> bool`; `_known_kinds()`; `_extract_from_page(page)`; `get_cortex() -> OcularCortex`
- **imports:** __future__, dataclasses, hashlib, time, trading

## `trading/brain/worldmodel.py`
_trading/brain/worldmodel.py — learned market world-model + imagination planner._
- **classes:** MarketWorldModel, _MinMax, _MCTSNode, PositionState, ImaginationPlanner, WorldModelNode
- **functions:** `market_features(ohlcv) -> np.ndarray`; `_feature_matrix(ohlcv) -> np.ndarray`; `build_planner(ohlcv) -> ImaginationPlanner`; `register_world_model() -> WorldModelNode`
- **imports:** __future__, core.node_protocol, dataclasses, math, numpy, pandas

## `trading/broker_sense/__init__.py`
_trading/broker_sense — the Broker-Sense Funnel (owner-approved 2026-07-05)._

## `trading/broker_sense/account_watchlist.py`
_trading/broker_sense/account_watchlist.py — mirror OPEN trades into a dedicated_
- **functions:** `open_nse_symbols() -> list[str]`; `plan_sync(desired, already) -> dict`; `_load_state() -> dict`; `_save_state(synced, report) -> None`; `status() -> dict`; `_open_ui(sessions, broker)`; `_logged_in(ui) -> bool`; `apply_sync() -> dict`; `_add_symbol(ui, sym) -> bool`; `_ensure_watchlist(ui) -> bool`; `_remove_symbol(ui, sym) -> bool`
- **imports:** __future__, os, time, trading, typing

## `trading/broker_sense/app_explorer.py`
_trading/broker_sense/app_explorer.py — use EVERY feature a trading app offers (decision #6)._
- **classes:** FeatureCatalog
- **functions:** `classify_feature(label) -> str`; `get_catalog() -> FeatureCatalog`; `_crawl_page(app, pg, where, cat, symbol) -> dict`; `explore(broker, sessions) -> dict`; `human_checklist(symbol, market, sessions) -> dict`
- **imports:** __future__, time, trading, trading.broker_sense.brokers, trading.broker_sense.learning_columns

## `trading/broker_sense/app_school.py`
_trading/broker_sense/app_school.py — the brain LEARNS to drive a broker app (self-driving-car_
- **classes:** AppMap, AppSchool
- **functions:** `market_status(broker) -> dict`; `_min_quote_volume() -> float`; `_ccxt_exchange(segment)`; `get_school() -> AppSchool`
- **imports:** __future__, datetime, os, time, trading, trading.broker_sense.brokers, zoneinfo

## `trading/broker_sense/binance_ai_select.py`
_trading/broker_sense/binance_ai_select.py — Binance's built-in "AI Select" recommendations (P3+)._
- **functions:** `enabled() -> bool`; `_get_json(url)`; `_items(typ) -> list[dict]`; `picks() -> list[dict]`; `selected_bases() -> set`; `is_ai_selected(symbol) -> dict`; `clear_cache() -> None`
- **imports:** __future__, json, os, threading, time, urllib.request

## `trading/broker_sense/binance_catalysts.py`
_trading/broker_sense/binance_catalysts.py — Binance-native event catalysts (P2, compute-offload)._
- **functions:** `enabled() -> bool`; `_get_json(url)`; `_articles(cat, n)`; `announcements(cat, n) -> list[dict]`; `_extract_symbols(title) -> list[str]`; `_seen_path()`; `_load_seen() -> dict`; `_save_seen(seen) -> None`; `refresh_new_listings() -> dict`; `new_listings(max_age_s) -> list[dict]`; `catalyst(symbol) -> dict`
- **imports:** __future__, json, os, re, time, trading, urllib.request

## `trading/broker_sense/binance_options.py`
_trading/broker_sense/binance_options.py — Binance options IV/skew regime gauge (P4)._
- **functions:** `enabled() -> bool`; `_get_json(url)`; `_mark()`; `_f(v)`; `_parse(sym)`; `iv_summary(underlying) -> dict`; `regime() -> dict`; `clear_cache() -> None`
- **imports:** __future__, json, os, threading, time, urllib.request

## `trading/broker_sense/binance_orderflow.py`
_trading/broker_sense/binance_orderflow.py — Binance-computed order-flow & positioning features._
- **functions:** `enabled() -> bool`; `_norm(symbol) -> str`; `_get_json(url)`; `_cached(key, url)`; `_data(path, symbol)`; `_f(v)`; `_liq_pressure(symbol) -> dict`; `features(symbol) -> dict`; `signal(symbol) -> dict`; `clear_cache() -> None`
- **imports:** __future__, json, os, threading, time, trading.broker_sense.binance_stream, urllib.parse, urllib.request

## `trading/broker_sense/binance_sectors.py`
_trading/broker_sense/binance_sectors.py — Binance-native sector taxonomy + rotation (P3)._
- **functions:** `enabled() -> bool`; `_get_json(url)`; `_base_tags() -> dict`; `_base_of(symbol) -> str`; `tags_for(symbol) -> list[str]`; `sector_rotation() -> list[dict]`; `sector_signal(symbol) -> dict`; `clear_cache() -> None`
- **imports:** __future__, json, os, threading, time, urllib.request

## `trading/broker_sense/binance_stream.py`
_trading/broker_sense/binance_stream.py — Binance all-market WEBSOCKET mirror (compute-offload)._
- **classes:** BinanceUniverseMirror
- **functions:** `enabled() -> bool`; `_f(v)`; `_i(v)`; `get_mirror() -> BinanceUniverseMirror`
- **imports:** __future__, asyncio, collections, json, os, threading, time, trading

## `trading/broker_sense/binance_watchlist.py`
_trading/broker_sense/binance_watchlist.py — mirror OPEN crypto trades into the REAL_
- **functions:** `_flat(pair) -> str`; `open_crypto_symbols() -> dict`; `_load_state() -> dict`; `_save_state(synced, report) -> None`; `status() -> dict`; `_symbol_url(sym, segment) -> str`; `_open_symbol_ui(sessions, sym, segment)`; `_star_state(ui, sym) -> bool | None`; `_set_star(ui, sym, want) -> bool`; `apply_sync() -> dict`; `_close(pg) -> None`
- **imports:** __future__, os, re, time, trading, trading.broker_sense.account_watchlist

## `trading/broker_sense/book_monitor.py`
_trading/broker_sense/book_monitor.py — non-invasive screen-mirror order-book reader._
- **classes:** BookMonitor
- **functions:** `_shot_dir()`
- **imports:** __future__, hashlib, os, re, time, trading, trading.broker_sense, trading.broker_sense.brokers

## `trading/broker_sense/broker_features.py`
_trading/broker_sense/broker_features.py — USE the broker apps' OWN built-in pickers._
- **classes:** FeaturePerf
- **functions:** `current_regime() -> str`; `_classify_label(label)`; `discovered_pickers(broker) -> list[dict]`; `features_for(broker, segment) -> list[dict]`; `_route(broker, feat) -> str`; `read_feature(broker, feat, sessions) -> list[dict]`; `_slice_by_kind(universe, kind, limit) -> list`; `_max_workers() -> int`; `read_all_features(broker, sessions) -> dict`; `_detect_ignitions(broker, feature_map) -> list`; `recent_igniters(broker) -> dict`; `get_perf() -> FeaturePerf`; `fuse(broker, feature_map) -> list[dict]`; `_record_snapshots(broker, feature_map) -> None`; `credit_symbol(broker, symbol) -> list`; `new_entries(broker, feature, current_syms) -> list`; `cross_broker_signals() -> dict`; `order_preview(broker, symbol, sessions) -> dict`; `watchlist_remember(broker, symbols, sessions) -> dict`; `live_movers(broker, sessions) -> list[dict]`; `invent_preset(broker, cycle) -> dict`; `invented_presets(broker) -> dict`; `status() -> dict`
- **imports:** __future__, concurrent.futures, os, re, time, trading

## `trading/broker_sense/brokers.py`
_trading/broker_sense/brokers.py — broker-app registry + ROLE ENFORCEMENT in code._
- **classes:** BrokerApp, RoleViolation
- **functions:** `_overrides() -> dict`; `set_real_nse_broker(name) -> dict`; `real_broker(market) -> str | None`; `screening_brokers(market) -> list[BrokerApp]`; `assert_can_execute(name, market) -> None`; `status() -> dict`
- **imports:** __future__, dataclasses, trading

## `trading/broker_sense/chart_render.py`
_trading/broker_sense/chart_render.py — draw candle charts locally, two flavors._
- **functions:** `_shot_dir()`; `_out(symbol, tf, tag) -> str`; `plain(rows, symbol, tf, out_path) -> str | None`; `_frame(rows)`; `annotated(rows, symbol, tf, out_path) -> str | None`; `_overlay_volume_profile(ax, rows) -> None`
- **imports:** __future__, os, time, trading

## `trading/broker_sense/chart_vision.py`
_trading/broker_sense/chart_vision.py — screenshot the candles, read them, delete them._
- **classes:** ChartVision
- **functions:** `_shot_dir()`; `wipe() -> int`; `_tv_symbol(symbol, market) -> str`
- **imports:** __future__, hashlib, os, time, trading, trading.broker_sense, trading.broker_sense.brokers

## `trading/broker_sense/chart_vlm.py`
_trading/broker_sense/chart_vlm.py — Lane B of the vision cascade: read the chart IMAGE_
- **classes:** ChartVLMNode
- **functions:** `_parse(raw) -> dict | None`; `_norm(obj) -> dict`; `read_chart(images, symbol, tf) -> dict | None`; `register_chart_vlm_node() -> ChartVLMNode`
- **imports:** __future__, core.node_protocol, json, re

## `trading/broker_sense/chart_yolo.py`
_trading/broker_sense/chart_yolo.py — Lane C of the vision cascade: YOLOv8 chart-pattern detection._
- **classes:** ChartYoloNode
- **functions:** `available() -> bool`; `_model()`; `detect(image) -> dict | None`; `detect_and_cache(symbol, image) -> dict | None`; `cached(symbol) -> dict | None`; `register_chart_yolo_node() -> ChartYoloNode`
- **imports:** __future__, core.node_protocol, math, os

## `trading/broker_sense/cnn_direction.py`
_trading/broker_sense/cnn_direction.py — candle-IMAGE → direction (savers B, F)._
- **classes:** CandleDirectionModel, CandleVisionNode
- **functions:** `_build_net()`; `get_model() -> CandleDirectionModel`; `llm_escalate(symbol, tf, candles) -> dict | None`; `register_candle_vision_node() -> CandleVisionNode`
- **imports:** __future__, core.node_protocol, numpy, os

## `trading/broker_sense/curiosity.py`
_trading/broker_sense/curiosity.py — curiosity-driven feature discovery on app screens_
- **functions:** `_registry()`; `_field_stats() -> dict`; `curiosity(name, stats) -> dict`; `rank() -> list[dict]`; `harvest(max_accept) -> dict`; `status() -> dict`
- **imports:** __future__, math, time, trading

## `trading/broker_sense/data_failsafe.py`
_trading/broker_sense/data_failsafe.py — the owner's rule 4: NEVER skip a trade for data._
- **functions:** `_rss_bytes() -> int`; `_guard_ram()`; `_cached(kind, symbol, fn)`; `_ccxt_ex()`; `_base(symbol) -> str`; `_ui_only() -> bool`; `quote(symbol, market) -> dict | None`; `top_of_book(symbol, market) -> dict | None`; `ohlcv(symbol, market, timeframe, limit) -> list | None`; `_nse_ohlcv(symbol, timeframe, limit) -> list | None`; `consistent(gui_value, api_value, tol_pct) -> bool`
- **imports:** __future__, os, time

## `trading/broker_sense/data_sources.py`
_trading/broker_sense/data_sources.py — per-broker PUBLIC-vs-ACCOUNT data-source switch._
- **functions:** `_load() -> dict`; `public_enabled(broker) -> bool`; `set_public(broker, on) -> dict`; `account_first(broker) -> bool`; `primary_broker(market) -> str`; `set_primary(market, broker) -> dict`; `status() -> dict`
- **imports:** __future__, trading

## `trading/broker_sense/direct_feeds.py`
_trading/broker_sense/direct_feeds.py — record market-data routes for WEBSOCKET-ONLY feeds that a_
- **functions:** `has_feed(broker, kind) -> bool`; `verify_and_record(broker, kind, app_map) -> bool`
- **imports:** __future__, asyncio, json

## `trading/broker_sense/exec_adapter.py`
_trading/broker_sense/exec_adapter.py — APIs are used ONLY here (owner's step 8)._
- **classes:** ExecAdapter
- **imports:** __future__, os, trading.broker_sense.brokers

## `trading/broker_sense/fast_candles.py`
_trading/broker_sense/fast_candles.py — direction from OHLCV DATA, not chart screenshots._
- **functions:** `_ema(vals, n) -> float`; `_rsi(closes, n) -> float`; `_clamp(x, lo, hi) -> float`; `direction_from_ohlcv(rows) -> dict`; `_ohlcv_fast(sym, market, tf) -> list | None`; `read(picks, market, timeframes, deadline) -> dict[str, dict[str, dict]]`
- **imports:** __future__, time, trading.broker_sense

## `trading/broker_sense/funnel.py`
_trading/broker_sense/funnel.py — the cascade orchestrator (savers B + I: every cycle_
- **classes:** BrokerSenseFunnel
- **functions:** `_budget_s() -> float`; `_unlimited_opens() -> bool`; `_unlimited_budget() -> float`; `_unlimited_min_qv() -> float`; `_fast_book(symbol, market) -> dict`; `_fast_candles() -> bool`; `_login_brokers(market) -> list[str]`; `_vote(chart) -> tuple[str, float]`
- **imports:** __future__, os, time, trading, trading.broker_sense, trading.broker_sense.app_explorer, trading.broker_sense.book_monitor, trading.broker_sense.exec_adapter, trading.broker_sense.ocular_perception, trading.broker_sense.screeners, trading.broker_sense.watchlist

## `trading/broker_sense/human_handoff.py`
_trading/broker_sense/human_handoff.py — mid-session human-CAPTCHA handoff._
- **functions:** `enabled() -> bool`; `_vnc_enabled() -> bool`; `_display() -> str`; `_max_wait() -> float`; `_poll_interval() -> float`; `_check_interval() -> float`; `_state_path()`; `_read() -> dict`; `_write(data) -> None`; `_now() -> float`; `_vnc(op) -> str`; `_vnc_up() -> tuple[bool, str]`; `_alert(broker, url) -> None`; `_any_other_active(brokers, exclude) -> bool`; `_activate(broker, url) -> None`; `_deactivate(broker) -> None`; `is_challenge(page) -> bool`; `guard(broker, page) -> bool`; `_resume_flag_path(broker)`; `_resume_requested(broker) -> bool`; `request_resume(broker) -> dict`; `clear_resume(broker) -> None`; `take_control(broker) -> dict`; `stop_control() -> dict`; `status() -> dict`
- **imports:** __future__, json, os, subprocess, time, trading

## `trading/broker_sense/indicator_fusion.py`
_trading/broker_sense/indicator_fusion.py — ultra-advanced multi-timeframe indicator fusion._
- **functions:** `_ohlc(rows)`; `_sma(vals, n) -> float`; `_ema_series(vals, n) -> list[float]`; `_true_ranges(h, l, c) -> list[float]`; `_wilder(vals, n) -> float`; `_atr(h, l, c, n) -> float`; `_adx(h, l, c, n) -> tuple[float, float, float]`; `_supertrend(h, l, c, n, mult) -> tuple[int, float]`; `_parabolic_sar(h, l, c, af0, af_max) -> tuple[int, float]`; `_macd(c) -> tuple[float, float, float]`; `_bollinger(c, n, k) -> tuple[float, float, float]`; `_stoch_rsi(c, n) -> float`; `indicators_from_ohlcv(rows) -> dict`; `_fetch(sym, market, tf, bars) -> list | None`; `_meta_label(confluence, direction, market, symbol) -> dict`; `_barriers(direction, price, atr, k_stop, k_tp, time_bars) -> dict`; `fuse(symbol, market, timeframes, vision) -> dict`
- **imports:** __future__, math, os, time, trading.broker_sense, trading.broker_sense.fast_candles

## `trading/broker_sense/interception.py`
_trading/broker_sense/interception.py — the brain's peripheral nerve: capture the broker_
- **classes:** EndpointRegistry, NetworkRecorder
- **functions:** `_url_pattern(url) -> str`; `classify(url, body) -> str`; `_sample_keys(body) -> list[str]`; `get_recorder() -> NetworkRecorder`
- **imports:** __future__, time, trading, urllib.parse

## `trading/broker_sense/learning_columns.py`
_trading/broker_sense/learning_columns.py — discovered app data → DYNAMIC learning columns._
- **classes:** ColumnRegistry
- **functions:** `_norm(label) -> str`; `get_registry() -> ColumnRegistry`; `discover_from_text(source, text) -> list[str]`
- **imports:** __future__, re, time, trading

## `trading/broker_sense/live_browser.py`
_trading/broker_sense/live_browser.py — an interactive HEADLESS browser streamed to the_
- **classes:** _Session, LiveBrowser
- **functions:** `get_live_browser() -> LiveBrowser`
- **imports:** __future__, queue, threading, time, trading

## `trading/broker_sense/live_mirror.py`
_trading/broker_sense/live_mirror.py — M: LIVE video screen mirror (Pillar 27 batch)._
- **functions:** `_env(name, default) -> str`; `enabled() -> bool`; `display() -> str`; `available() -> dict`; `frames(fps)`
- **imports:** __future__, os, subprocess, threading

## `trading/broker_sense/ocular_perception.py`
_trading/broker_sense/ocular_perception.py — the funnel's NEW eyes (Phase-2 deep read)._
- **classes:** OcularPerception
- **functions:** `_vision_quota() -> int`; `_flag(name, default) -> bool`; `_flatten_numbers(obj, prefix) -> str`; `_summarize_book(ob) -> dict`
- **imports:** __future__, os, time, trading.broker_sense.learning_columns

## `trading/broker_sense/run_account_watchlist.py`
_trading/broker_sense/run_account_watchlist.py — keep the Upstox 'Brain-Open' watchlist_
- **functions:** `_nse_open() -> bool`; `main() -> int`
- **imports:** __future__, datetime, os, sys, time

## `trading/broker_sense/run_app_school.py`
_trading/broker_sense/run_app_school.py — run ONE App Driving School crawl in its own process._
- **functions:** `main() -> int`
- **imports:** __future__, json, sys

## `trading/broker_sense/run_broker_features.py`
_trading/broker_sense/run_broker_features.py — read every built-in broker picker in one process._
- **functions:** `main() -> int`
- **imports:** __future__, json, sys

## `trading/broker_sense/run_funnel_loop.py`
_run_funnel_loop.py — the Broker-Sense driver (replaces the wedged run_brain_loop)._
- **functions:** `_next_bar_close() -> float`; `_nse_open() -> bool`; `main() -> int`
- **imports:** __future__, datetime, os, sys, time

## `trading/broker_sense/run_school_monitor.py`
_trading/broker_sense/run_school_monitor.py — DEDICATED App-Driving-School learning monitor._
- **functions:** `_explore_symbol(broker) -> dict`; `_market_open(broker) -> bool`; `_coverage(broker) -> dict`; `_log(msg) -> None`; `main() -> int`; `_snapshot(rounds, done, stale) -> None`
- **imports:** __future__, json, sys, time, trading, trading.broker_sense.app_school

## `trading/broker_sense/run_upstox_focus.py`
_trading/broker_sense/run_upstox_focus.py — drive the Upstox App School to 100%._
- **functions:** `_coverage() -> dict`; `_nse_open() -> bool`; `_log(msg) -> None`; `main() -> int`
- **imports:** __future__, json, subprocess, sys, time

## `trading/broker_sense/screen_mirror.py`
_trading/broker_sense/screen_mirror.py — live screen-mirror of the brain's OWN browsers._
- **functions:** `enabled() -> bool`; `_dir(broker)`; `_min_interval() -> float`; `record(broker, page) -> bool`; `record_bytes(broker, jpeg) -> bool`; `log_action(broker, page, act, detail) -> None`; `_append_action(broker, row) -> None`; `frame(broker) -> bytes | None`; `actions(broker, limit) -> list[dict]`; `status() -> dict`
- **imports:** __future__, json, os, time, trading, typing

## `trading/broker_sense/screeners.py`
_trading/broker_sense/screeners.py — the whole-universe screen runs on OTHER people's servers._
- **classes:** PresetStore
- **functions:** `_crypto_pair(raw) -> str | None`; `_tv_query(preset, market, limit)`; `tv_screen(market, preset, limit) -> list[dict]`; `_parse_screen_page(broker, sessions, url) -> list[dict]`; `app_screen(broker, sessions) -> list[dict]`; `account_screen(broker, sessions) -> list[dict]`; `screen_all(market, sessions) -> list[dict]`
- **imports:** __future__, re, time, trading, trading.broker_sense.brokers

## `trading/broker_sense/sessions.py`
_trading/broker_sense/sessions.py — persistent logged-in broker browser sessions (saver H)._
- **classes:** SessionManager
- **functions:** `_sess_path(broker)`; `has_session(broker) -> bool`; `_looks_like_login(pg) -> bool`; `is_human_challenge(pg) -> bool`; `_challenge_present(pg) -> bool`; `_otp_attrs_are_code_box(attrs) -> bool`; `_otp_input(el) -> bool`; `_click_login(pg)`; `get_sessions() -> SessionManager`
- **imports:** __future__, os, re, stat, time, trading, trading.broker_sense.brokers

## `trading/broker_sense/stock_xray.py`
_trading/broker_sense/stock_xray.py — the Upstox Stock X-Ray: one FUSED per-stock snapshot._
- **functions:** `_oa()`; `_is_option(symbol, segment) -> bool`; `_opt_exchange(symbol, exchange, segment) -> str`; `demand_supply_zones(candles) -> dict`; `_cluster(levels, price) -> list[dict]`; `circuit_bands(quote) -> dict`; `depth_imbalance(depth) -> dict`; `capture(symbol, exchange, segment) -> dict`; `_summary(snap) -> dict`; `_visual_capture(symbol, sessions) -> dict`; `_persist(symbol, snap) -> None`; `get_xray(symbol) -> Optional[dict]`; `latest(limit) -> list[dict]`; `capture_on_open(symbol, exchange, segment) -> None`; `_to_list_candles(rows) -> list`; `_slim_candle(r) -> Optional[dict]`; `_f(d, key) -> Optional[float]`
- **imports:** __future__, time, trading, typing

## `trading/broker_sense/trade_columns.py`
_trading/broker_sense/trade_columns.py — turn the App Driving School's discovered app labels_
- **functions:** `_norm(label) -> str`; `journal_fields() -> set`; `discovered_labels() -> list`; `propose() -> dict`; `accepted() -> list`; `accept(column) -> dict`; `reject(column) -> dict`
- **imports:** __future__, re, trading

## `trading/broker_sense/ui_crawl.py`
_trading/broker_sense/ui_crawl.py — the EYES' symbol-page crawl (owner goal_
- **functions:** `_binance_url(symbol) -> str`; `_upstox_url(symbol) -> str`; `_page_url(broker, symbol) -> str`; `_expected_info_gain(sym, now, visits, ui_cov) -> float`; `_due_symbols(symbols, k) -> list[str]`; `_mark_visited(symbol, ok) -> None`; `crawl_once(sessions, symbols) -> dict`; `status() -> dict`
- **imports:** __future__, os, re, time, trading

## `trading/broker_sense/ui_data.py`
_trading/broker_sense/ui_data.py — UI-ONLY market data (owner goal 2026-07-07)._
- **functions:** `enabled() -> bool`; `_fresh_shortlist_cov(shortlist, fresh_s) -> float | None`; `maybe_auto_flip(shortlist, min_hit_rate, min_symbols) -> dict`; `_norm_symbol(raw) -> str`; `_interval_from(params, url) -> str | None`; `_parse_rows(body) -> list | None`; `feed_capture(broker, url, body) -> bool`; `_candidates(symbol) -> list[str]`; `ui_ohlcv(symbol, timeframe, limit) -> list | None`; `coverage() -> dict`; `_maybe_snapshot() -> None`; `_write_rows_snapshot(rows) -> None`; `_hydrate_from_snapshot() -> None`
- **imports:** __future__, os, re, time, trading

## `trading/broker_sense/ui_health.py`
_trading/broker_sense/ui_health.py — Human-UI self-check (owner goal 2026-07-07, #10)._
- **functions:** `_has_session(broker) -> bool`; `_eyes_fresh(broker, max_age_s) -> dict`; `_crawl_recent(max_age_s) -> dict`; `_hand_available() -> dict`; `check() -> dict`
- **imports:** __future__, time, trading

## `trading/broker_sense/vision_worker.py`
_trading/broker_sense/vision_worker.py — async deep chart-vision worker (the brain's patient eyes)._
- **functions:** `_cache() -> dict`; `_save(cache) -> None`; `cached_read(symbol, tf) -> dict | None`; `deep_vision(symbol, timeframes) -> dict | None`; `read_symbol(symbol, market, timeframes) -> dict`; `_target_symbols(limit) -> list[tuple[str, str]]`; `run_once(limit) -> dict`; `loop(interval, limit) -> None`
- **imports:** __future__, os, time, trading

## `trading/broker_sense/volume_profile.py`
_trading/broker_sense/volume_profile.py — Volume Profile / Value Area engine._
- **functions:** `_ms(ts) -> int`; `session_key(ts, market) -> int`; `volume_profile(rows, bins) -> dict`; `session_profiles(rows, market, max_sessions) -> list[dict]`; `value_migration(rows, market) -> dict`; `_vol_trend(vols) -> float`; `absorption(rows, lookback) -> dict`; `failed_auction(rows, market) -> dict`; `order_plan(rows, direction, market, swing) -> dict | None`; `features(rows, market) -> dict`
- **imports:** __future__

## `trading/broker_sense/watchlist.py`
_trading/broker_sense/watchlist.py — hot watchlist with TTL (saver E)._
- **classes:** HotWatchlist
- **imports:** __future__, time, trading

## `trading/broker_sense/watchlist_study.py`
_trading/broker_sense/watchlist_study.py — W: the watchlist study funnel (Pillar 27)._
- **functions:** `_env_f(name, default) -> float`; `enabled() -> bool`; `study_symbols(market) -> list[str]`; `propose(candidates) -> dict`; `_patterns_from_ohlc(o, h, l, c) -> tuple[list[str], int]`; `_candle_patterns(symbol, segment) -> dict`; `_fuse(mtf, micro, fusion, patterns) -> tuple[str | None, float, dict]`; `study_round(sessions) -> dict`; `status() -> dict`
- **imports:** __future__, os, time, trading

## `trading/classification_eval.py`
_Classification evaluation artifacts (CANON-37) + confusion-structure verdicts_
- **functions:** `_labels(y_true, y_pred) -> list`; `confusion(y_true, y_pred, labels) -> dict`; `per_class_report(y_true, y_pred, labels) -> dict`; `misclassification_gallery(y_true, y_pred, proba, k) -> list`; `_py(v)`; `confusion_structure_verdict(y_true, y_pred, labels, collapse_frac, swap_frac) -> dict`; `classification_eval(y_true, y_pred, proba, labels, gallery_k) -> dict`
- **imports:** __future__, numpy

## `trading/config.py`
_trading/config.py — central trading configuration (T1)._
- **classes:** TradingConfig
- **functions:** `_load() -> TradingConfig`
- **imports:** __future__, config, dataclasses

## `trading/connectivity_check.py`
_trading/connectivity_check.py — #13: prove every feature is CONNECTED and USED on_
- **functions:** `_dig(d, dotted)`; `check(n_recent) -> dict`
- **imports:** __future__, time, trading

## `trading/cortex_signal.py`
_CORTEX B8 — CortexSignalSource: the per-bar live signal pipeline (CANON-51)._
- **classes:** CortexSignalSource
- **functions:** `_psych_block(feat, symbol) -> np.ndarray`; `build_features(df, symbol) -> tuple[np.ndarray, np.ndarray]`; `default_arc()`; `get_cortex_source() -> CortexSignalSource`; `record_pending(symbol, side, experts_fired) -> None`; `record_shadow(segment, symbol, cortex, decider_action) -> None`; `apply_trust_feedback(closed_trades) -> int`
- **imports:** __future__, numpy, os, time, trading.feature_bus

## `trading/crypto/__init__.py`
_trading/crypto/ — Trading Phase T2 (Crypto Foundation)._
- **imports:** __future__, trading.crypto.config

## `trading/crypto/config.py`
_trading/crypto/config.py — crypto trading configuration (T2)._
- **classes:** ExchangeKeys, CryptoConfig
- **functions:** `_load() -> CryptoConfig`
- **imports:** __future__, config, dataclasses

## `trading/crypto/engine_client.py`
_trading/crypto/engine_client.py — thin, honest wrapper over Freqtrade's REST API (T-split B)._
- **classes:** FreqtradeError, CryptoEngineClient
- **functions:** `_order_type() -> str`; `_inbox_enabled() -> bool`; `_inbox_append(rec) -> dict`
- **imports:** __future__, json, os, trading.crypto.config, trading.openalgo_client, typing

## `trading/crypto/exchange_client.py`
_trading/crypto/exchange_client.py — thin ccxt wrapper (T2)._
- **classes:** ExchangeError, Reachable, ExchangeClient
- **imports:** __future__, dataclasses, trading.crypto.config, typing

## `trading/crypto/exchange_pool.py`
_trading/crypto/exchange_pool.py — multi-venue market-DATA pool (ban-proofing)._
- **classes:** _TokenBucket, _Venue, ExchangePool
- **functions:** `all_pools_status() -> dict`; `get_pool(market_type, quote, preferred) -> ExchangePool`; `pool_enabled() -> bool`
- **imports:** __future__, os, threading, time, typing

## `trading/crypto/feed.py`
_trading/crypto/feed.py — crypto market feed (T2)._
- **classes:** CryptoFeed
- **imports:** __future__, threading, time, trading.crypto.config, trading.crypto.exchange_client, trading.tick_cache

## `trading/crypto/freqtrade/__init__.py`
_trading/crypto/freqtrade/ — managed Freqtrade config + launch helper (T-split B)._

## `trading/crypto/freqtrade/brain_executor.py`
_trading/crypto/freqtrade/brain_executor.py — brain reads strategies as instructions (Phase G)._
- **classes:** LibraryBrainDecider, BrainExecutor
- **functions:** `_spot(symbol) -> str`; `library_brain_decider()`
- **imports:** __future__, os, pandas, time

## `trading/crypto/freqtrade/brain_learning.py`
_trading/crypto/freqtrade/brain_learning.py — the brain's CLOSED LEARNING LOOP._
- **classes:** BrainLearningCycle
- **imports:** __future__, os, time

## `trading/crypto/freqtrade/candle_updater.py`
_trading/crypto/freqtrade/candle_updater.py — keep OHLCV candle data continuously fresh._
- **functions:** `_batches(pairs, size) -> list[list[str]]`; `_uidir() -> str`; `_now() -> str`; `_write_status(uidir) -> None`; `_top_pairs(n) -> list[str]`; `_download(batch) -> int`; `run_cycle(uidir, cycle) -> None`; `main() -> int`
- **imports:** __future__, datetime, json, os, subprocess, time

## `trading/crypto/freqtrade/config_template.py`
_trading/crypto/freqtrade/config_template.py — build a Freqtrade config from OUR config._
- **functions:** `_pairs(cfg) -> list[str]`; `_freqai_block() -> dict`; `enabled_segments() -> list[str]`; `_seg_max_open(segment) -> dict`; `_segments_block(cfg) -> dict`; `build_config(cfg) -> dict`; `write_config(path, cfg, dry_run_wallet) -> str`
- **imports:** __future__, json, os, secrets, trading.crypto.config

## `trading/crypto/freqtrade/control.py`
_trading/crypto/freqtrade/control.py — guarded paper↔live & spot↔futures switch (Phase F)._
- **functions:** `_cfg()`; `_config_json() -> dict`; `_bot_running() -> bool`; `status() -> dict`; `_set_env_keys(updates) -> None`; `_wait_port_free(host, port, timeout) -> bool`; `restart_bot() -> dict`; `switch() -> dict`; `set_params() -> dict`; `set_segments_enabled(segments) -> dict`; `main(argv) -> int`
- **imports:** __future__, dataclasses, json, os, re, socket, subprocess, time

## `trading/crypto/freqtrade/entry_meta.py`
_Sidecar store for per-entry brain metadata (trader psychology + decision snapshot)._
- **functions:** `_load() -> dict`; `_key(pair, segment) -> str`; `_parse_ts(iso) -> float | None`; `record(pair, segment, meta) -> None`; `lookup(pair, segment, open_date) -> dict | None`
- **imports:** __future__, datetime, time, trading

## `trading/crypto/freqtrade/launch.py`
_trading/crypto/freqtrade/launch.py — generate the config and print the launch command._
- **functions:** `_write_start_script(cfg_path, user_dir) -> str`; `main() -> None`
- **imports:** __future__, os, sys, trading.crypto.config, trading.crypto.freqtrade.config_template

## `trading/crypto/freqtrade/micro_policy.py`
_trading/crypto/freqtrade/micro_policy.py — distilled entry micro-policy (invent-beyond #4)._
- **classes:** MicroPolicy
- **functions:** `cheap_features(close, high, low, volume) -> np.ndarray`; `_feats_from_df(df) -> np.ndarray`; `get_micro() -> Optional[MicroPolicy]`; `invalidate() -> None`; `distill_once(decider, symbols) -> dict`; `status() -> dict`
- **imports:** __future__, numpy, os, time, trading, typing

## `trading/crypto/freqtrade/ml_decider.py`
_trading/crypto/freqtrade/ml_decider.py — real ML direction models → brain instruction (Phase G)._
- **classes:** MLDirectionDecider
- **functions:** `all_ml_deciders() -> list`
- **imports:** __future__, numpy, pandas, time

## `trading/crypto/freqtrade/percoin_decider.py`
_trading/crypto/freqtrade/percoin_decider.py — brain picks the BEST strategy PER COIN (Phase G+)._
- **classes:** PerCoinBrainDecider
- **functions:** `per_coin_brain_decider()`
- **imports:** __future__, math, numpy, os, time, trading.crypto.freqtrade.brain_executor

## `trading/crypto/freqtrade/run_brain_loop.py`
_run_brain_loop.py — the missing driver: run the brain→Freqtrade entry/exit loop._
- **functions:** `main() -> int`
- **imports:** __future__, os, sys, time, trading.crypto.engine_client, trading.crypto.freqtrade.brain_executor, trading.crypto.freqtrade.brain_learning

## `trading/crypto/freqtrade/run_micro_distill.py`
_Nightly micro-policy distillation daemon (invent-beyond #4)._
- **functions:** `main() -> None`
- **imports:** __future__, os, time

## `trading/crypto/freqtrade/user_data/strategies/FreqAIDirection.py`
_FreqAIDirection — FreqAI directional ML strategy (Wave: crypto ML strategies → Freqtrade)._
- **classes:** FreqAIDirection
- **imports:** __future__, freqtrade.strategy, numpy, pandas, technical

## `trading/crypto/freqtrade/user_data/strategies/MlBridgeStrategy.py`
_MlBridgeStrategy — minimal placeholder Freqtrade strategy (T-split B)._
- **classes:** MlBridgeStrategy
- **imports:** __future__, freqtrade.strategy, pandas

## `trading/crypto/freqtrade/user_data/strategies/MlBridgeStrategySpot.py`
_MlBridgeStrategySpot — the SPOT-segment variant of MlBridgeStrategy._
- **classes:** MlBridgeStrategySpot
- **imports:** MlBridgeStrategy

## `trading/crypto/freqtrade/user_data/strategies/lib_BreakoutAtrChannel.py`
_AUTO-GENERATED by trading.strategy.freqtrade_adapter — do not edit by hand._
- **classes:** BreakoutAtrChannel
- **imports:** sys, trading.strategy.freqtrade_strategy_base

## `trading/crypto/freqtrade/user_data/strategies/lib_BreakoutBollingerSqueeze.py`
_AUTO-GENERATED by trading.strategy.freqtrade_adapter — do not edit by hand._
- **classes:** BreakoutBollingerSqueeze
- **imports:** sys, trading.strategy.freqtrade_strategy_base

## `trading/crypto/freqtrade/user_data/strategies/lib_BreakoutDonchianTrailing.py`
_AUTO-GENERATED by trading.strategy.freqtrade_adapter — do not edit by hand._
- **classes:** BreakoutDonchianTrailing
- **imports:** sys, trading.strategy.freqtrade_strategy_base

## `trading/crypto/freqtrade/user_data/strategies/lib_BreakoutGapAndGo.py`
_AUTO-GENERATED by trading.strategy.freqtrade_adapter — do not edit by hand._
- **classes:** BreakoutGapAndGo
- **imports:** sys, trading.strategy.freqtrade_strategy_base

## `trading/crypto/freqtrade/user_data/strategies/lib_BreakoutInsideBar.py`
_AUTO-GENERATED by trading.strategy.freqtrade_adapter — do not edit by hand._
- **classes:** BreakoutInsideBar
- **imports:** sys, trading.strategy.freqtrade_strategy_base

## `trading/crypto/freqtrade/user_data/strategies/lib_BreakoutLwVolatility.py`
_AUTO-GENERATED by trading.strategy.freqtrade_adapter — do not edit by hand._
- **classes:** BreakoutLwVolatility
- **imports:** sys, trading.strategy.freqtrade_strategy_base

## `trading/crypto/freqtrade/user_data/strategies/lib_BreakoutOpeningRange.py`
_AUTO-GENERATED by trading.strategy.freqtrade_adapter — do not edit by hand._
- **classes:** BreakoutOpeningRange
- **imports:** sys, trading.strategy.freqtrade_strategy_base

## `trading/crypto/freqtrade/user_data/strategies/lib_BreakoutRangeExpansion.py`
_AUTO-GENERATED by trading.strategy.freqtrade_adapter — do not edit by hand._
- **classes:** BreakoutRangeExpansion
- **imports:** sys, trading.strategy.freqtrade_strategy_base

## `trading/crypto/freqtrade/user_data/strategies/lib_BreakoutTtmSqueeze.py`
_AUTO-GENERATED by trading.strategy.freqtrade_adapter — do not edit by hand._
- **classes:** BreakoutTtmSqueeze
- **imports:** sys, trading.strategy.freqtrade_strategy_base

## `trading/crypto/freqtrade/user_data/strategies/lib_ComboAdxGatedCross.py`
_AUTO-GENERATED by trading.strategy.freqtrade_adapter — do not edit by hand._
- **classes:** ComboAdxGatedCross
- **imports:** sys, trading.strategy.freqtrade_strategy_base

## `trading/crypto/freqtrade/user_data/strategies/lib_ComboBollingerRsi.py`
_AUTO-GENERATED by trading.strategy.freqtrade_adapter — do not edit by hand._
- **classes:** ComboBollingerRsi
- **imports:** sys, trading.strategy.freqtrade_strategy_base

## `trading/crypto/freqtrade/user_data/strategies/lib_ComboElderTripleScreen.py`
_AUTO-GENERATED by trading.strategy.freqtrade_adapter — do not edit by hand._
- **classes:** ComboElderTripleScreen
- **imports:** sys, trading.strategy.freqtrade_strategy_base

## `trading/crypto/freqtrade/user_data/strategies/lib_ComboEmaCloud.py`
_AUTO-GENERATED by trading.strategy.freqtrade_adapter — do not edit by hand._
- **classes:** ComboEmaCloud
- **imports:** sys, trading.strategy.freqtrade_strategy_base

## `trading/crypto/freqtrade/user_data/strategies/lib_ComboPullbackContinuation.py`
_AUTO-GENERATED by trading.strategy.freqtrade_adapter — do not edit by hand._
- **classes:** ComboPullbackContinuation
- **imports:** sys, trading.strategy.freqtrade_strategy_base

## `trading/crypto/freqtrade/user_data/strategies/lib_ComboRsiMacd.py`
_AUTO-GENERATED by trading.strategy.freqtrade_adapter — do not edit by hand._
- **classes:** ComboRsiMacd
- **imports:** sys, trading.strategy.freqtrade_strategy_base

## `trading/crypto/freqtrade/user_data/strategies/lib_ComboSupertrendRsi.py`
_AUTO-GENERATED by trading.strategy.freqtrade_adapter — do not edit by hand._
- **classes:** ComboSupertrendRsi
- **imports:** sys, trading.strategy.freqtrade_strategy_base

## `trading/crypto/freqtrade/user_data/strategies/lib_ComboTrendDay.py`
_AUTO-GENERATED by trading.strategy.freqtrade_adapter — do not edit by hand._
- **classes:** ComboTrendDay
- **imports:** sys, trading.strategy.freqtrade_strategy_base

## `trading/crypto/freqtrade/user_data/strategies/lib_ComboVwapRsi.py`
_AUTO-GENERATED by trading.strategy.freqtrade_adapter — do not edit by hand._
- **classes:** ComboVwapRsi
- **imports:** sys, trading.strategy.freqtrade_strategy_base

## `trading/crypto/freqtrade/user_data/strategies/lib_FlowAccumulation.py`
_AUTO-GENERATED by trading.strategy.freqtrade_adapter — do not edit by hand._
- **classes:** FlowAccumulation
- **imports:** sys, trading.strategy.freqtrade_strategy_base

## `trading/crypto/freqtrade/user_data/strategies/lib_FlowChaikinAdosc.py`
_AUTO-GENERATED by trading.strategy.freqtrade_adapter — do not edit by hand._
- **classes:** FlowChaikinAdosc
- **imports:** sys, trading.strategy.freqtrade_strategy_base

## `trading/crypto/freqtrade/user_data/strategies/lib_FlowMfiTrend.py`
_AUTO-GENERATED by trading.strategy.freqtrade_adapter — do not edit by hand._
- **classes:** FlowMfiTrend
- **imports:** sys, trading.strategy.freqtrade_strategy_base

## `trading/crypto/freqtrade/user_data/strategies/lib_FlowObvTrend.py`
_AUTO-GENERATED by trading.strategy.freqtrade_adapter — do not edit by hand._
- **classes:** FlowObvTrend
- **imports:** sys, trading.strategy.freqtrade_strategy_base

## `trading/crypto/freqtrade/user_data/strategies/lib_FlowRvolShock.py`
_AUTO-GENERATED by trading.strategy.freqtrade_adapter — do not edit by hand._
- **classes:** FlowRvolShock
- **imports:** sys, trading.strategy.freqtrade_strategy_base

## `trading/crypto/freqtrade/user_data/strategies/lib_FlowVolumeBreakout.py`
_AUTO-GENERATED by trading.strategy.freqtrade_adapter — do not edit by hand._
- **classes:** FlowVolumeBreakout
- **imports:** sys, trading.strategy.freqtrade_strategy_base

## `trading/crypto/freqtrade/user_data/strategies/lib_FlowVwapTrend.py`
_AUTO-GENERATED by trading.strategy.freqtrade_adapter — do not edit by hand._
- **classes:** FlowVwapTrend
- **imports:** sys, trading.strategy.freqtrade_strategy_base

## `trading/crypto/freqtrade/user_data/strategies/lib_MeanrevAtrOverextension.py`
_AUTO-GENERATED by trading.strategy.freqtrade_adapter — do not edit by hand._
- **classes:** MeanrevAtrOverextension
- **imports:** sys, trading.strategy.freqtrade_strategy_base

## `trading/crypto/freqtrade/user_data/strategies/lib_MeanrevBbPctb.py`
_AUTO-GENERATED by trading.strategy.freqtrade_adapter — do not edit by hand._
- **classes:** MeanrevBbPctb
- **imports:** sys, trading.strategy.freqtrade_strategy_base

## `trading/crypto/freqtrade/user_data/strategies/lib_MeanrevBollinger.py`
_AUTO-GENERATED by trading.strategy.freqtrade_adapter — do not edit by hand._
- **classes:** MeanrevBollinger
- **imports:** sys, trading.strategy.freqtrade_strategy_base

## `trading/crypto/freqtrade/user_data/strategies/lib_MeanrevCci.py`
_AUTO-GENERATED by trading.strategy.freqtrade_adapter — do not edit by hand._
- **classes:** MeanrevCci
- **imports:** sys, trading.strategy.freqtrade_strategy_base

## `trading/crypto/freqtrade/user_data/strategies/lib_MeanrevConnorsRsi2.py`
_AUTO-GENERATED by trading.strategy.freqtrade_adapter — do not edit by hand._
- **classes:** MeanrevConnorsRsi2
- **imports:** sys, trading.strategy.freqtrade_strategy_base

## `trading/crypto/freqtrade/user_data/strategies/lib_MeanrevKeltner.py`
_AUTO-GENERATED by trading.strategy.freqtrade_adapter — do not edit by hand._
- **classes:** MeanrevKeltner
- **imports:** sys, trading.strategy.freqtrade_strategy_base

## `trading/crypto/freqtrade/user_data/strategies/lib_MeanrevMfi.py`
_AUTO-GENERATED by trading.strategy.freqtrade_adapter — do not edit by hand._
- **classes:** MeanrevMfi
- **imports:** sys, trading.strategy.freqtrade_strategy_base

## `trading/crypto/freqtrade/user_data/strategies/lib_MeanrevRsi.py`
_AUTO-GENERATED by trading.strategy.freqtrade_adapter — do not edit by hand._
- **classes:** MeanrevRsi
- **imports:** sys, trading.strategy.freqtrade_strategy_base

## `trading/crypto/freqtrade/user_data/strategies/lib_MeanrevStochastic.py`
_AUTO-GENERATED by trading.strategy.freqtrade_adapter — do not edit by hand._
- **classes:** MeanrevStochastic
- **imports:** sys, trading.strategy.freqtrade_strategy_base

## `trading/crypto/freqtrade/user_data/strategies/lib_MeanrevStochrsi.py`
_AUTO-GENERATED by trading.strategy.freqtrade_adapter — do not edit by hand._
- **classes:** MeanrevStochrsi
- **imports:** sys, trading.strategy.freqtrade_strategy_base

## `trading/crypto/freqtrade/user_data/strategies/lib_MeanrevUltimateOsc.py`
_AUTO-GENERATED by trading.strategy.freqtrade_adapter — do not edit by hand._
- **classes:** MeanrevUltimateOsc
- **imports:** sys, trading.strategy.freqtrade_strategy_base

## `trading/crypto/freqtrade/user_data/strategies/lib_MeanrevVwap.py`
_AUTO-GENERATED by trading.strategy.freqtrade_adapter — do not edit by hand._
- **classes:** MeanrevVwap
- **imports:** sys, trading.strategy.freqtrade_strategy_base

## `trading/crypto/freqtrade/user_data/strategies/lib_MeanrevWilliamsR.py`
_AUTO-GENERATED by trading.strategy.freqtrade_adapter — do not edit by hand._
- **classes:** MeanrevWilliamsR
- **imports:** sys, trading.strategy.freqtrade_strategy_base

## `trading/crypto/freqtrade/user_data/strategies/lib_MeanrevZscore.py`
_AUTO-GENERATED by trading.strategy.freqtrade_adapter — do not edit by hand._
- **classes:** MeanrevZscore
- **imports:** sys, trading.strategy.freqtrade_strategy_base

## `trading/crypto/freqtrade/user_data/strategies/lib_MlRegimeSwitchingHmm.py`
_AUTO-GENERATED by trading.strategy.freqtrade_adapter — do not edit by hand._
- **classes:** MlRegimeSwitchingHmm
- **imports:** sys, trading.strategy.freqtrade_strategy_base

## `trading/crypto/freqtrade/user_data/strategies/lib_MomBreakout.py`
_AUTO-GENERATED by trading.strategy.freqtrade_adapter — do not edit by hand._
- **classes:** MomBreakout
- **imports:** sys, trading.strategy.freqtrade_strategy_base

## `trading/crypto/freqtrade/user_data/strategies/lib_MomCmo.py`
_AUTO-GENERATED by trading.strategy.freqtrade_adapter — do not edit by hand._
- **classes:** MomCmo
- **imports:** sys, trading.strategy.freqtrade_strategy_base

## `trading/crypto/freqtrade/user_data/strategies/lib_MomIgnition.py`
_AUTO-GENERATED by trading.strategy.freqtrade_adapter — do not edit by hand._
- **classes:** MomIgnition
- **imports:** sys, trading.strategy.freqtrade_strategy_base

## `trading/crypto/freqtrade/user_data/strategies/lib_MomMacdHistogram.py`
_AUTO-GENERATED by trading.strategy.freqtrade_adapter — do not edit by hand._
- **classes:** MomMacdHistogram
- **imports:** sys, trading.strategy.freqtrade_strategy_base

## `trading/crypto/freqtrade/user_data/strategies/lib_MomObvConfirmed.py`
_AUTO-GENERATED by trading.strategy.freqtrade_adapter — do not edit by hand._
- **classes:** MomObvConfirmed
- **imports:** sys, trading.strategy.freqtrade_strategy_base

## `trading/crypto/freqtrade/user_data/strategies/lib_MomPpo.py`
_AUTO-GENERATED by trading.strategy.freqtrade_adapter — do not edit by hand._
- **classes:** MomPpo
- **imports:** sys, trading.strategy.freqtrade_strategy_base

## `trading/crypto/freqtrade/user_data/strategies/lib_MomRelativeVolume.py`
_AUTO-GENERATED by trading.strategy.freqtrade_adapter — do not edit by hand._
- **classes:** MomRelativeVolume
- **imports:** sys, trading.strategy.freqtrade_strategy_base

## `trading/crypto/freqtrade/user_data/strategies/lib_MomRoc.py`
_AUTO-GENERATED by trading.strategy.freqtrade_adapter — do not edit by hand._
- **classes:** MomRoc
- **imports:** sys, trading.strategy.freqtrade_strategy_base

## `trading/crypto/freqtrade/user_data/strategies/lib_MomRsiRegime.py`
_AUTO-GENERATED by trading.strategy.freqtrade_adapter — do not edit by hand._
- **classes:** MomRsiRegime
- **imports:** sys, trading.strategy.freqtrade_strategy_base

## `trading/crypto/freqtrade/user_data/strategies/lib_MomStochastic.py`
_AUTO-GENERATED by trading.strategy.freqtrade_adapter — do not edit by hand._
- **classes:** MomStochastic
- **imports:** sys, trading.strategy.freqtrade_strategy_base

## `trading/crypto/freqtrade/user_data/strategies/lib_MomTimeseries.py`
_AUTO-GENERATED by trading.strategy.freqtrade_adapter — do not edit by hand._
- **classes:** MomTimeseries
- **imports:** sys, trading.strategy.freqtrade_strategy_base

## `trading/crypto/freqtrade/user_data/strategies/lib_MomTrix.py`
_AUTO-GENERATED by trading.strategy.freqtrade_adapter — do not edit by hand._
- **classes:** MomTrix
- **imports:** sys, trading.strategy.freqtrade_strategy_base

## `trading/crypto/freqtrade/user_data/strategies/lib_PatternDojiBreakout.py`
_AUTO-GENERATED by trading.strategy.freqtrade_adapter — do not edit by hand._
- **classes:** PatternDojiBreakout
- **imports:** sys, trading.strategy.freqtrade_strategy_base

## `trading/crypto/freqtrade/user_data/strategies/lib_PatternEngulfing.py`
_AUTO-GENERATED by trading.strategy.freqtrade_adapter — do not edit by hand._
- **classes:** PatternEngulfing
- **imports:** sys, trading.strategy.freqtrade_strategy_base

## `trading/crypto/freqtrade/user_data/strategies/lib_PatternHammerStar.py`
_AUTO-GENERATED by trading.strategy.freqtrade_adapter — do not edit by hand._
- **classes:** PatternHammerStar
- **imports:** sys, trading.strategy.freqtrade_strategy_base

## `trading/crypto/freqtrade/user_data/strategies/lib_PatternHarami.py`
_AUTO-GENERATED by trading.strategy.freqtrade_adapter — do not edit by hand._
- **classes:** PatternHarami
- **imports:** sys, trading.strategy.freqtrade_strategy_base

## `trading/crypto/freqtrade/user_data/strategies/lib_PatternMarubozu.py`
_AUTO-GENERATED by trading.strategy.freqtrade_adapter — do not edit by hand._
- **classes:** PatternMarubozu
- **imports:** sys, trading.strategy.freqtrade_strategy_base

## `trading/crypto/freqtrade/user_data/strategies/lib_PatternThreeBarReversal.py`
_AUTO-GENERATED by trading.strategy.freqtrade_adapter — do not edit by hand._
- **classes:** PatternThreeBarReversal
- **imports:** sys, trading.strategy.freqtrade_strategy_base

## `trading/crypto/freqtrade/user_data/strategies/lib_SpotDcaAccumulate.py`
_AUTO-GENERATED by trading.strategy.freqtrade_adapter — do not edit by hand._
- **classes:** SpotDcaAccumulate
- **imports:** sys, trading.strategy.freqtrade_strategy_base

## `trading/crypto/freqtrade/user_data/strategies/lib_SpotGridRange.py`
_AUTO-GENERATED by trading.strategy.freqtrade_adapter — do not edit by hand._
- **classes:** SpotGridRange
- **imports:** sys, trading.strategy.freqtrade_strategy_base

## `trading/crypto/freqtrade/user_data/strategies/lib_TrendAdxDi.py`
_AUTO-GENERATED by trading.strategy.freqtrade_adapter — do not edit by hand._
- **classes:** TrendAdxDi
- **imports:** sys, trading.strategy.freqtrade_strategy_base

## `trading/crypto/freqtrade/user_data/strategies/lib_TrendAroon.py`
_AUTO-GENERATED by trading.strategy.freqtrade_adapter — do not edit by hand._
- **classes:** TrendAroon
- **imports:** sys, trading.strategy.freqtrade_strategy_base

## `trading/crypto/freqtrade/user_data/strategies/lib_TrendDonchianBreakout.py`
_AUTO-GENERATED by trading.strategy.freqtrade_adapter — do not edit by hand._
- **classes:** TrendDonchianBreakout
- **imports:** sys, trading.strategy.freqtrade_strategy_base

## `trading/crypto/freqtrade/user_data/strategies/lib_TrendEmaCrossover.py`
_AUTO-GENERATED by trading.strategy.freqtrade_adapter — do not edit by hand._
- **classes:** TrendEmaCrossover
- **imports:** sys, trading.strategy.freqtrade_strategy_base

## `trading/crypto/freqtrade/user_data/strategies/lib_TrendGoldenDeathCross.py`
_AUTO-GENERATED by trading.strategy.freqtrade_adapter — do not edit by hand._
- **classes:** TrendGoldenDeathCross
- **imports:** sys, trading.strategy.freqtrade_strategy_base

## `trading/crypto/freqtrade/user_data/strategies/lib_TrendKama.py`
_AUTO-GENERATED by trading.strategy.freqtrade_adapter — do not edit by hand._
- **classes:** TrendKama
- **imports:** sys, trading.strategy.freqtrade_strategy_base

## `trading/crypto/freqtrade/user_data/strategies/lib_TrendLinregSlope.py`
_AUTO-GENERATED by trading.strategy.freqtrade_adapter — do not edit by hand._
- **classes:** TrendLinregSlope
- **imports:** sys, trading.strategy.freqtrade_strategy_base

## `trading/crypto/freqtrade/user_data/strategies/lib_TrendMacd.py`
_AUTO-GENERATED by trading.strategy.freqtrade_adapter — do not edit by hand._
- **classes:** TrendMacd
- **imports:** sys, trading.strategy.freqtrade_strategy_base

## `trading/crypto/freqtrade/user_data/strategies/lib_TrendMacdZeroLine.py`
_AUTO-GENERATED by trading.strategy.freqtrade_adapter — do not edit by hand._
- **classes:** TrendMacdZeroLine
- **imports:** sys, trading.strategy.freqtrade_strategy_base

## `trading/crypto/freqtrade/user_data/strategies/lib_TrendParabolicSar.py`
_AUTO-GENERATED by trading.strategy.freqtrade_adapter — do not edit by hand._
- **classes:** TrendParabolicSar
- **imports:** sys, trading.strategy.freqtrade_strategy_base

## `trading/crypto/freqtrade/user_data/strategies/lib_TrendSmaCrossover.py`
_AUTO-GENERATED by trading.strategy.freqtrade_adapter — do not edit by hand._
- **classes:** TrendSmaCrossover
- **imports:** sys, trading.strategy.freqtrade_strategy_base

## `trading/crypto/freqtrade/user_data/strategies/lib_TrendSupertrend.py`
_AUTO-GENERATED by trading.strategy.freqtrade_adapter — do not edit by hand._
- **classes:** TrendSupertrend
- **imports:** sys, trading.strategy.freqtrade_strategy_base

## `trading/crypto/freqtrade/user_data/strategies/lib_TrendSupertrendMacdCombo.py`
_AUTO-GENERATED by trading.strategy.freqtrade_adapter — do not edit by hand._
- **classes:** TrendSupertrendMacdCombo
- **imports:** sys, trading.strategy.freqtrade_strategy_base

## `trading/crypto/freqtrade/user_data/strategies/lib_TrendTema.py`
_AUTO-GENERATED by trading.strategy.freqtrade_adapter — do not edit by hand._
- **classes:** TrendTema
- **imports:** sys, trading.strategy.freqtrade_strategy_base

## `trading/crypto/freqtrade/user_data/strategies/lib_TrendTripleMaStack.py`
_AUTO-GENERATED by trading.strategy.freqtrade_adapter — do not edit by hand._
- **classes:** TrendTripleMaStack
- **imports:** sys, trading.strategy.freqtrade_strategy_base

## `trading/crypto/freqtrade/user_data/strategies/lib_TrendTurtle55.py`
_AUTO-GENERATED by trading.strategy.freqtrade_adapter — do not edit by hand._
- **classes:** TrendTurtle55
- **imports:** sys, trading.strategy.freqtrade_strategy_base

## `trading/crypto/freqtrade/user_data/strategies/lib_VolBbWidthExpansion.py`
_AUTO-GENERATED by trading.strategy.freqtrade_adapter — do not edit by hand._
- **classes:** VolBbWidthExpansion
- **imports:** sys, trading.strategy.freqtrade_strategy_base

## `trading/crypto/freqtrade/user_data/strategies/lib_VolCompressionBreakout.py`
_AUTO-GENERATED by trading.strategy.freqtrade_adapter — do not edit by hand._
- **classes:** VolCompressionBreakout
- **imports:** sys, trading.strategy.freqtrade_strategy_base

## `trading/crypto/freqtrade/user_data/strategies/lib_VolExpansionTrend.py`
_AUTO-GENERATED by trading.strategy.freqtrade_adapter — do not edit by hand._
- **classes:** VolExpansionTrend
- **imports:** sys, trading.strategy.freqtrade_strategy_base

## `trading/crypto/freqtrade/user_data/strategies/lib_VolLowvolMeanrevert.py`
_AUTO-GENERATED by trading.strategy.freqtrade_adapter — do not edit by hand._
- **classes:** VolLowvolMeanrevert
- **imports:** sys, trading.strategy.freqtrade_strategy_base

## `trading/crypto/freqtrade_ingest.py`
_trading/crypto/freqtrade_ingest.py — Freqtrade closed trades → 85-col journal → NN bridge (Phase D)._
- **functions:** `_learn_from_close(ft, t) -> None`; `_f(v, default) -> float`; `_broker_context(pair, seg) -> dict`; `_peak_client(perp)`; `_fmt_ms(ms) -> str | None`; `_peak_fields(ft, allow_net) -> dict`; `map_trade(ft) -> ClosedTrade`; `map_open_trade(ft) -> dict`; `_tailgate_open_cols(ft) -> dict`; `closed_view(client, net_budget) -> list[dict]`; `open_trades_view(client) -> list[dict]`; `ingest_closed(journal, client) -> dict`
- **imports:** __future__, dataclasses, datetime, time, trading.journal.schema

## `trading/crypto/funding.py`
_trading/crypto/funding.py — perpetual funding-rate monitor (T2 §5)._
- **classes:** Funding, FundingMonitor
- **imports:** __future__, dataclasses, trading.crypto.config, trading.crypto.exchange_client, typing

## `trading/crypto/liquidation.py`
_trading/crypto/liquidation.py — liquidation-price estimator (T2)._
- **functions:** `liquidation_price() -> float`; `distance_to_liquidation() -> float`
- **imports:** __future__, trading.crypto.config

## `trading/crypto/markets.py`
_trading/crypto/markets.py — live crypto markets/screener feed (Binance-style table)._
- **functions:** `_client(segment)`; `_funding(ex) -> dict`; `live_markets() -> list[dict]`
- **imports:** __future__, time

## `trading/crypto/mlnb_writer.py`
_trading/crypto/mlnb_writer.py — standalone same-origin overlay writer for the forked FreqUI._
- **functions:** `_uidir() -> str`; `_dash_url() -> str`; `write_once(uidir) -> None`; `main() -> int`
- **imports:** __future__, json, os, re, time

## `trading/crypto/paper_engine.py`
_trading/crypto/paper_engine.py — crypto paper-fill simulator (T2 §3)._
- **classes:** Fill, Position, PaperEngine
- **functions:** `walk_order_book(side, amount, book) -> Fill`
- **imports:** __future__, dataclasses, trading.crypto.config, trading.crypto.liquidation

## `trading/crypto/session.py`
_trading/crypto/session.py — Crypto T2 orchestrator (one honest entry point)._
- **classes:** CryptoSession
- **imports:** __future__, trading.crypto.config, trading.crypto.exchange_client, trading.crypto.feed, trading.crypto.funding, trading.crypto.paper_engine, trading.crypto.watchlist, trading.market_toggle, trading.tick_cache

## `trading/crypto/watchlist.py`
_trading/crypto/watchlist.py — persisted crypto watchlist (T2)._
- **classes:** CryptoWatchItem, CryptoWatchlist
- **imports:** __future__, dataclasses, trading, trading.crypto.config

## `trading/direction/__init__.py`
_trading/direction — the Direction Accuracy Program (goal Pillar 27)._

## `trading/direction/dir_exit.py`
_trading/direction/dir_exit.py — D-exit: the directional EXIT oracle (Pillar 27)._
- **functions:** `_env_f(name, default) -> float`; `mode() -> str`; `_horizon() -> str | None`; `read(symbol, market, segment) -> dict`; `evaluate() -> dict`; `status() -> dict`
- **imports:** __future__, os

## `trading/direction/meta_challenger.py`
_trading/direction/meta_challenger.py — TabPFN challenger for the D6 meta-labeler._
- **functions:** `_env_f(name, default) -> float`; `_load_rows(max_rows) -> list[dict]`; `_encoded(rows)`; `_holdout_scores(fit_predict, X, y, cut) -> dict`; `_lgbm_fit_predict(cat_idx)`; `_tabpfn_fit_predict(cat_idx)`; `challenge(max_rows) -> dict`; `maybe_challenge() -> dict | None`; `status() -> dict`
- **imports:** __future__, json, os, pathlib, time, trading

## `trading/direction/meta_labeler.py`
_trading/direction/meta_labeler.py — D6: the direction meta-labeler (Pillar 27)._
- **functions:** `_env_f(name, default) -> float`; `_enabled() -> bool`; `_model_path() -> Path`; `_source_prior(source, horizon) -> float`; `_featurize(ex) -> dict`; `_frame(rows)`; `train(min_examples) -> dict`; `maybe_train() -> dict | None`; `load_model() -> dict | None`; `p_correct(example) -> float | None`; `gate(direction, example) -> dict`; `status() -> dict`
- **imports:** __future__, datetime, json, os, pathlib, time, trading

## `trading/direction/micro_features.py`
_trading/direction/micro_features.py — D4: microstructure direction features (Pillar 27)._
- **functions:** `_env_f(name, default) -> float`; `_enabled() -> bool`; `venue_gap(symbol) -> dict`; `funding_extreme(symbol) -> dict`; `mtf_agree(symbol, segment) -> dict`; `psych_ofi(symbol, segment) -> dict`; `snapshot(symbol, segment) -> dict`; `record_claims(symbols, segment, budget_s) -> dict`
- **imports:** __future__, os, time

## `trading/direction/mirror_gate.py`
_trading/direction/mirror_gate.py — D2: the Mirror Gate (goal Pillar 27)._
- **functions:** `_env_f(name, default) -> float`; `_enabled() -> bool`; `_buckets() -> dict`; `_horizons() -> list[str]`; `_lookup(source, regime, horizons) -> tuple[int, int, str]`; `decide(direction) -> dict`; `apply(direction) -> tuple[str | None, dict]`; `status() -> dict`
- **imports:** __future__, os, time, trading

## `trading/direction/pullback.py`
_trading/direction/pullback.py — D3: pullback entries (goal Pillar 27)._
- **functions:** `_env_f(name, default) -> float`; `enabled() -> bool`; `_key(symbol, segment) -> str`; `live_price(symbol, segment) -> float | None`; `atr_from_df(df) -> float | None`; `atr_from_feather(symbol, segment, tf) -> float | None`; `arm() -> bool`; `_dist(row) -> float`; `sweep(price_fn) -> list[dict]`; `status() -> dict`
- **imports:** __future__, os, time, trading

## `trading/direction/reflex.py`
_trading/direction/reflex.py — R2: the Reflex fast lane (Pillars 27 + 9)._
- **classes:** _Stats
- **functions:** `enabled() -> bool`; `_env_f(name, default) -> float`; `_venue_sym(row) -> tuple[str, str]`; `crossed(row, mid) -> str | None`; `_armed_maps() -> tuple[dict, dict]`; `run(executor_for) -> None`
- **imports:** __future__, json, os, time, trading

## `trading/direction/regime.py`
_trading/direction/regime.py — D5: the direction regime classifier (goal Pillar 27)._
- **functions:** `_env_f(name, default) -> float`; `_er(closes) -> tuple[float | None, bool]`; `_classify_closes(closes) -> dict`; `classify(symbol, segment) -> dict`; `market_regime() -> str`
- **imports:** __future__, os, time, trading

## `trading/direction/truth_ledger.py`
_trading/direction/truth_ledger.py — D1: the Direction Truth Ledger (goal Pillar 27)._
- **functions:** `_enabled() -> bool`; `_pending_path() -> Path`; `record() -> bool`; `_candle_dir() -> Path`; `_feather_for(symbol, segment) -> tuple[Path | None, str]`; `_closes(path)`; `_price_at(path, epoch) -> float | None`; `_append_train(folds) -> None`; `_bucket_key(source, regime, horizon) -> str`; `_fold(agg, row, horizon, correct, method) -> None`; `_resolve_row(row, now) -> tuple[list[tuple[str, bool, str]], bool]`; `tick(budget_s) -> dict`; `_parse_dt(s) -> float | None`; `backfill_journal(limit) -> dict`; `_wilson(correct, n, z) -> tuple[float, float, float]`; `hit_rates() -> list[dict]`; `status() -> dict`
- **imports:** __future__, datetime, fcntl, json, math, os, pathlib, time, trading

## `trading/evidence.py`
_trading/evidence.py — W3 evidence lane: baselines, counterfactuals, autonomy gates,_
- **functions:** `_store() -> dict`; `_save(d) -> None`; `_norm(sig) -> dict`; `_price_of(sig) -> float | None`; `observe_cycle() -> dict`; `_feed_snapshots(d, signals, now) -> int`; `_nearest_snap(snaps, target_ts) -> float | None`; `record_data_failure(source, detail) -> None`; `baseline_stats(market, segment, window_days) -> dict`; `skip_stats(market, segment, window_days) -> dict`; `autonomy_gates(market, segment) -> dict`; `watchdogs() -> dict`; `status() -> dict`
- **imports:** __future__, time, trading

## `trading/execution/__init__.py`
_trading/execution/ — Trade Execution Engine (Phase T3)._
- **imports:** __future__, trading.execution.bracket, trading.execution.circuit_breaker, trading.execution.engine, trading.execution.kill_switch, trading.execution.mae_mfe, trading.execution.margin, trading.execution.order_state, trading.execution.profit_booking, trading.execution.trailing

## `trading/execution/bracket.py`
_trading/execution/bracket.py — bracket + cover order builders (T3 §9)._
- **functions:** `_exit_action(entry_action) -> str`; `_target_stop_prices(entry_action, entry_price, target_points, stop_points) -> tuple[float, float]`; `bracket_order() -> dict`; `cover_order() -> dict`
- **imports:** __future__

## `trading/execution/circuit_breaker.py`
_trading/execution/circuit_breaker.py — daily-loss circuit breaker (T3 §7)._
- **classes:** DailyCircuitBreaker, CircuitBreakerTripped
- **imports:** __future__, dataclasses, trading, trading.squareoff

## `trading/execution/engine.py`
_trading/execution/engine.py — ExecutionEngine + TradeManager (T3 composition)._
- **classes:** TradeManager, ExecutionEngine
- **imports:** __future__, dataclasses, trading.execution.circuit_breaker, trading.execution.kill_switch, trading.execution.mae_mfe, trading.execution.order_state, trading.execution.profit_booking, trading.execution.trailing, typing

## `trading/execution/kill_switch.py`
_trading/execution/kill_switch.py — real-money safety kill-switch (T3 §10)._
- **classes:** KillSwitch
- **imports:** __future__, dataclasses, typing

## `trading/execution/mae_mfe.py`
_trading/execution/mae_mfe.py — tick-by-tick MAE/MFE tracker (T3 §2)._
- **classes:** MAEMFE
- **functions:** `_is_long(side) -> bool`
- **imports:** __future__, dataclasses

## `trading/execution/margin.py`
_trading/execution/margin.py — SEBI SPAN + Exposure margin check (T3 §8)._
- **classes:** MarginCheck
- **functions:** `nse_fo_margin(notional) -> dict`; `nse_intraday_margin(notional) -> dict`; `check_margin(required, available) -> MarginCheck`; `check_fo_order() -> MarginCheck`
- **imports:** __future__, dataclasses

## `trading/execution/order_state.py`
_trading/execution/order_state.py — order lifecycle state machine (T3 §1)._
- **classes:** OrderStatus, InvalidTransition, Order
- **imports:** __future__, dataclasses, enum

## `trading/execution/profit_booking.py`
_trading/execution/profit_booking.py — partial profit-booking ladder (T3 §6)._
- **classes:** Rung, BookEvent, ProfitLadder
- **functions:** `_is_long(side) -> bool`
- **imports:** __future__, dataclasses

## `trading/execution/profit_tailgate.py`
_trading/execution/profit_tailgate.py — adaptive trailing take-profit ("profit tailgating")._
- **functions:** `_key(market, segment, regime) -> str`; `_store() -> dict`; `learned_distance(market, segment, regime) -> float`; `locked_profit(market, segment) -> dict`; `clear_lock(trade_id) -> None`; `should_exit(market, segment, profit_pct, peak_profit_pct) -> tuple`; `learn(market, segment) -> None`; `status() -> dict`
- **imports:** __future__, trading

## `trading/execution/rl_exec_env.py`
_AI-scientist idea #8 — order-execution environment (gymnasium) for the RL slicing agent._
- **classes:** ExecutionEnv
- **functions:** `twap_episode_reward(env, seed) -> float`
- **imports:** __future__, numpy

## `trading/execution/rl_execution.py`
_AI-scientist idea #8 — RL execution agent (SB3-PPO order slicing over ExecutionEnv)._
- **classes:** RLExecutionAgent
- **imports:** __future__, numpy, trading.execution.rl_exec_env

## `trading/execution/trailing.py`
_trading/execution/trailing.py — trailing-stop strategies (T3 §3, §4, §5)._
- **classes:** WilderATR, TrailingStop, ExponentialTrailingStop, ATRTrailingStop, ChandelierExit, ParabolicSAR, ProfitLockTrailing
- **functions:** `_is_long(side) -> bool`
- **imports:** __future__, dataclasses, math

## `trading/exits/__init__.py`
_trading/exits/ — four separate trailing-exit components over one signed engine._
- **classes:** TrailingEngine, LongProfitTrail, LongStopTrail, ShortProfitTrail, ShortLossTrail
- **functions:** `make_exit(direction, purpose)`; `status(engine) -> dict`; `build_demo_trailing() -> dict`
- **imports:** __future__, trading.execution.trailing

## `trading/feature_bus.py`
_Feature bus — every data stream the brain owns, joined into ONE per-bar_
- **functions:** `_bar_ts(feat) -> np.ndarray`; `mtf_block(feat) -> np.ndarray`; `_btc_series()`; `market_block(feat, symbol) -> np.ndarray`; `record_live(symbol, values) -> None`; `live_block(feat, symbol) -> np.ndarray`
- **imports:** __future__, functools, json, numpy, os

## `trading/features_ta.py`
_Technical-feature layer — thin pandas-ta-classic wrapper (CANON-24/25)._
- **functions:** `_col(df, name) -> pd.Series`; `add_indicators(df, rsi_len, ema_lens, sma_len, bb_len, slope_len) -> pd.DataFrame`; `gate_warmup(df, cols) -> pd.DataFrame`; `support(df1, l, n1, n2) -> int`; `resistance(df1, l, n1, n2) -> int`; `fractal_levels(df, n1, n2) -> dict`; `_close_to_levels(price, levels, tol) -> bool`; `proximity_signal(df, n1, n2, tol, patterns) -> pd.Series`; `pattern_levels(df, n1, n2, atr_len, rr, patterns) -> list`; `one_hot_features(df, cols, categories) -> tuple`; `admission_gate(df, signal) -> dict`
- **imports:** __future__, numpy, pandas

## `trading/fitness.py`
_CORTEX fitness engine — mark-to-market scoring + honesty gates (B1, stitch-map rows 1-3)._
- **functions:** `_to_series(arr, index, name) -> pd.Series`; `_f(x, default) -> float`; `run_signals(close, entries, exits, fee, freq) -> 'vbt.Portfolio'`; `scorecard(pf) -> dict`; `underwater_fitness(pf) -> float`; `persistence_gate(y_true, y_pred, p_max) -> tuple[bool, dict]`; `majority_gate(y_true, y_pred_cls) -> tuple[bool, dict]`; `benchmark_gate(pf, close, fee) -> tuple[bool, dict]`; `arbitrate_timeframe(segment, short_tf, daily, metric, margin) -> dict`; `honest_report(pf, close, y_true, y_pred, y_true_cls, y_pred_cls) -> dict`
- **imports:** __future__, dieboldmariano, math, numpy, pandas, vectorbt

## `trading/goal.py`
_trading/goal.py — W1 goal scoreboard: score EVERY trade + segment against goal.yaml._
- **functions:** `load_goals() -> dict`; `segment_goal(market, segment) -> dict`; `_seg_of(row) -> tuple[str, str]`; `score_trade(row) -> dict`; `_parse_ts(s) -> float | None`; `_daily_series(rows) -> dict[str, float]`; `_max_drawdown(daily, base) -> float`; `_sharpe(daily, base) -> float | None`; `scoreboard(trades, window_days) -> dict`; `last_scoreboard() -> dict`
- **imports:** __future__, datetime, math, os, time, trading

## `trading/heads.py`
_CORTEX B6 — forecast heads: direct + autoregressive rollout on foundation nodes._
- **classes:** RolloutHead
- **functions:** `evaluate_head(head, windows, y_true_matrix, k, floor_model, p_max) -> dict`; `build_foundation_heads() -> dict`
- **imports:** __future__, numpy, trading.rollout

## `trading/instruments.py`
_trading/instruments.py — NSE/NFO/MCX instrument master via OpenAlgo._
- **classes:** Instrument, InstrumentStore
- **functions:** `to_dict(inst) -> dict`
- **imports:** __future__, dataclasses, trading, trading.openalgo_client

## `trading/journal/__init__.py`
_trading/journal/ — Brain Confidence + Trade Journal & Analytics (Phase T5)._
- **imports:** __future__, trading.journal.analytics, trading.journal.behavior, trading.journal.charges, trading.journal.confidence, trading.journal.journal, trading.journal.quality, trading.journal.schema, trading.journal.tearsheet

## `trading/journal/analytics.py`
_trading/journal/analytics.py — aggregate journal analytics (T5 §T5.5/6, blueprint §6)._
- **classes:** JournalAnalytics
- **functions:** `_net(t) -> float`; `_bucket_r(r) -> str`; `analyze_trades(trades) -> JournalAnalytics`
- **imports:** __future__, dataclasses, math

## `trading/journal/behavior.py`
_trading/journal/behavior.py — behavioural trade screening (T5 §T5.8)._
- **functions:** `_parse_dt(value) -> datetime | None`; `flag_revenge_trade(trade, prior_trades, window_minutes) -> bool`; `flag_overtrading(day_trade_count, daily_limit) -> bool`; `screen_behavior(trades) -> dict`
- **imports:** __future__, datetime

## `trading/journal/charges.py`
_trading/journal/charges.py — Indian + crypto transaction-cost math (T5 §5 P&L)._
- **classes:** SegmentRates, IndianChargeRates
- **functions:** `nse_charges(segment) -> dict`; `crypto_charges() -> dict`; `net_pnl(gross_pnl, total_charges) -> float`
- **imports:** __future__, dataclasses

## `trading/journal/confidence.py`
_trading/journal/confidence.py — per-symbol Bayesian confidence (T5 §T5.1/§T5.2)._
- **classes:** SymbolConfidence, ConfidenceBook
- **functions:** `_as_prob(value) -> float | None`
- **imports:** __future__, dataclasses, typing

## `trading/journal/journal.py`
_trading/journal/journal.py — TradeJournal orchestrator (T5)._
- **classes:** TradeJournal
- **functions:** `_is_crypto(trade) -> bool`; `_segment(trade) -> str`
- **imports:** __future__, trading, trading.journal.analytics, trading.journal.behavior, trading.journal.charges, trading.journal.confidence, trading.journal.quality, trading.journal.schema, trading.journal.tearsheet

## `trading/journal/quality.py`
_trading/journal/quality.py — per-trade quality metrics (T5 §5, blueprint Trade Quality Metrics)._
- **functions:** `r_multiple(net_pnl, entry_price, stop_price, quantity) -> float | None`; `_parse(dt)`; `_hms(seconds) -> str`; `trade_quality(trade) -> dict`
- **imports:** __future__, datetime

## `trading/journal/reset.py`
_trading/journal/reset.py — permanently wipe CLOSED-trade data, brain-safe (operator reset)._
- **functions:** `_backup(name, data) -> str`; `reset_closed_trades() -> dict`
- **imports:** __future__, json, os, time, trading

## `trading/journal/schema.py`
_trading/journal/schema.py — 85+ column closed-trade record (T5 §3, blueprint §5)._
- **classes:** ClosedTrade
- **functions:** `csv_header() -> str`
- **imports:** __future__, dataclasses, json

## `trading/journal/tearsheet.py`
_trading/journal/tearsheet.py — Phase T5 HTML/PDF performance tearsheet._
- **functions:** `_trade_dt(t) -> datetime | None`; `_fmt(v, prec) -> str`; `equity_curve(trades, starting_equity) -> list[dict]`; `monthly_pnl(trades) -> dict`; `_summary_stats(trades, starting_equity) -> list[tuple[str, str, str]]`; `_quantstats_rows(trades, starting_equity) -> list[tuple[str, str, str]]`; `_svg_line(values, color, fill, width, height, baseline)`; `_equity_section(curve) -> str`; `_heatmap_section(trades) -> str`; `_stats_section(rows) -> str`; `_page(title, body) -> str`; `render_tearsheet(trades) -> str`; `render_tearsheet_pdf(trades, path) -> str`
- **imports:** __future__, datetime, math, trading.journal.schema

## `trading/labels.py`
_Barrier-style 3-class labeling for CORTEX lanes (CANON-28; PNP-14/PNP-15)._
- **functions:** `barrier_label(close, pipdiff, sl_tp_ratio, horizon_bars) -> np.ndarray`; `class_balance(labels) -> dict`
- **imports:** __future__, numpy

## `trading/market_toggle.py`
_trading/market_toggle.py — NSE master on/off switch (T1 §7)._
- **classes:** MarketOff, MasterToggle
- **imports:** __future__, trading, typing

## `trading/online/__init__.py`
_trading/online/ — "Go online": continuous paper/live trading with safe switches (O1–O5)._
- **imports:** __future__, trading.online.replay, trading.online.session, trading.online.state, trading.online.supervisor, trading.online.wallet

## `trading/online/controls.py`
_trading/online/controls.py — shared, persisted control surface (O5)._
- **functions:** `registry() -> MarketRegistry`; `book() -> PaperWalletBook`; `reset_singletons() -> None`; `_ms_dict(market) -> dict`; `start(market) -> dict`; `stop(market) -> dict`; `pause(market) -> dict`; `halt(market) -> dict`; `set_mode(market, mode) -> dict`; `set_allow_live(market, allow) -> dict`; `set_segments(market, segments) -> dict`; `toggle_segment(market, segment) -> dict`; `_flush_loop_positions(market) -> None`; `set_balance(market, amount, portfolio_id) -> dict`; `top_up(market, amount, portfolio_id) -> dict`; `reset_wallet(market, portfolio_id) -> dict`; `panic(note) -> dict`; `status() -> dict`; `_fmt_state(d) -> str`; `_fmt_status() -> str`; `_cmd_balance(args) -> str`; `build_online_command_router() -> dict`; `handle_command(command, args) -> str`
- **imports:** __future__, trading.online.state, trading.online.wallet

## `trading/online/live_loop.py`
_trading/online/live_loop.py — the always-on LIVE trade loop (the missing daemon)._
- **classes:** BrainDecider, LiveTradeLoop
- **functions:** `trade_type(market, instrument, product, exchange) -> str`; `momentum_decider(window, band)`; `_xray_on_open(symbol, exchange, segment) -> None`; `_cortex_shadow_nse(market, symbol, window, d, in_position) -> dict`; `_brain_decider()`; `get_loop() -> LiveTradeLoop`; `start_loop() -> LiveTradeLoop`
- **imports:** __future__, collections, threading, time, trading.online, trading.online.session, trading.online.state

## `trading/online/replay.py`
_trading/online/replay.py — NSE off-hours candle/tick replay feed (Phase O3)._
- **classes:** CandleReplay, ReplaySession
- **functions:** `_as_bar(bar) -> dict`; `synthetic_ticks(bar, n) -> list[float]`
- **imports:** __future__, datetime, numpy, pandas, time, typing

## `trading/online/run_live_loop.py`
_trading/online/run_live_loop.py — run the OnlineTrader live loop as its OWN process._
- **functions:** `main() -> int`
- **imports:** __future__, sys, time

## `trading/online/session.py`
_trading/online/session.py — market calendar + LIVE↔REPLAY mode (O1)._
- **classes:** MarketSession
- **imports:** __future__, datetime, pandas

## `trading/online/state.py`
_trading/online/state.py — per-market state + central trading-state gate (O1)._
- **classes:** TradingState, MarketState, TradingStateGate, MarketRegistry
- **functions:** `normalize_segment(seg) -> str`
- **imports:** __future__, dataclasses, enum, trading

## `trading/online/supervisor.py`
_trading/online/supervisor.py — always-on trading supervisor (O4)._
- **classes:** OnlineSupervisor
- **imports:** __future__, dataclasses, pandas, trading.online.replay, trading.online.session, trading.online.state, trading.online.wallet

## `trading/online/wallet.py`
_trading/online/wallet.py — editable per-market paper-money wallet (O2)._
- **classes:** SlippageModel, FeeModel, CryptoFeeModel, NseFeeModel, FillModel, ProbabilisticFillModel, PaperWallet, PaperWalletBook
- **functions:** `_is_buy(side) -> bool`; `_state_file(market, portfolio_id) -> str`
- **imports:** __future__, dataclasses, trading, trading.crypto.paper_engine, trading.journal, typing

## `trading/openalgo_client.py`
_trading/openalgo_client.py — thin, honest wrapper over the OpenAlgo REST SDK._
- **classes:** ConnState, OpenAlgoError, OpenAlgoClient
- **imports:** __future__, dataclasses, trading.config, typing

## `trading/options/__init__.py`
_trading/options/ — Options Intelligence (Phase T4)._
- **imports:** __future__, trading.options.chain, trading.options.gex, trading.options.greeks, trading.options.iv, trading.options.max_pain, trading.options.oi, trading.options.payoff, trading.options.pcr

## `trading/options/chain.py`
_trading/options/chain.py — OptionsChain container (T4 §3 live chain table)._
- **classes:** OptionQuote, OptionLeg, OptionsChain
- **functions:** `_is_call(opt_type) -> bool`
- **imports:** __future__, dataclasses, trading.options.gex, trading.options.greeks, trading.options.max_pain, trading.options.oi, trading.options.payoff, trading.options.pcr

## `trading/options/gex.py`
_trading/options/gex.py — dealer Gamma Exposure (GEX) + zero-gamma level (T4 §7)._
- **functions:** `gamma_exposure(strikes) -> dict`; `zero_gamma_level(per_strike) -> float | None`
- **imports:** __future__

## `trading/options/greeks.py`
_trading/options/greeks.py — Black-76 option Greeks (T4 §2)._
- **functions:** `_norm_cdf(x) -> float`; `_norm_pdf(x) -> float`; `_is_call(flag) -> bool`; `_d1_d2(F, K, t, sigma) -> tuple[float, float]`; `black76_price(flag, F, K, t, r, sigma) -> float`; `_analytic_greeks(flag, F, K, t, r, sigma) -> dict`; `_vollib_greeks(flag, F, K, t, r, sigma) -> dict | None`; `get_all_greeks(flag, F, K, t, r, sigma) -> dict`; `implied_vol(price, flag, F, K, t, r) -> float | None`
- **imports:** __future__, math

## `trading/options/iv.py`
_trading/options/iv.py — IV Rank + IV Percentile (T4 §4 of features list)._
- **classes:** IVHistory
- **functions:** `iv_rank(current, history) -> float | None`; `iv_percentile(current, history) -> float | None`
- **imports:** __future__, collections, dataclasses

## `trading/options/live_chain.py`
_trading/options/live_chain.py — REAL NFO/BFO option chain → T4 analytics (2026-07-10)._
- **functions:** `_nearest_expiry(cli, underlying, opt_exchange) -> tuple[str, _dt.date] | None`; `fetch_raw_chain(underlying, strike_count) -> dict | None`; `cached_raw_chain(underlying) -> dict | None`; `to_chain(raw) -> OptionsChain`; `live_status(underlying, max_age_sec) -> dict | None`
- **imports:** __future__, datetime, math, time, trading.options.chain

## `trading/options/max_pain.py`
_trading/options/max_pain.py — Max Pain strike per expiry (T4 §6 of features)._
- **functions:** `_pain_at(settle, call_oi, put_oi) -> float`; `max_pain(call_oi, put_oi) -> dict`
- **imports:** __future__

## `trading/options/oi.py`
_trading/options/oi.py — OI heatmap aggregation + OI-change tracker (T4 §1 /oitracker)._
- **classes:** OITracker
- **functions:** `oi_heatmap(call_oi, put_oi) -> dict`; `classify_oi_change(price_change, oi_change) -> str`
- **imports:** __future__, dataclasses

## `trading/options/payoff.py`
_trading/options/payoff.py — multi-leg options payoff diagram (T4 §8 of features)._
- **classes:** PayoffLeg
- **functions:** `_price_grid(legs, lo, hi, steps) -> list[float]`; `payoff_curve(legs, prices) -> list[dict]`; `_breakevens(curve) -> list[float]`; `payoff_summary(legs) -> dict`
- **imports:** __future__, dataclasses

## `trading/options/pcr.py`
_trading/options/pcr.py — Put/Call Ratio, OI and volume (T4 §5 of features)._
- **functions:** `_ratio(put_total, call_total) -> float | None`; `put_call_ratio(call_oi, put_oi) -> dict`
- **imports:** __future__

## `trading/practice.py`
_Practice mode — the brain trades HISTORIC data to learn (user mandate_
- **functions:** `_source(trust_path, explore)`; `replay(df, symbol) -> dict`; `list_runs(limit) -> list`
- **imports:** __future__, json, numpy, os, time

## `trading/risk_overlay.py`
_Risk-map overlay — CANON-49 (JKA-07..10 spec, made honest)._
- **classes:** RiskOverlay
- **functions:** `forecast_sigma(returns, horizon) -> float`; `_ewma_sigma(r, lam) -> float`
- **imports:** __future__, numpy

## `trading/rl/__init__.py`
_(no summary)_

## `trading/rl/exec_policy.py`
_trading/rl/exec_policy.py — W6 RL execution-policy (PPO over a trade-spec action space)._
- **classes:** TradingExecEnv, RLExecPolicyNode
- **functions:** `_feat(ohlcv) -> np.ndarray`; `_atr(ohlcv, n) -> np.ndarray`; `train_policy(ohlcv) -> dict`; `latest_signal(ohlcv) -> dict`; `register_rl_exec(tag)`
- **imports:** __future__, gymnasium, json, math, numpy, os, pathlib, time, trading

## `trading/rollout.py`
_Rollout engine — CANON-47/48 (KRF-18/21/22)._
- **functions:** `_call_model(model, window) -> np.ndarray`; `_default_update(window, pred) -> np.ndarray`; `autoregressive_rollout(model, window, k, update_fn) -> np.ndarray`; `per_horizon_errors(y_true_matrix, y_pred_matrix) -> dict`; `persistence_rollout(window, k) -> np.ndarray`; `compare_to_floors(model, windows, y_true_matrix, k, floor_model, update_fn) -> dict`
- **imports:** __future__, numpy

## `trading/sandbox/__init__.py`
_(no summary)_

## `trading/sandbox/paper_sandbox.py`
_trading/sandbox/paper_sandbox.py — the brain's FAST paper-trading sandbox._
- **classes:** PaperSandbox
- **functions:** `_book_from_price(price) -> dict`; `get_sandbox() -> PaperSandbox`
- **imports:** __future__, os, time, trading, trading.crypto.paper_engine

## `trading/sandbox/run_sandbox_loop.py`
_trading/sandbox/run_sandbox_loop.py — drive the fast paper sandbox on a short interval._
- **functions:** `main() -> int`
- **imports:** __future__, os, time

## `trading/scouts.py`
_trading/scouts.py — W4 smart-money scout swarm + consensus oracle + dispatcher._
- **functions:** `_cfg_min_agree() -> int`; `_cfg_window_s() -> float`; `_store() -> dict`; `_save(d) -> None`; `record_signal(scout) -> dict`; `run_whale_prints_scout() -> int`; `run_crowd_psych_scout() -> int`; `run_onchain_scout() -> int`; `run_fusion_conviction_scout(app_signals) -> int`; `sophie_consensus() -> list[dict]`; `consensus_for(symbol) -> dict | None`; `_ross_dispatch(events) -> None`; `run_all(app_signals) -> dict`; `status() -> dict`
- **imports:** __future__, os, time, trading

## `trading/screener/__init__.py`
_trading/screener — per-segment ranked candidate screeners (NSE + crypto)._
- **imports:** __future__, trading.screener.filters, trading.screener.screener, trading.screener.stubs

## `trading/screener/commodities.py`
_trading/screener/commodities.py — MCX commodity FUTURES candidate generation._
- **functions:** `_fut_rows(raw) -> list[dict]`; `resolve_near_month_fut(client, base) -> Optional[dict]`; `screen_mcx_commodities(source) -> list[dict]`
- **imports:** __future__, trading.screener.options, typing

## `trading/screener/filters.py`
_trading/screener/filters.py — standalone, composable screener filter algorithms._
- **functions:** `_num(v, default) -> float`; `_get(row) -> float`; `percent_change_filter(rows) -> list[Row]`; `volume_filter(rows) -> list[Row]`; `relative_volume(volumes, window) -> float | None`; `age_filter(rows) -> list[Row]`; `realized_volatility(closes) -> float | None`; `volatility_filter(rows) -> list[Row]`; `range_stability(highs, lows) -> float | None`; `oi_buildup(price_change, oi_change) -> str`; `apply_technical_filters(ohlc_df) -> dict`; `score_rows(rows, score_fn, reason_fn) -> list[Row]`
- **imports:** __future__, math, typing

## `trading/screener/options.py`
_trading/screener/options.py — single-leg NSE option (CE/PE) candidate generation._
- **functions:** `atm_strike(ltp, strikes) -> Optional[float]`; `_strike_step(strikes) -> float`; `nearest_expiry(expiries) -> Optional[str]`; `pick_contracts(rows, ltp, mode, otm_depth, chain_cap) -> list[dict]`; `_norm_rows(raw) -> list[dict]`; `_broker()`; `_spot_exch(underlying) -> str`; `_opt_exch(underlying) -> str`; `_ltp(client, underlying) -> float`; `_search_options(client, underlying, exchange) -> list[dict]`; `screen_nse_options(source) -> list[dict]`
- **imports:** __future__, typing

## `trading/screener/prediction.py`
_Prediction-market screener — scans ALL live event markets and ranks them for the loop._
- **functions:** `_fetch(limit) -> list[dict]`; `scan(limit) -> list[dict]`; `last_price(symbol) -> float | None`; `screen_crypto_prediction(limit, filters) -> list[dict]`
- **imports:** __future__, json, time, urllib.request

## `trading/screener/screener.py`
_trading/screener/screener.py — per-segment ranked screeners (the live-loop entry)._
- **classes:** Screener
- **functions:** `_cand(symbol, segment, market, score, reason, metrics, source) -> dict`; `screen_nse_movers(source, segment) -> list[dict]`; `screen_nse_fno(source) -> list[dict]`; `screen_nse_options(source) -> list[dict]`; `_ticker_rows(tickers, markets, want) -> list[dict]`; `screen_crypto_spot(source) -> list[dict]`; `screen_crypto_futures(source) -> list[dict]`; `screen_crypto_options(source) -> list[dict]`; `build_demo_screener() -> Screener`
- **imports:** __future__, os, trading.screener, trading.screener.stubs, typing

## `trading/screener/sources.py`
_trading/screener/sources.py — INJECTABLE, offline-safe market-data sources._
- **classes:** LiveNSESource, LiveCryptoSource
- **functions:** `_rows_from_df(obj) -> list[dict]`; `_normalise_nse_movers(rows) -> list[dict]`
- **imports:** __future__, trading.screener.filters, typing

## `trading/screener/stubs.py`
_trading/screener/stubs.py — deterministic OFFLINE candidate lists per segment._
- **functions:** `stub_candidates(market, segment) -> list[dict]`
- **imports:** __future__

## `trading/screener/universe.py`
_trading/screener/universe.py — the LIQUID, tradeable NSE equity universe._
- **functions:** `is_liquid(symbol) -> bool`; `liquid_movers(oa_quote) -> list[dict]`
- **imports:** __future__, typing

## `trading/session.py`
_trading/session.py — NSE T1 orchestrator (single honest entry point)._
- **classes:** NSESession
- **imports:** __future__, trading, trading.config, trading.instruments, trading.market_toggle, trading.openalgo_client, trading.tick_cache, trading.watchlist

## `trading/simlab.py`
_CORTEX B5 — SimLab: a psychology-free order-matching market environment (KRF-06/13)._
- **classes:** SimResult, SimLab
- **imports:** __future__, dataclasses, datetime, numpy

## `trading/sizing/__init__.py`
_Phase-T8: Position / capital sizing layer (NSE + crypto, long & short)._
- **imports:** __future__, position_sizer

## `trading/sizing/position_sizer.py`
_Per-trade position sizer -- turns an edge/stop/prob into qty & notional._
- **classes:** PositionSizer
- **functions:** `_side_sign(side) -> int`; `afml_bet_size(prob, side, num_classes) -> float`; `build_demo_sizing() -> dict`
- **imports:** __future__, math, scipy.stats, typing

## `trading/squareoff.py`
_trading/squareoff.py — exchange auto-squareoff rule engine (T1 §8)._
- **classes:** SquareoffRule
- **functions:** `_parse(hhmm) -> time`; `_minus_minutes(t, minutes) -> time`; `build_rules(config) -> dict[str, SquareoffRule]`; `now_ist() -> datetime`; `due_exchanges(when, config) -> list[str]`; `is_squareoff_due(exchange, when, config) -> bool`; `next_squareoff(exchange, config) -> time | None`
- **imports:** __future__, dataclasses, datetime, trading.config

## `trading/state.py`
_trading/state.py — tiny JSON state persistence for the trading package._
- **functions:** `_path(name) -> Path`; `load_json(name, default) -> Any`; `save_json(name, data) -> None`; `update_json(name, updates) -> dict`; `mutate_json(name, fn, default) -> Any`
- **imports:** __future__, json, os, pathlib, tempfile, typing

## `trading/strategy/__init__.py`
_trading/strategy/ — Strategy creation / mutation / evolution engine (Phase T8)._
- **imports:** __future__, trading.strategy.backtest, trading.strategy.control, trading.strategy.evolve, trading.strategy.features, trading.strategy.fitness, trading.strategy.genome, trading.strategy.guardrails, trading.strategy.operators, trading.strategy.registry

## `trading/strategy/autoresearch.py`
_trading/strategy/autoresearch.py — the LIVE autoresearch champion loop (invent-beyond #5)._
- **functions:** `_cfg_int(name, default) -> int`; `_store() -> dict`; `_save(d) -> None`; `_crypto_symbols() -> list[str]`; `_nse_symbols() -> list[str]`; `_pick(symbols, cycle) -> str`; `_frame(symbol, market, timeframe)`; `run_cycle() -> dict`; `status() -> dict`
- **imports:** __future__, logging, os, time, trading

## `trading/strategy/backtest.py`
_trading/strategy/backtest.py — backtest via vectorbt + walk-forward (T8.1, reuse-first)._
- **classes:** BacktestResult
- **functions:** `_profit_factor(gross_win, gross_loss) -> float`; `_safe(fn, default)`; `backtest_signal(signal, ohlcv) -> BacktestResult`; `_pandas_backtest(close, target, cost_rate, periods_per_year)`; `walk_forward_folds(n_rows) -> list[dict]`
- **imports:** __future__, dataclasses, numpy, pandas

## `trading/strategy/champion_bandit.py`
_trading/strategy/champion_bandit.py — regime-contextual champion allocator (#3)._
- **functions:** `_store() -> dict`; `_regime() -> str`; `_champions(market) -> list[str]`; `suggest_allocation(market) -> dict`; `stake_scale(market, strategy) -> float`; `update(market, strategy) -> None`; `status() -> dict`
- **imports:** __future__, os, time, trading

## `trading/strategy/control.py`
_trading/strategy/control.py — feature gate for the evolution/mutation engine._
- **classes:** StrategyEvolutionDisabled
- **functions:** `_env_flag() -> bool | None`; `evolution_enabled() -> bool`; `set_evolution_enabled(enabled) -> None`; `require_evolution_enabled() -> None`
- **imports:** __future__, os

## `trading/strategy/cpcv.py`
_trading/strategy/cpcv.py — Combinatorial Purged Cross-Validation (Pillar 20)._
- **functions:** `_group_bounds(n_rows, n_groups) -> list[tuple[int, int]]`; `_purge_train(train, test_blocks, embargo) -> list[tuple[int, int]]`; `combinatorial_purged_folds(n_rows) -> list[dict]`; `n_paths(n_groups, k_test) -> int`
- **imports:** __future__, itertools, numpy

## `trading/strategy/direction_equation.py`
_trading/strategy/direction_equation.py — P2 of the direction-equation quest: discover ONE_
- **functions:** `_forward_return(close, h) -> np.ndarray`; `horizon_ic(raw, close, h) -> float`; `_equation_generators()`; `score_equation(cand, feats_oos, close_oos, horizons) -> dict | None`; `discover(ohlcv, market) -> list[dict]`; `cpcv_robustness(ohlcv, expr, kind, features) -> dict | None`; `_triple_barrier_winrate(ohlcv, expr, kind, features) -> dict | None`; `_block_ic_matrix(ohlcv, cands) -> np.ndarray | None`; `validate(ohlcv, ranked, market) -> dict`; `save_equations(market, ranked) -> None`; `load_equations(market) -> list[dict]`; `_now() -> float`; `discover_and_save(ohlcv, market) -> list[dict]`; `_ohlcv_for(symbol, market, tf, bars) -> pd.DataFrame | None`; `run_for_market(symbol, market) -> list[dict]`
- **imports:** __future__, numpy, pandas, trading, trading.strategy.generators.expression, trading.strategy.guardrails

## `trading/strategy/direction_equation_deploy.py`
_trading/strategy/direction_equation_deploy.py — P4 of the direction-equation quest: deploy the_
- **functions:** `_rows_to_df(rows) -> pd.DataFrame | None`; `_equation_score(feats, eqs, top_k) -> float | None`; `predict(rows, market) -> dict | None`; `equation_tilt(rows, market) -> dict | None`; `reevolve_all(symbols) -> dict`
- **imports:** __future__, numpy, pandas, trading.strategy.direction_equation, trading.strategy.generators.expression

## `trading/strategy/evolve.py`
_trading/strategy/evolve.py — DEAP NSGA-II evolution loop (T8.3)._
- **classes:** EvolutionResult
- **functions:** `_assign_fitness(strat, ohlcv, feats, n_folds) -> Strategy`; `evolve(ohlcv) -> EvolutionResult`
- **imports:** __future__, copy, dataclasses, deap, numpy, pandas, trading.strategy.control, trading.strategy.features, trading.strategy.fitness, trading.strategy.genome, trading.strategy.guardrails, trading.strategy.operators, trading.strategy.registry

## `trading/strategy/evolved_link.py`
_trading/strategy/evolved_link.py — the live wire between the self-evolving strategy_
- **functions:** `_loop()`; `_portfolio()`; `breed(ohlcv_by_market) -> dict`; `persist_dashboard_status(loop) -> dict`; `best_evolved_strategy(market)`; `attach_to_pipeline(pipeline, market) -> bool`; `status() -> dict`
- **imports:** __future__, time, trading.strategy.control

## `trading/strategy/features.py`
_trading/strategy/features.py — OHLCV → feature frame via TA-Lib (T8.1, reuse-first)._
- **functions:** `_talib_feats(df, close, high, low, fast, slow, mom_n)`; `_pandas_feats(df, close_s, fast, slow, mom_n)`; `compute_features(ohlcv) -> pd.DataFrame`
- **imports:** __future__, numpy, pandas

## `trading/strategy/fitness.py`
_trading/strategy/fitness.py — journal/backtest-driven multi-objective fitness (T8.2)._
- **classes:** Fitness
- **functions:** `evaluate_oos(strategy, ohlcv) -> dict`; `multi_objective(oos) -> tuple[float, tuple, dict]`; `journal_realized(realized_trade_returns) -> dict | None`; `fitness(strategy, ohlcv) -> Fitness`
- **imports:** __future__, dataclasses, numpy, pandas, trading.strategy.backtest, trading.strategy.cpcv, trading.strategy.features, trading.strategy.genome

## `trading/strategy/foundry.py`
_trading/strategy/foundry.py — the brain's STRATEGY FOUNDRY._
- **classes:** FoundrySpec, StrategyFoundry
- **functions:** `strategy_id(segment, name) -> str`; `_seed_specs() -> list[FoundrySpec]`
- **imports:** __future__, dataclasses, hashlib, numpy, time

## `trading/strategy/foundry_advanced.py`
_trading/strategy/foundry_advanced.py — data-backed foundry strategies on REAL feeds._
- **functions:** `_binance(perp)`; `_sid(foundry, name)`; `orderbook_alpha_eval(foundry, symbol) -> dict | None`; `avellaneda_stoikov_eval(foundry, symbol, gamma, k) -> dict | None`; `basis_arb_eval(foundry, symbol) -> dict | None`; `cross_exchange_arb_eval(foundry, symbol, venues) -> dict | None`; `triangular_arb_eval(foundry, legs) -> dict | None`; `crypto_options_vol_eval(foundry, currency) -> dict | None`; `run_all_advanced(foundry) -> dict`
- **imports:** __future__, math, time

## `trading/strategy/foundry_strategies.py`
_trading/strategy/foundry_strategies.py — EXECUTABLE strategies for the Strategy Foundry,_
- **functions:** `hmm_regime_signal(ext_feats) -> pd.Series`; `_backtest_metrics(signal, close) -> dict`; `funding_rate_arb_eval(foundry, symbols, exchange) -> dict | None`; `_pair_cointegration(a, b)`; `statarb_pairs_eval(foundry, series_by_symbol) -> list[dict]`; `backtest_and_track(foundry, ohlcv_by_symbol) -> list[dict]`
- **imports:** __future__, numpy, pandas

## `trading/strategy/freqtrade_adapter.py`
_trading/strategy/freqtrade_adapter.py — translate LibraryStrategy → Freqtrade IStrategy (Phase C)._
- **functions:** `_spot_mode() -> bool`; `_is_crypto(strat) -> bool`; `crypto_strategies() -> list`; `skipped_strategies() -> list[dict]`; `class_name_for(name) -> str`; `can_short_for(strat) -> bool`; `make_freqtrade_strategy(name)`; `generate_strategy_files(out_dir) -> dict`; `main(argv) -> int`
- **imports:** __future__, os, re

## `trading/strategy/freqtrade_strategy_base.py`
_trading/strategy/freqtrade_strategy_base.py — concrete Freqtrade base for library strategies._
- **classes:** LibraryStrategyBase
- **imports:** __future__, freqtrade.strategy, pandas

## `trading/strategy/generators/__init__.py`
_trading/strategy/generators — the Strategy-Generator Portfolio._
- **imports:** __future__, trading.strategy.generators.base, trading.strategy.generators.expression, trading.strategy.generators.portfolio

## `trading/strategy/generators/alpha_mining.py`
_trading/strategy/generators/alpha_mining.py — generator ⑤: formulaic-alpha mining._
- **classes:** AlphaMiningGenerator
- **functions:** `_rand_expr(rng, depth) -> str`
- **imports:** __future__, numpy, pandas, trading.strategy.generators.base, trading.strategy.generators.expression

## `trading/strategy/generators/alpha_ops.py`
_trading/strategy/generators/alpha_ops.py — formulaic-alpha operator library._
- **functions:** `_s(x, index)`; `Abs(x)`; `Sign(x)`; `Log(x)`; `Add(a, b)`; `Sub(a, b)`; `Mul(a, b)`; `Div(a, b)`; `Pow(a, b)`; `Greater(a, b)`; `Less(a, b)`; `Ref(x, d)`; `Delta(x, d)`; `Mean(x, d)`; `Sum(x, d)`; `Std(x, d)`; `Var(x, d)`; `Skew(x, d)`; `Kurt(x, d)`; `Max(x, d)`; `Min(x, d)`; `Med(x, d)`; `Mad(x, d)`; `Rank(x, d)`; `WMA(x, d)`; `EMA(x, d)`; `Cov(a, b, d)`; `Corr(a, b, d)`; `alpha_namespace(df) -> dict`
- **imports:** __future__, numpy, pandas

## `trading/strategy/generators/base.py`
_trading/strategy/generators/base.py — the Strategy-Generator Portfolio backbone._
- **classes:** Candidate, StrategyGenerator
- **functions:** `register_candidate_type(tag)`; `rebuild(payload)`; `evaluate_and_admit(candidates, ohlcv) -> dict`; `_update_champion(market, cid, metrics) -> None`
- **imports:** __future__, pandas, typing

## `trading/strategy/generators/expression.py`
_trading/strategy/generators/expression.py — a candidate whose signal is a discovered_
- **classes:** ExpressionStrategy
- **functions:** `_protected_div(a, b)`; `_protected_sqrt(a)`; `_protected_log(a)`; `_protected_inv(a)`; `_causal_z(s) -> pd.Series`; `eval_expression(expr, kind, df, features) -> pd.Series`
- **imports:** __future__, dataclasses, numpy, pandas, trading.strategy.generators.base

## `trading/strategy/generators/llm_mutation.py`
_trading/strategy/generators/llm_mutation.py — generator ②: LLM-as-mutation-operator._
- **classes:** LLMMutationGenerator
- **functions:** `_valid_src(src, features) -> bool`; `_extract_json(text)`
- **imports:** __future__, json, numpy, os, re, trading.strategy.generators.base

## `trading/strategy/generators/optuna_tune.py`
_trading/strategy/generators/optuna_tune.py — generator ⑥ (part B): Optuna tuning._
- **classes:** OptunaGenerator
- **imports:** __future__, numpy, pandas, trading.strategy.generators.base, trading.strategy.generators.expression

## `trading/strategy/generators/portfolio.py`
_trading/strategy/generators/portfolio.py — runs the whole generator portfolio._
- **classes:** StrategyPortfolio
- **functions:** `_try(factory)`; `default_generators() -> list`
- **imports:** __future__, pandas, trading.strategy.generators.base

## `trading/strategy/generators/quality_diversity.py`
_trading/strategy/generators/quality_diversity.py — generator ④: Quality-Diversity (pyribs)._
- **classes:** QualityDiversityGenerator
- **functions:** `_standardize(feats, flist) -> np.ndarray`
- **imports:** __future__, numpy, pandas, trading.strategy.generators.base, trading.strategy.generators.expression

## `trading/strategy/generators/rd_agent.py`
_trading/strategy/generators/rd_agent.py — generator ⑦: RD-Agent(Q)-style factor researcher._
- **classes:** RDAgentGenerator
- **functions:** `_extract_json(text)`
- **imports:** __future__, json, numpy, os, re, trading.strategy.generators.base, trading.strategy.generators.expression

## `trading/strategy/generators/stats_gate.py`
_trading/strategy/generators/stats_gate.py — generator ⑥ (part A): family-wise error control._
- **functions:** `family_wise_superior(fold_returns_by_id) -> set`
- **imports:** __future__, numpy

## `trading/strategy/generators/symbolic.py`
_trading/strategy/generators/symbolic.py — generator ③: symbolic regression (BOTH engines)._
- **classes:** GplearnGenerator, PysrGenerator, OperonGenerator
- **functions:** `_feature_matrix(feats, market)`
- **imports:** __future__, numpy, pandas, trading.strategy.generators.base, trading.strategy.generators.expression

## `trading/strategy/genome.py`
_trading/strategy/genome.py — DEAP genetic-programming strategy genome (T8.1, reuse-first)._
- **classes:** FloatS, BoolS, Strategy
- **functions:** `_and(a, b)`; `_or(a, b)`; `_gt(a, b)`; `_lt(a, b)`; `_gtc(a, c)`; `_ltc(a, c)`; `_xup(a, b)`; `_xdn(a, b)`; `get_pset(features) -> gp.PrimitiveSetTyped`; `_zscore(df, features) -> pd.DataFrame`; `random_tree(pset, rng)`; `compile_signal(tree, pset, zdf, features) -> pd.Series`; `random_strategy(features, rng) -> Strategy`
- **imports:** __future__, dataclasses, deap, numpy, pandas, random, trading.strategy.features

## `trading/strategy/guardrails.py`
_trading/strategy/guardrails.py — overfitting guardrails (T8.2)._
- **classes:** GuardrailReport
- **functions:** `probabilistic_sharpe_ratio(sr, n) -> float`; `expected_max_sharpe(var_sr, n_trials) -> float`; `deflated_sharpe_ratio(returns) -> dict`; `pbo_cscv(perf_blocks) -> dict`; `information_coefficient(values, forward_returns) -> float`; `passes_guardrails(strategy, ohlcv) -> GuardrailReport`
- **imports:** __future__, dataclasses, itertools, math, numpy, scipy, trading.strategy.fitness

## `trading/strategy/library/__init__.py`
_trading/strategy/library/ — curated institutional Strategy Library (the active T8 feature)._
- **imports:** __future__, trading.strategy.library.base, trading.strategy.library.features_ext, trading.strategy.library.registry

## `trading/strategy/library/base.py`
_trading/strategy/library/base.py — the LibraryStrategy abstraction + data-requirement model._
- **classes:** DataReq, StrategyStatus, LibraryStrategy
- **functions:** `long_when(cond, index) -> pd.Series`; `long_short(long_cond, short_cond, index) -> pd.Series`; `stateful_band(entry_long, exit_long, entry_short, exit_short) -> pd.Series`
- **imports:** __future__, dataclasses, enum, pandas, typing

## `trading/strategy/library/catalog/__init__.py`
_trading/strategy/library/catalog/ — the strategy definitions, one module per family group._

## `trading/strategy/library/catalog/_impl_crypto_deriv.py`
_catalog/_impl_crypto_deriv.py — REAL backtest functions for crypto-derivatives strategies._
- **functions:** `_empty(reason) -> dict`; `_load(want_oi)`; `bt_funding_arb(md) -> dict`; `bt_funding_momentum(md) -> dict`; `bt_basis_arb(md) -> dict`; `bt_cash_carry(md) -> dict`; `bt_basis_trading(md) -> dict`; `bt_calendar_spread(md) -> dict`; `bt_roll_yield_harvesting(md) -> dict`; `bt_oi_breakout(md) -> dict`
- **imports:** __future__, numpy, pandas, trading.strategy.library, warnings

## `trading/strategy/library/catalog/_impl_crypto_options.py`
_catalog/_impl_crypto_options.py — REAL backtests for crypto-options strategies (Wave 1B)._
- **functions:** `_empty(reason) -> dict`; `_ivrv()`; `_chain()`; `_vol_premium(short_vol) -> dict`; `bt_vrp_harvest(md) -> dict`; `bt_short_straddle(md) -> dict`; `bt_short_strangle(md) -> dict`; `bt_iron_condor(md) -> dict`; `bt_iron_butterfly(md) -> dict`; `bt_volatility_carry(md) -> dict`; `bt_iv_rv_arbitrage(md) -> dict`; `bt_vega_trading(md) -> dict`; `bt_long_straddle(md) -> dict`; `bt_long_strangle(md) -> dict`; `bt_volatility_cone(md) -> dict`; `bt_skew_trading(md) -> dict`; `_underlying_daily()`; `_atm_iv() -> float`; `_structure_metrics(legs) -> dict`; `bt_long_call(md) -> dict`; `bt_long_put(md) -> dict`; `bt_bull_call_spread(md) -> dict`; `bt_bear_put_spread(md) -> dict`; `bt_covered_call(md) -> dict`; `bt_protective_put(md) -> dict`; `bt_ratio_spread(md) -> dict`
- **imports:** __future__, numpy, pandas, trading.strategy.library, warnings

## `trading/strategy/library/catalog/_impl_ml_direction.py`
_catalog/_impl_ml_direction.py — REAL sklearn/boosting ML-direction backtests (Wave 2)._
- **functions:** `_empty(reason) -> dict`; `_ohlcv()`; `_ml_backtest(model_key) -> dict`; `bt_rf(md) -> dict`; `bt_xgb(md) -> dict`; `bt_lgb(md) -> dict`; `bt_catboost(md) -> dict`
- **imports:** __future__, importlib, numpy, pandas, trading.strategy.library, warnings

## `trading/strategy/library/catalog/_impl_multi_asset.py`
_catalog/_impl_multi_asset.py — REAL backtests for multi-asset crypto stat-arb (Wave 1C)._
- **functions:** `_empty(reason) -> dict`; `_panel(days)`; `_nse_panel()`; `_best_pair(logp)`; `_pairs_metrics() -> dict`; `bt_pairs_trading(md) -> dict`; `bt_cointegration(md) -> dict`; `bt_correlation(md) -> dict`; `_cross_sectional() -> dict`; `bt_cross_sectional_momentum(md) -> dict`; `bt_cross_sectional_mean_reversion(md) -> dict`; `bt_relative_strength_ranking(md) -> dict`; `bt_long_short_market_neutral(md) -> dict`; `bt_nse_basket(md) -> dict`; `bt_nse_correlation_breakdown(md) -> dict`; `bt_nse_leader_laggard(md) -> dict`; `bt_nse_sector_rotation(md) -> dict`; `bt_nse_dollar_neutral(md) -> dict`; `bt_nse_beta_neutral(md) -> dict`; `bt_nse_cross_sectional_momentum(md) -> dict`; `bt_nse_cross_sectional_mr(md) -> dict`
- **imports:** __future__, numpy, pandas, trading.strategy.library, warnings

## `trading/strategy/library/catalog/_impl_nse_factor.py`
_catalog/_impl_nse_factor.py — REAL backtests for the NSE factor family (Wave 2, free yfinance)._
- **functions:** `_empty(reason) -> dict`; `_data()`; `_long_short_from_scores(panel, scores) -> dict`; `_factor(kind) -> dict`; `bt_factor_value(md) -> dict`; `bt_factor_growth(md) -> dict`; `bt_factor_quality(md) -> dict`; `bt_factor_dividend(md) -> dict`; `bt_factor_low_volatility(md) -> dict`; `bt_factor_multifactor(md) -> dict`; `bt_statarb_factor(md) -> dict`
- **imports:** __future__, numpy, pandas, trading.strategy.library, warnings

## `trading/strategy/library/catalog/_impl_orderflow.py`
_catalog/_impl_orderflow.py — REAL backtests for order-flow + market-making (Wave 3)._
- **functions:** `_empty(reason) -> dict`; `_flow(tf, limit)`; `_flow_signal(kind) -> dict`; `bt_cumulative_delta(md) -> dict`; `bt_aggressive_buyer(md) -> dict`; `bt_footprint(md) -> dict`; `bt_cvd_divergence(md) -> dict`; `bt_absorption(md) -> dict`; `bt_order_book_imbalance(md) -> dict`; `_mm_sim() -> dict`; `bt_avellaneda_stoikov(md) -> dict`; `bt_passive_bid_ask(md) -> dict`; `bt_inventory_based(md) -> dict`; `bt_gueant_lehalle(md) -> dict`; `bt_dynamic_spread(md) -> dict`; `bt_microprice(md) -> dict`
- **imports:** __future__, numpy, pandas, trading.strategy.library, warnings

## `trading/strategy/library/catalog/alternative_data.py`
_catalog/alternative_data.py — alternative-data alpha (Level-3 institutional, data-gated)._
- **functions:** `_g(name, family, logic, segments, data_req, oss, notes)`
- **imports:** __future__, trading.strategy.library.base

## `trading/strategy/library/catalog/breakout.py`
_catalog/breakout.py — Breakout / volatility-expansion family (executable on OHLCV)._
- **functions:** `_bb_squeeze(f)`; `_ttm_squeeze(f)`; `_atr_channel(f)`; `_lw_volatility(f)`; `_range_expansion(f)`; `_inside_bar(f)`; `_gap_and_go(f)`; `_donchian_stop(f)`; `_mk(name, family, logic, signal, oss, tf)`; `_opening_range_sig(f)`; `_cpr_pivot_sig(f)`
- **imports:** __future__, pandas, trading.strategy.library.base

## `trading/strategy/library/catalog/event_macro.py`
_catalog/event_macro.py — event-driven, macro, fundamental-factor & seasonal families (data-gated)._
- **functions:** `_g(name, category, family, logic, segments, data_req, oss, tf, notes)`
- **imports:** __future__, trading.strategy.library.base, trading.strategy.library.catalog

## `trading/strategy/library/catalog/high_frequency.py`
_catalog/high_frequency.py — HFT / market-microstructure family (data-gated)._
- **functions:** `_g(name, family, logic, segments, data_req, oss, notes)`
- **imports:** __future__, trading.strategy.library.base, trading.strategy.library.catalog

## `trading/strategy/library/catalog/machine_learning.py`
_catalog/machine_learning.py — ML / RL / regime family._
- **functions:** `_regime_hmm(f) -> pd.Series`; `_g(name, family, logic, segments, oss, data_req, notes, tf)`
- **imports:** __future__, numpy, pandas, trading.strategy.library.base, trading.strategy.library.catalog

## `trading/strategy/library/catalog/market_making.py`
_catalog/market_making.py — liquidity-provision / market-making family (data-gated)._
- **functions:** `_g(name, family, logic, segments, data_req, oss, notes)`
- **imports:** __future__, trading.strategy.library.base, trading.strategy.library.catalog

## `trading/strategy/library/catalog/mean_reversion.py`
_catalog/mean_reversion.py — Mean-Reversion family (executable on OHLCV)._
- **functions:** `_rsi_rev(f)`; `_rsi2_connors(f)`; `_bb_rev(f)`; `_pctb_rev(f)`; `_zscore_rev(f)`; `_vwap_rev(f)`; `_stoch_rev(f)`; `_stochrsi_rev(f)`; `_willr_rev(f)`; `_cci_rev(f)`; `_mfi_rev(f)`; `_keltner_rev(f)`; `_atr_overext(f)`; `_ultosc_rev(f)`; `_mk(name, family, logic, signal, oss, tf)`
- **imports:** __future__, pandas, trading.strategy.library.base

## `trading/strategy/library/catalog/meta_systems.py`
_catalog/meta_systems.py — Level-11 meta-strategy systems (data-gated portfolio layers)._
- **functions:** `_g(name, family, logic, data_req, oss, notes)`
- **imports:** __future__, trading.strategy.library.base

## `trading/strategy/library/catalog/momentum.py`
_catalog/momentum.py — Momentum family (executable on OHLCV)._
- **functions:** `_roc(f)`; `_tsmom(f)`; `_rsi_mom(f)`; `_macd_accel(f)`; `_cmo(f)`; `_ppo(f)`; `_trix(f)`; `_rvol_mom(f)`; `_obv_mom(f)`; `_breakout_mom(f)`; `_ignition(f)`; `_stoch_mom(f)`; `_mk(name, family, logic, signal, oss, tf)`
- **imports:** __future__, pandas, trading.strategy.library.base

## `trading/strategy/library/catalog/multi_indicator.py`
_catalog/multi_indicator.py — multi-indicator confluence family (executable on OHLCV)._
- **functions:** `_rsi_macd(f)`; `_pullback_cont(f)`; `_adx_gated_cross(f)`; `_triple_screen(f)`; `_bb_rsi(f)`; `_supertrend_rsi(f)`; `_vwap_rsi(f)`; `_ema_cloud(f)`; `_trend_day(f)`; `_dca_accumulate(f)`; `_grid_range(f)`; `_mk(name, family, logic, signal, oss, cat, tf, segs, short)`
- **imports:** __future__, pandas, trading.strategy.library.base

## `trading/strategy/library/catalog/options.py`
_catalog/options.py — options & options-volatility family (data-gated)._
- **functions:** `_g(name, family, logic, segments, data_req, oss, tf, notes)`
- **imports:** __future__, trading.strategy.library.base, trading.strategy.library.catalog

## `trading/strategy/library/catalog/order_flow.py`
_catalog/order_flow.py — tick-level order-flow family (data-gated)._
- **functions:** `_g(name, family, logic, segments, data_req, oss, notes, backtest)`
- **imports:** __future__, trading.strategy.library.base, trading.strategy.library.catalog

## `trading/strategy/library/catalog/pattern.py`
_catalog/pattern.py — candlestick / price-action family (executable on OHLCV)._
- **functions:** `_bull_engulf(f)`; `_hammer(f)`; `_doji_break(f)`; `_three_bar_reversal(f)`; `_marubozu(f)`; `_harami(f)`; `_mk(name, family, logic, signal, oss)`
- **imports:** __future__, pandas, trading.strategy.library.base

## `trading/strategy/library/catalog/statistical_arbitrage.py`
_catalog/statistical_arbitrage.py — stat-arb / relative-value / cross-asset arbitrage._
- **functions:** `_g(name, category, family, logic, segments, data_req, oss, tf, notes, backtest)`
- **imports:** __future__, trading.strategy.library.base, trading.strategy.library.catalog

## `trading/strategy/library/catalog/trend.py`
_catalog/trend.py — Trend-Following family (executable on OHLCV)._
- **functions:** `_ma_cross(fast, slow)`; `_sig_supertrend(f)`; `_sig_adx_di(f)`; `_sig_macd(f)`; `_sig_macd_zero(f)`; `_sig_donchian(f)`; `_sig_turtle_55(f)`; `_sig_aroon(f)`; `_sig_psar(f)`; `_sig_slope(f)`; `_sig_sma200(f)`; `_sig_kama(f)`; `_sig_tema(f)`; `_sig_triple_ma(f)`; `_sig_st_macd(f)`
- **imports:** __future__, pandas, trading.strategy.library.base

## `trading/strategy/library/catalog/volatility.py`
_catalog/volatility.py — realized-volatility regime family (executable on OHLCV)._
- **functions:** `_vol_expansion_trend(f)`; `_lowvol_meanrev(f)`; `_bb_width_expansion(f)`; `_vol_compression_anticipation(f)`; `_mk(name, family, logic, signal, oss, tf)`
- **imports:** __future__, pandas, trading.strategy.library.base

## `trading/strategy/library/catalog/volume_flow.py`
_catalog/volume_flow.py — volume / money-flow family (executable on OHLCV+volume)._
- **functions:** `_obv_trend(f)`; `_adosc(f)`; `_volume_breakout(f)`; `_rvol_shock(f)`; `_vwap_trend(f)`; `_mfi_trend(f)`; `_accumulation(f)`; `_vp_failed_auction(f)`; `_vp_value_position(f)`; `_mk(name, family, logic, signal, oss, tf)`
- **imports:** __future__, pandas, trading.strategy.library.base

## `trading/strategy/library/created.py`
_trading/strategy/library/created.py — brain-CREATED strategies as first-class library entries._
- **functions:** `_segments_for(market) -> tuple`; `_guarded_signal(candidate)`; `load_created_strategies() -> list[LibraryStrategy]`; `created_store_signature(state_file)`
- **imports:** __future__, os, pandas, trading.strategy.library.base

## `trading/strategy/library/data_sources/__init__.py`
_trading/strategy/library/data_sources/ — REAL data fetchers for the library strategies._
- **functions:** `cache_path(name) -> str`
- **imports:** __future__, os

## `trading/strategy/library/data_sources/crypto_deriv.py`
_data_sources/crypto_deriv.py — ccxt crypto-derivatives data (funding, OHLCV, OI, basis)._
- **functions:** `_ccxt(exchange, market_type)`; `_ohlcv_df(rows) -> pd.DataFrame`; `fetch_ohlcv(symbol) -> pd.DataFrame`; `fetch_funding_history(symbol) -> pd.Series`; `fetch_open_interest_history(symbol) -> pd.Series`; `load_market(symbol) -> MarketData`
- **imports:** __future__, numpy, pandas, time, trading.strategy.library.data_sources, trading.strategy.library.marketdata

## `trading/strategy/library/data_sources/deribit_options.py`
_data_sources/deribit_options.py — REAL free Deribit option-chain + IV/RV data (Wave 1B)._
- **functions:** `_ccxt_deribit()`; `_cached(key, ttl, fn)`; `load_chain(currency) -> pd.DataFrame`; `_dvol(currency) -> pd.Series`; `_realized_vol(currency) -> pd.Series`; `iv_rv_series(currency) -> pd.DataFrame`
- **imports:** __future__, numpy, pandas, time

## `trading/strategy/library/data_sources/multi_asset.py`
_data_sources/multi_asset.py — REAL multi-symbol crypto price panel (Wave 1C)._
- **functions:** `load_panel(symbols) -> pd.DataFrame`
- **imports:** __future__, numpy, pandas, time

## `trading/strategy/library/data_sources/nse_fundamentals.py`
_data_sources/nse_fundamentals.py — REAL NSE fundamentals + price panel (Wave 2, free via yfinance)._
- **functions:** `price_panel(tickers) -> pd.DataFrame`; `fundamentals(tickers) -> pd.DataFrame`
- **imports:** __future__, numpy, pandas, time

## `trading/strategy/library/data_sources/orderflow.py`
_data_sources/orderflow.py — REAL order-flow + L2 snapshot data (Wave 3)._
- **functions:** `_binance()`; `flow_series(symbol) -> pd.DataFrame`; `order_book_snapshot(symbol) -> dict | None`
- **imports:** __future__, numpy, pandas, time

## `trading/strategy/library/evaluators.py`
_trading/strategy/library/evaluators.py — backtest evaluators for data-backed strategies._
- **functions:** `metrics_from_returns(rets) -> dict`; `carry_metrics(funding) -> dict`; `basis_convergence_metrics(basis) -> dict`; `signal_returns_metrics(close, signal) -> dict`
- **imports:** __future__, numpy, pandas

## `trading/strategy/library/features_ext.py`
_trading/strategy/library/features_ext.py — extended causal indicator frame (TA-Lib)._
- **functions:** `_supertrend(high, low, close, atr, mult) -> tuple[pd.Series, pd.Series]`; `compute_features_ext(ohlcv) -> pd.DataFrame`; `_rolling_vp(df, h, l, c, v, window) -> None`; `_pandas_fallback(df, o, h, l, c, v, fast, slow, mom_n, bb_n, bb_k)`
- **imports:** __future__, numpy, pandas

## `trading/strategy/library/marketdata.py`
_trading/strategy/library/marketdata.py — multi-input data context for library strategies._
- **classes:** MarketData
- **imports:** __future__, dataclasses, pandas

## `trading/strategy/library/registry.py`
_trading/strategy/library/registry.py — collect the catalog + coverage stats._
- **classes:** LibraryRegistry
- **functions:** `_load_all() -> list[LibraryStrategy]`; `get_registry() -> LibraryRegistry`; `all_strategies() -> list[LibraryStrategy]`
- **imports:** __future__, dataclasses, importlib, trading.strategy.library.base

## `trading/strategy/library/run.py`
_trading/strategy/library/run.py — backtest the executable library + rank a leaderboard._
- **functions:** `synth_ohlcv(n, seed) -> pd.DataFrame`; `_oos_tail(feats)`; `_score_one(strat, feats) -> dict`; `_rank_key(m) -> tuple`; `_pick_market(strat) -> str`; `run_library(ohlcv_by_market) -> dict`; `build_library_snapshot() -> dict`; `_fmt(m) -> str`; `main() -> int`
- **imports:** __future__, numpy, pandas, trading.strategy.backtest, trading.strategy.library.features_ext, trading.strategy.library.registry, warnings

## `trading/strategy/metalabel.py`
_trading/strategy/metalabel.py — meta-labeling gate (Pillar 20, López de Prado ch. 3)._
- **classes:** MetaLabeler
- **functions:** `_atr(ohlcv, n) -> np.ndarray`; `_tb_core(close, atr, sig, pt, sl, max_hold)`; `triple_barrier_labels(ohlcv, signal) -> pd.DataFrame`; `_auc(y, p) -> float`; `_fit_logistic(X, y) -> dict`; `_predict_logistic(params, X) -> np.ndarray`
- **imports:** __future__, dataclasses, numpy, pandas

## `trading/strategy/operators.py`
_trading/strategy/operators.py — mutation + crossover via DEAP gp (T8.1, reuse-first)._
- **functions:** `market_features(market) -> list[str]`; `_safe_expr(pset, type_)`; `_mutate_tree(src, pset, rng)`; `mutate(strategy, features, rng) -> Strategy`; `crossover(a, b, rng) -> tuple`
- **imports:** __future__, copy, deap, numpy, random, trading.strategy.features, trading.strategy.genome

## `trading/strategy/registry.py`
_trading/strategy/registry.py — promote evolved strategies to NodeProtocol nodes (T8.3)._
- **classes:** StrategyNode, StrategyRegistry
- **functions:** `promote(strategy, features) -> StrategyNode`
- **imports:** __future__, core.node_protocol, dataclasses, numpy, pandas, trading.strategy.genome

## `trading/strategy/run_autoresearch.py`
_trading/strategy/run_autoresearch.py — daemon entry for the live autoresearch loop._
- **functions:** `_sig(_signum, _frame)`; `main() -> int`
- **imports:** __future__, logging, os, signal, sys, time

## `trading/strategy/self_evolve.py`
_trading/strategy/self_evolve.py — the lifelong self-evolving strategy loop._
- **classes:** SelfEvolvingLoop, SelfEvolveNode
- **functions:** `register_self_evolve(loop) -> SelfEvolveNode`
- **imports:** __future__, core.node_protocol, numpy, pandas, trading.brain.skills, trading.strategy.control, trading.strategy.evolve, trading.strategy.fitness, trading.strategy.genome

## `trading/sweep.py`
_Logged hyperparameter / lookback / topology sweep harness (CANON-34)._
- **functions:** `grid() -> list`; `chrono_split(n, val_frac) -> tuple`; `run_sweep(build_fn, X, y, params_grid) -> dict`; `_jsonable(params) -> dict`; `_now() -> float`
- **imports:** __future__, itertools, json, numpy, os, time, trading.classification_eval

## `trading/tick_cache.py`
_trading/tick_cache.py — per-symbol real-time price cache (T1 §5)._
- **classes:** Tick, TickCache, MarketFeed
- **imports:** __future__, dataclasses, threading, time, trading.openalgo_client

## `trading/uq/__init__.py`
_trading/uq — calibrated uncertainty for trade decisions (Pillar 17)._
- **imports:** trading.uq.conformal

## `trading/uq/conformal.py`
_trading/uq/conformal.py — conformal trade-outcome calibration (Pillar 17)._
- **classes:** TradeUQ
- **functions:** `self_uncertainty_from_votes(longs, shorts) -> float | None`; `_feat(conf, direction, market, psych) -> list[float]`; `_trade_conf(t)`; `get_uq() -> TradeUQ`
- **imports:** __future__, math, numpy, os, threading, time, trading

## `trading/validation_holdout.py`
_CORTEX B8 — live-unseen validation protocol (CANON-42)._
- **functions:** `_jsonl_path() -> Path`; `_accuracy_path() -> Path`; `record_prediction(ts, symbol, pred, horizon) -> dict`; `_load_all() -> list[dict]`; `_rewrite(records) -> None`; `_candle_close(symbol, ts) -> float | None`; `score_matured(now) -> dict`
- **imports:** __future__, json, os, pathlib, time

## `trading/watchlist.py`
_trading/watchlist.py — persisted NSE watchlist (T1 §6)._
- **classes:** WatchItem, Watchlist
- **imports:** __future__, dataclasses, trading, trading.instruments, trading.tick_cache
