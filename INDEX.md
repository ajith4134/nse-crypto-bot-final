# INDEX.md — AUTO-GENERATED. Do not edit by hand.

Regenerate with `make index` (parses the source via AST).

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

## `.pytensor/compiledir_Linux-6.12-cloud-amd64-x86_64-with-glibc2.41--3.13.5-64/__init__.py`
_(no summary)_

## `.pytensor/compiledir_Linux-6.12-cloud-amd64-x86_64-with-glibc2.41--3.13.5-64/lazylinker_ext/__init__.py`
_(no summary)_

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

## `core/heads.py`
_Output heads — the multi-output contract for the prediction-graph network._
- **classes:** OutputHead
- **imports:** __future__, dataclasses

## `core/node_protocol.py`
_Node interface contracts for the prediction-graph network._
- **classes:** IOSchema, NodeProtocol, NodeInfo, BaseNode
- **imports:** __future__, dataclasses, typing

## `core/registry.py`
_Live node registry — the single source of truth the dashboard reads._
- **functions:** `register(node, summary, upstream) -> None`; `set_metrics(name, metrics, trained) -> None`; `reset() -> None`; `snapshot() -> dict`
- **imports:** __future__, core.node_protocol

## `dashboard/server.py`
_dashboard/server.py — zero-dependency dashboard server (stdlib http.server)._
- **classes:** Handler
- **functions:** `main() -> None`
- **imports:** __future__, base64, http.server, json, os, sys

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

## `data/sources.py`
_Crypto data sources (stdlib HTTP only)._
- **functions:** `_get_json(url, headers, timeout) -> dict`; `_write_csv(rows, path, header) -> None`; `coingecko_daily(coin, days, vs) -> list[tuple]`; `fetch_coin(coin, days) -> tuple[str, int]`; `load_coin(coin) -> list[tuple]`; `etherscan_gas_oracle() -> dict`; `coinalyze_funding(symbol) -> dict`
- **imports:** __future__, config, json, os, time, urllib.request

## `eval/__init__.py`
_(no summary)_

## `eval/golden.py`
_Golden datasets + evaluation — the 'known input->output first' discipline._
- **functions:** `make_golden_dataset(n, noise, seed) -> tuple[Matrix, Labels]`; `train_test_split(X, y, test_frac, seed) -> tuple[Matrix, Labels, Matrix, Labels]`; `accuracy(pred, y) -> float`; `argmax_labels(pred_output) -> Labels`; `_macro_f1(pred, y, n_classes) -> float`; `_r2(pred, y) -> float`; `score_head(head, pred_output, y) -> dict`; `baseline_for(head, y_train, y_test) -> dict`
- **imports:** __future__, core.heads, core.node_protocol, numpy, random

## `memory/__init__.py`
_(no summary)_

## `memory/brain.py`
_KnowledgeBrain — the Phase-4 brain/memory layer._
- **classes:** KnowledgeBrain
- **functions:** `_slug(s) -> str`; `_chunk(text, words) -> list[str]`; `_read_pdf(path) -> str`; `_html_to_text(raw) -> str`
- **imports:** __future__, collections, html, itertools, memory.graph, memory.store, os, re, urllib.request

## `memory/graph.py`
_KnowledgeGraph — concept graph backed by NetworkX (reuse-first)._
- **classes:** _NetworkxGraph, _DictGraph
- **functions:** `KnowledgeGraph()`
- **imports:** __future__

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

## `nodes/automl_node.py`
_AutoGluonNode — the plan's Phase-1 *production* stacked-ensemble node._
- **classes:** AutoGluonNode
- **imports:** __future__, core.node_protocol, numpy, tempfile

## `nodes/base_learners.py`
_Base prediction nodes (pure-Python, CPU-only, zero deps)._
- **classes:** LogisticRegressionNode, KNNNode, DecisionStumpNode
- **functions:** `_sigmoid(z) -> float`
- **imports:** __future__, core.node_protocol, math, native

## `nodes/chaos_nodes.py`
_Step 3: chaos / nonlinear-dynamics node families (pure-Python)._
- **classes:** RecurrenceNode, ChaosFeatureNode
- **imports:** __future__, core.node_protocol, native, nodes.base_learners

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
- **classes:** _ARFallback, _DLForecastBase, NHiTSNode, TCNNode, NBEATSNode, TSMixerNode, GRUNode, AEAnomalyNode
- **functions:** `_silence()`; `_timeseries(y)`; `nhits_node(name)`; `tcn_node(name)`; `nbeats_node(name)`; `tsmixer_node(name)`; `gru_node(name)`; `ae_anomaly_node(name)`
- **imports:** __future__, core.node_protocol, nodes.quant_nodes, numpy, time, warnings

## `nodes/dynamics_nodes.py`
_Nonlinear-dynamics / chaos / physics nodes — the reuse-first dynamics layer._
- **classes:** _Base, SINDyNode, RQANode, PermEntropyNode, AntropyNode, DMDNode, TransferEntropyNode
- **functions:** `sindy_node(name, col, W) -> SINDyNode`; `rqa_node(name, col, W) -> RQANode`; `permentropy_node(name, col, W) -> PermEntropyNode`; `antropy_node(name, col, W) -> AntropyNode`; `dmd_node(name, col, W) -> DMDNode`; `transfer_entropy_node(name, col, col2, W) -> TransferEntropyNode`
- **imports:** __future__, core.node_protocol, numpy, warnings

## `nodes/frontier_nodes.py`
_Frontier nodes: quantum-inspired kernels, a reinforcement-learning policy, and_
- **classes:** QuantumKernelNode, RLPolicyNode, OptionIVNode
- **functions:** `_http_json(url, timeout) -> dict`; `quantum_kernel_node(name)`; `rl_policy_node(name)`; `option_iv_node(name)`
- **imports:** __future__, core.node_protocol, json, nodes.quant_nodes, numpy, os, ssl, time, urllib.request, warnings

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

## `nodes/ml_nodes.py`
_Advanced ML / topology / control nodes — the reuse-first expansion of the_
- **classes:** _HeadMixin, _FeatureBase, Catch22Node, TsfreshNode, TDANode, CausalSelectNode, GaussianProcessNode, _ForecastBase, DartsForecastNode, ControlSysIDNode
- **functions:** `_readout(task)`; `_ar_fit(s, p)`; `_ar_forecast_column(coef, c0, p, s_train, s_eval) -> np.ndarray`; `gaussian_process_node(max_rows, name) -> GaussianProcessNode`; `catch22_node(win, col, name) -> Catch22Node`; `tsfresh_node(win, col, name) -> TsfreshNode`; `tda_node(win, col, name) -> TDANode`; `causal_select_node(top_k, name) -> CausalSelectNode`; `darts_forecast_node(lags, col, name) -> DartsForecastNode`; `control_sysid_node(lags, col, name) -> ControlSysIDNode`
- **imports:** __future__, core.node_protocol, numpy, warnings

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
- **functions:** `_oss_candidates()`; `factories()`; `names()`
- **imports:** __future__, nodes.base_learners, nodes.chaos_nodes, nodes.phase2_nodes, nodes.phase2b_nodes

## `nodes/probabilistic_nodes.py`
_Uncertainty / probabilistic / symbolic / fuzzy / survival nodes._
- **classes:** _HeadBase, ConformalNode, ProphetNode, GplearnSymbolicNode, FuzzyTSNode, BayesianNode, SurvivalHazardNode
- **functions:** `_readout(task)`; `_base_matrix(X) -> np.ndarray`; `conformal_node()`; `prophet_node()`; `gplearn_symbolic_node()`; `fuzzy_ts_node()`; `bayesian_node()`; `survival_hazard_node()`
- **imports:** __future__, core.node_protocol, logging, numpy, os, time, warnings

## `nodes/quant_nodes.py`
_Quant / finance / math-structure nodes — OSS time-series & extreme-value_
- **classes:** _QBase, _FeatNode, _PredNode, GarchVolNode, EVTTailNode, StateSpaceNode, StatsForecastNode, ADFStationarityNode, CointSpreadNode, _HeadBase, _WindowFeat, EWMAVolNode
- **functions:** `_quiet()`; `garch_vol_node(col, win, name) -> GarchVolNode`; `evt_tail_node(col, win, name) -> EVTTailNode`; `state_space_node(col, win, name) -> StateSpaceNode`; `statsforecast_node(col, win, name) -> StatsForecastNode`; `adf_stationarity_node(col, win, name) -> ADFStationarityNode`; `coint_spread_node(col0, col1, win, name) -> CointSpreadNode`; `_compat_readout(task)`; `ewma_vol_node(name)`
- **imports:** __future__, contextlib, core.node_protocol, numpy, warnings

## `nodes/router_node.py`
_LearnedRouterNode — Phase 3: dynamic routing between full-model nodes._
- **classes:** LearnedRouterNode
- **functions:** `_roughness(x) -> float`
- **imports:** __future__, core.node_protocol, native

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

## `nodes/symbolic_node.py`
_PySRNode — the plan's Phase-5 equation-discovery node._
- **classes:** PySRNode
- **imports:** __future__, core.node_protocol, numpy

## `nodes/universal_node.py`
_UniversalNode — builds a NodeProtocol node from any AlgoSpec (core/algo_registry)._
- **classes:** UniversalNode
- **functions:** `build_nodes(task) -> list`
- **imports:** __future__, core.algo_registry, core.node_protocol, numpy, os, warnings

## `run_brain.py`
_run_brain.py — Step 1: let the brain GROW the network from a candidate pool._
- **functions:** `_split3(X, y, a, b)`; `_split3_shuffled(X, y, seed)`; `_split4(X, y, a, b, c)`; `_split4_shuffled(X, y, seed)`; `main(benchmark) -> dict`
- **imports:** __future__, core, core.brain, data.benchmarks, eval.golden, json, nodes.pool, os, random, sys, time

## `run_chaos_compare.py`
_Step 3 evidence: do chaos-feature nodes hold accuracy better under noise?_
- **functions:** `main() -> dict`
- **imports:** __future__, data.benchmarks, data.dataset, eval.golden, nodes.chaos_nodes, nodes.phase2_nodes

## `run_crypto.py`
_run_crypto.py — train the prediction-graph network on REAL crypto data._
- **functions:** `main(coin, days) -> dict`
- **imports:** __future__, core, data.dataset, eval.golden, json, nodes.base_learners, nodes.phase2_nodes, nodes.stacking_node, os, time

## `run_dev.py`
_run_dev.py — train the growing network on a synthetic benchmark (default data)._
- **functions:** `noise_sweep(levels) -> list[dict]`; `main(benchmark) -> dict`
- **imports:** __future__, core, data.benchmarks, data.dataset, eval.golden, json, nodes.base_learners, nodes.phase2_nodes, nodes.phase2b_nodes, nodes.router_node, nodes.stacking_node, os, sys, time

## `run_intradaywf.py`
_Walk-forward (chronological) on Binance INTRADAY klines — more samples/structure._
- **functions:** `eval_symbol(symbol, interval, target)`; `main(target, interval, total) -> dict`
- **imports:** __future__, core.brain, data.binance, eval.golden, json, nodes.pool, os, run_realwf, sys

## `run_knowledge.py`
_Phase 4 demo: build the knowledge brain, ingest docs, and recall._
- **functions:** `_wiki(title) -> str | None`; `main() -> dict`
- **imports:** __future__, json, memory.brain, os, urllib.request

## `run_multi.py`
_run_multi.py — the MULTI-OUTPUT network: an output layer of several heads._
- **classes:** _MetaView
- **functions:** `cls_pool()`; `reg_pool()`; `domain_pool()`; `_combine(outputs, task)`; `_load_synthetic(benchmark, n)`; `_load_crypto(train_frac)`; `_split_dataset(ds, cap, train_frac)`; `_load_external(source)`; `main(arg, n, pool) -> dict`
- **imports:** __future__, core, core.heads, data.benchmarks, eval.golden, json, nodes, numpy, os, sys, time, warnings

## `run_noise_router.py`
_(ii) Demonstrate the noise-regime router beating either single expert._
- **functions:** `_split(X, y, reg, frac, seed)`; `_by_regime(pred, y, reg)`; `main() -> dict`
- **imports:** __future__, core, data.benchmarks, eval.golden, json, nodes.base_learners, nodes.chaos_nodes, nodes.noise_router, nodes.phase2_nodes, os, random, time

## `run_oss.py`
_run_oss.py — train the REUSE-FIRST (OSS-backed) node layer and emit state.json._
- **functions:** `main(benchmark, with_autogluon) -> dict`
- **imports:** __future__, core, data.benchmarks, data.dataset, eval.golden, json, nodes, nodes.stacking_node, numpy, os, sys, time, warnings

## `run_phase1.py`
_run_phase1.py — train the Phase-1 prediction-graph network and emit state.json._
- **functions:** `main() -> dict`
- **imports:** __future__, core, eval.golden, json, nodes.base_learners, nodes.stacking_node, os, time

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

## `run_unified_router.py`
_(2) Fold regime-routing into the main learned_router._
- **functions:** `_split(X, y, reg, frac, seed)`; `_by_regime(pred, y, reg)`; `main() -> dict`
- **imports:** __future__, core, data.benchmarks, eval.golden, json, nodes.base_learners, nodes.chaos_nodes, nodes.phase2_nodes, nodes.phase2b_nodes, nodes.router_node, os, random, time

## `tests/test_domain_nodes.py`
_Acceptance test: the PhD-domain node modules import and conform to NodeProtocol._
- **classes:** TestDomainNodes
- **imports:** __future__, core.node_protocol, data.benchmarks, data.dataset, unittest

## `tests/test_knowledge.py`
_Acceptance tests for the Phase-4 knowledge brain: ingest -> recall works._
- **classes:** TestKnowledge
- **imports:** __future__, memory.brain, unittest

## `tests/test_multihead.py`
_Acceptance test (multi-output): every output head must beat its task baseline._
- **classes:** TestMultiHead
- **imports:** __future__, run_multi, unittest

## `tests/test_pipeline.py`
_Phase-0/1 acceptance tests: interface enforcement + the learning loop works._
- **classes:** TestPipeline
- **imports:** __future__, core.node_protocol, eval.golden, nodes.base_learners, nodes.stacking_node, unittest

## `tests/test_robust.py`
_Acceptance test (hardening): the router-grown brain must beat the naive_
- **classes:** TestRobust
- **imports:** __future__, run_robust, unittest

## `tools/gen_index.py`
_gen_index.py — auto-generate INDEX.md from the source tree (AST, stdlib only)._
- **functions:** `_sig(fn) -> str`; `_summarize(path) -> dict`; `_iter_py() -> list[str]`; `build() -> str`
- **imports:** __future__, ast, os

## `tools/orderbook_collector.py`
_Live Binance L2 order-book snapshot collector (no key)._
- **functions:** `snapshot(symbol, levels)`; `main(symbol, every)`
- **imports:** __future__, json, os, sys, time, urllib.request
