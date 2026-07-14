"""
Labeled skill-retrieval dataset for the Phoenix-Evo retrieval benchmark.

Corpus
------
40 skill cards. 15 are grounded in artifacts that exist in this repository
(the 8-skill test corpus from tests/test_semantic_retrieval.py plus 7 skills
distilled from real skill cards under skills/active, skills/archived and
skills/draft). The remaining 25 are realistic distractor/domain skills so
that retrieval has a non-trivial search space.

Queries and relevance judgments (qrels)
---------------------------------------
60 queries in five categories:

    exact_keyword  (10)  query shares vocabulary with the target skill
    paraphrase     (20)  same intent, minimal lexical overlap
    cross_domain   (10)  related domain; tests fine-grained discrimination
    multi_intent    (8)  two primary relevant skills
    negative       (12)  no relevant skill exists in the corpus

Relevance grades:
    2 = primary: the skill directly addresses the query intent
    1 = partial: the skill is helpful but incomplete for the intent
    (absent = grade 0, not relevant)

Annotation provenance
---------------------
Judgments were produced by a single annotator (project author) following the
written criteria above, then reviewed in a second pass one day later.
This is disclosed in the benchmark report; independent multi-annotator
validation (with inter-annotator agreement) is future work and the qrels
format supports adding annotator columns without breaking consumers.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Skill:
    skill_id: str
    skill_name: str
    text: str
    # True if this card is grounded in a real artifact in this repository
    grounded_in_repo: bool = False


@dataclass(frozen=True)
class Query:
    query_id: str
    text: str
    category: str  # exact_keyword | paraphrase | cross_domain | multi_intent | negative
    qrels: dict[str, int] = field(default_factory=dict)  # skill_id -> grade (1|2)


def searchable_text(skill: Skill) -> str:
    """Build the text that retrieval methods index for a skill."""
    name_words = skill.skill_name.replace("_", " ")
    return f"{name_words}. {skill.text}"


# ---------------------------------------------------------------------------
# Corpus: 40 skills
# ---------------------------------------------------------------------------

SKILLS: list[Skill] = [
    # --- 8 skills from tests/test_semantic_retrieval.py (repo test corpus) ---
    Skill("skill_wsl_encoding", "fix_wsl_chinese_path_encoding",
          "Fix encoding issues with Chinese characters in WSL paths. When dealing with "
          "WSL file system paths that contain Chinese characters and cause encoding "
          "errors or garbled output.", grounded_in_repo=True),
    Skill("skill_git_merge", "resolve_git_merge_conflict",
          "Resolve merge conflicts in git repositories. When a git merge or rebase "
          "produces merge conflicts that need to be resolved manually.", grounded_in_repo=True),
    Skill("skill_api_auth", "implement_jwt_authentication",
          "Implement JWT-based authentication for REST APIs. When building API endpoints "
          "that require JSON Web Token based authentication and authorization.", grounded_in_repo=True),
    Skill("skill_docker_deploy", "deploy_application_with_docker",
          "Deploy applications using Docker and Docker Compose. When deploying a Python "
          "or Node.js application using Docker containers.", grounded_in_repo=True),
    Skill("skill_sql_optimize", "optimize_slow_sql_queries",
          "Optimize slow SQL queries through indexing and rewriting. When database "
          "queries are running slowly and need performance optimization.", grounded_in_repo=True),
    Skill("skill_react_component", "create_react_component_with_tests",
          "Create React components with TypeScript and unit tests. When building a new "
          "React component that needs unit tests and proper type definitions.", grounded_in_repo=True),
    Skill("skill_network_debug", "diagnose_network_connectivity_issues",
          "Diagnose and fix network connectivity issues. When experiencing network "
          "connectivity problems such as DNS resolution failures or timeout errors.", grounded_in_repo=True),
    Skill("skill_python_caching", "implement_redis_caching_layer",
          "Implement Redis-based caching for Python applications. When adding a caching "
          "layer to reduce database load and improve response times.", grounded_in_repo=True),

    # --- 7 skills distilled from real skill cards in skills/ ---
    Skill("skill_error_contract", "treat_error_message_as_contract_signal",
          "Treat error messages as contract signals rather than free text. When parsing "
          "or matching on error output, rely on stable identifiers such as error codes "
          "and exception class names instead of full message strings that change "
          "between library versions.", grounded_in_repo=True),
    Skill("skill_safe_file_reconstruction", "safe_file_reconstruction",
          "Reconstruct damaged or partially written files safely. When a file has been "
          "corrupted or truncated, create a backup copy first, rebuild content into a "
          "temporary file, verify it, and atomically replace the original.", grounded_in_repo=True),
    Skill("skill_signature_first_debugging", "signature_first_debugging",
          "Check function signatures before patching call sites. When a call fails with "
          "argument errors, inspect the current signature of the callee first instead "
          "of guessing, then update all call sites consistently.", grounded_in_repo=True),
    Skill("skill_syntax_validation", "syntax_validation_before_overwrite",
          "Validate syntax before overwriting files. When generating or rewriting source "
          "code files, parse and syntax-check the new content before replacing the "
          "existing file to avoid leaving the project in a broken state.", grounded_in_repo=True),
    Skill("skill_null_byte_repair", "repair_null_byte_corrupted_writes",
          "Repair files corrupted with null bytes after failed writes on WSL Chinese "
          "paths. When file writes to paths containing Chinese characters produce "
          "files padded with null bytes, detect the corruption and rewrite the file "
          "using a safe encoding-aware method.", grounded_in_repo=True),
    Skill("skill_tcm_api", "build_tcm_syndrome_differentiation_api",
          "Build a Traditional Chinese Medicine syndrome differentiation reasoning API. "
          "When implementing a service that maps symptom inputs to TCM syndrome "
          "patterns and exposes the reasoning through a REST interface.", grounded_in_repo=True),
    Skill("skill_workflow_orchestration", "build_multi_node_workflow_orchestration",
          "Build a multi-node dataflow workflow orchestration engine. When tasks must "
          "be arranged as a graph of dependent nodes where outputs of one step feed "
          "the inputs of the next, with scheduling and failure handling.", grounded_in_repo=True),

    # --- 25 realistic domain skills (distractors and additional targets) ---
    Skill("skill_pandas_cleaning", "clean_tabular_data_with_pandas",
          "Clean messy tabular data with pandas. When CSV or Excel exports contain "
          "missing values, inconsistent types, duplicated rows, or malformed columns "
          "that must be normalized before analysis."),
    Skill("skill_regex_extraction", "extract_fields_with_regular_expressions",
          "Extract structured fields from semi-structured text using regular "
          "expressions. When log lines or documents contain repeating patterns such "
          "as dates, identifiers, or key-value pairs that need to be captured."),
    Skill("skill_ci_github_actions", "setup_github_actions_ci",
          "Set up continuous integration pipelines with GitHub Actions. When a "
          "repository needs automated build, test, and lint workflows triggered on "
          "pushes and pull requests."),
    Skill("skill_k8s_deployment", "deploy_service_to_kubernetes",
          "Deploy services to a Kubernetes cluster. When an application must run on "
          "Kubernetes with deployments, services, ingress, and resource limits, "
          "optionally packaged with Helm charts."),
    Skill("skill_nginx_reverse_proxy", "configure_nginx_reverse_proxy",
          "Configure Nginx as a reverse proxy with TLS termination. When routing "
          "incoming HTTPS traffic to backend services with proper certificates, "
          "headers, and timeouts."),
    Skill("skill_oauth2_flow", "implement_oauth2_authorization_code_flow",
          "Implement the OAuth2 authorization code flow with third-party identity "
          "providers. When adding social sign-in such as Google or GitHub login to "
          "an application."),
    Skill("skill_rate_limiting", "add_api_rate_limiting",
          "Add rate limiting to API endpoints. When endpoints must be protected from "
          "abuse or brute force by limiting requests per client with token bucket or "
          "sliding window algorithms."),
    Skill("skill_websocket_realtime", "push_realtime_updates_with_websockets",
          "Push real-time updates to browsers with WebSockets. When clients need live "
          "data such as notifications, scores, or dashboards without HTTP polling."),
    Skill("skill_grpc_service", "design_grpc_service_with_protobuf",
          "Design gRPC services with protocol buffers. When services need efficient "
          "typed RPC communication with generated client and server stubs."),
    Skill("skill_message_queue", "process_jobs_with_message_queue",
          "Process background jobs with a message queue. When work must be executed "
          "asynchronously by workers consuming from RabbitMQ or Kafka with retries "
          "and dead letter handling."),
    Skill("skill_db_migration", "run_safe_database_schema_migrations",
          "Run safe database schema migrations. When altering tables in production "
          "with tools like Alembic or Flyway while avoiding downtime and data loss."),
    Skill("skill_memory_leak", "diagnose_python_memory_leaks",
          "Diagnose memory leaks in long-running Python services. When resident "
          "memory grows over time, use heap snapshots and object graph analysis to "
          "find leaking references."),
    Skill("skill_cpu_profiling", "profile_cpu_hotspots",
          "Profile CPU hotspots in applications. When a process consumes excessive "
          "processor time, use sampling profilers such as py-spy or cProfile to "
          "locate the hottest functions."),
    Skill("skill_log_aggregation", "centralize_logs_with_structured_logging",
          "Centralize logs from multiple servers with structured logging. When log "
          "events must be shipped to a searchable store such as an ELK stack with "
          "consistent JSON fields."),
    Skill("skill_prometheus_monitoring", "monitor_services_with_prometheus",
          "Monitor services with Prometheus metrics and Grafana alerting. When "
          "services need instrumentation, dashboards, and alerts on error rates or "
          "latency thresholds."),
    Skill("skill_secrets_management", "manage_application_secrets",
          "Manage application secrets safely. When API keys, passwords, and "
          "certificates must be stored outside source code using vaults or "
          "environment-based configuration."),
    Skill("skill_sql_injection_review", "review_code_for_sql_injection",
          "Review code for SQL injection vulnerabilities. When user input reaches "
          "database queries, ensure parameterized statements and reject string "
          "concatenation of untrusted values."),
    Skill("skill_xss_hardening", "prevent_cross_site_scripting",
          "Prevent cross-site scripting attacks in web applications. When rendering "
          "user-supplied content, apply output encoding, sanitization, and content "
          "security policy headers."),
    Skill("skill_unit_test_pytest", "write_pytest_unit_tests",
          "Write unit tests with pytest. When Python code needs automated tests using "
          "fixtures, parametrization, and mocking of external dependencies."),
    Skill("skill_e2e_playwright", "automate_browser_tests_with_playwright",
          "Automate end-to-end browser tests with Playwright. When user flows such as "
          "sign-up or checkout must be exercised in a real browser with assertions "
          "on page state."),
    Skill("skill_data_visualization", "create_charts_for_data_analysis",
          "Create charts for data analysis with matplotlib or plotly. When numeric "
          "results must be turned into line, bar, or scatter visualizations for "
          "reports and dashboards."),
    Skill("skill_excel_reporting", "generate_excel_reports",
          "Generate Excel reports programmatically. When analysis results must be "
          "exported as spreadsheets with formatting, formulas, and multiple sheets "
          "using openpyxl."),
    Skill("skill_pdf_extraction", "extract_content_from_pdf_documents",
          "Extract text and tables from PDF documents. When data locked inside PDF "
          "invoices or reports must be parsed into structured form."),
    Skill("skill_web_scraping", "scrape_websites_responsibly",
          "Scrape websites responsibly with requests and BeautifulSoup. When data "
          "must be collected from web pages while respecting robots.txt, rate "
          "limits, and pagination."),
    Skill("skill_i18n_localization", "add_internationalization_support",
          "Add internationalization and localization support to applications. When "
          "user interfaces must support multiple languages with message catalogs, "
          "locale-aware formatting, and translation workflows."),
]


# ---------------------------------------------------------------------------
# Queries: 60 with graded qrels
# ---------------------------------------------------------------------------

QUERIES: list[Query] = [
    # ---------------- exact_keyword (10) ----------------
    Query("q01", "fix encoding issue in WSL path", "exact_keyword",
          {"skill_wsl_encoding": 2, "skill_null_byte_repair": 1}),
    Query("q02", "resolve git merge conflict", "exact_keyword",
          {"skill_git_merge": 2}),
    Query("q03", "JWT authentication for REST API", "exact_keyword",
          {"skill_api_auth": 2, "skill_oauth2_flow": 1}),
    Query("q04", "optimize slow SQL query", "exact_keyword",
          {"skill_sql_optimize": 2}),
    Query("q05", "deploy application with docker compose", "exact_keyword",
          {"skill_docker_deploy": 2, "skill_k8s_deployment": 1}),
    Query("q06", "diagnose network connectivity issues", "exact_keyword",
          {"skill_network_debug": 2}),
    Query("q07", "Redis caching layer for Python application", "exact_keyword",
          {"skill_python_caching": 2}),
    Query("q08", "write pytest unit tests with fixtures", "exact_keyword",
          {"skill_unit_test_pytest": 2, "skill_e2e_playwright": 1}),
    Query("q09", "configure nginx reverse proxy with TLS", "exact_keyword",
          {"skill_nginx_reverse_proxy": 2}),
    Query("q10", "set up GitHub Actions CI pipeline", "exact_keyword",
          {"skill_ci_github_actions": 2}),

    # ---------------- paraphrase (20) ----------------
    Query("q11", "Unicode filenames come out garbled under Windows Subsystem for Linux",
          "paraphrase", {"skill_wsl_encoding": 2, "skill_null_byte_repair": 1}),
    Query("q12", "two branches changed the same lines, how do I reconcile them",
          "paraphrase", {"skill_git_merge": 2}),
    Query("q13", "add token-based login security to my web service",
          "paraphrase", {"skill_api_auth": 2, "skill_oauth2_flow": 1}),
    Query("q14", "database reads keep timing out, make them faster",
          "paraphrase", {"skill_sql_optimize": 2, "skill_python_caching": 1}),
    Query("q15", "containerize my Python web app for production",
          "paraphrase", {"skill_docker_deploy": 2, "skill_k8s_deployment": 1}),
    Query("q16", "cannot reach the backend, requests hang forever",
          "paraphrase", {"skill_network_debug": 2}),
    Query("q17", "speed up repeated lookups by remembering recent answers",
          "paraphrase", {"skill_python_caching": 2}),
    Query("q18", "my button widget needs typing and automated checks",
          "paraphrase", {"skill_react_component": 2}),
    Query("q19", "the traceback text keeps changing between library versions and my parser breaks",
          "paraphrase", {"skill_error_contract": 2, "skill_regex_extraction": 1}),
    Query("q20", "editor saved my file half-written and now it will not parse",
          "paraphrase", {"skill_safe_file_reconstruction": 2, "skill_syntax_validation": 1,
                         "skill_null_byte_repair": 1}),
    Query("q21", "check what arguments the helper takes before changing every caller",
          "paraphrase", {"skill_signature_first_debugging": 2}),
    Query("q22", "make sure generated code compiles before replacing the original file",
          "paraphrase", {"skill_syntax_validation": 2, "skill_safe_file_reconstruction": 1}),
    Query("q23", "document contains zero bytes inside after saving to a folder with a Chinese name",
          "paraphrase", {"skill_null_byte_repair": 2, "skill_wsl_encoding": 1,
                         "skill_safe_file_reconstruction": 1}),
    Query("q24", "orchestrate a pipeline where each step feeds the next",
          "paraphrase", {"skill_workflow_orchestration": 2, "skill_message_queue": 1}),
    Query("q25", "find why the service's RAM keeps climbing over days",
          "paraphrase", {"skill_memory_leak": 2, "skill_cpu_profiling": 1}),
    Query("q26", "which function burns all the processor time",
          "paraphrase", {"skill_cpu_profiling": 2, "skill_memory_leak": 1}),
    Query("q27", "collect logs from many servers into one searchable place",
          "paraphrase", {"skill_log_aggregation": 2, "skill_prometheus_monitoring": 1}),
    Query("q28", "get alerted when the error rate spikes",
          "paraphrase", {"skill_prometheus_monitoring": 2, "skill_log_aggregation": 1}),
    Query("q29", "third parties keep hammering my endpoint, slow them down",
          "paraphrase", {"skill_rate_limiting": 2}),
    Query("q30", "push live score updates to browsers without polling",
          "paraphrase", {"skill_websocket_realtime": 2}),

    # ---------------- cross_domain (10) ----------------
    Query("q31", "deploy machine learning model to Kubernetes cluster",
          "cross_domain", {"skill_k8s_deployment": 2, "skill_docker_deploy": 1}),
    Query("q32", "add a sign in with Google button to my app",
          "cross_domain", {"skill_oauth2_flow": 2, "skill_api_auth": 1}),
    Query("q33", "protect pages against script injection from user input",
          "cross_domain", {"skill_xss_hardening": 2, "skill_sql_injection_review": 1}),
    Query("q34", "attackers might tamper with my database through form fields",
          "cross_domain", {"skill_sql_injection_review": 2, "skill_xss_hardening": 1}),
    Query("q35", "roll out a new column to the users table without downtime",
          "cross_domain", {"skill_db_migration": 2, "skill_sql_optimize": 1}),
    Query("q36", "background workers should pick up jobs from a queue",
          "cross_domain", {"skill_message_queue": 2, "skill_workflow_orchestration": 1}),
    Query("q37", "click through the checkout flow automatically in a real browser",
          "cross_domain", {"skill_e2e_playwright": 2, "skill_unit_test_pytest": 1}),
    Query("q38", "turn survey numbers into charts for the quarterly report",
          "cross_domain", {"skill_data_visualization": 2, "skill_excel_reporting": 1}),
    Query("q39", "pull the pricing table out of a PDF invoice",
          "cross_domain", {"skill_pdf_extraction": 2}),
    Query("q40", "download all product pages and parse their specifications politely",
          "cross_domain", {"skill_web_scraping": 2, "skill_rate_limiting": 1}),

    # ---------------- multi_intent (8) ----------------
    Query("q41", "dockerize the service and wire up CI to build the image on every push",
          "multi_intent", {"skill_docker_deploy": 2, "skill_ci_github_actions": 2}),
    Query("q42", "secure the API with tokens and stop brute-force attempts",
          "multi_intent", {"skill_api_auth": 2, "skill_rate_limiting": 2}),
    Query("q43", "profile the slow endpoint and cache what it computes",
          "multi_intent", {"skill_cpu_profiling": 2, "skill_python_caching": 2,
                           "skill_sql_optimize": 1}),
    Query("q44", "scrape the catalog nightly and export a spreadsheet for the sales team",
          "multi_intent", {"skill_web_scraping": 2, "skill_excel_reporting": 2}),
    Query("q45", "migrate the schema and keep the queries fast afterwards",
          "multi_intent", {"skill_db_migration": 2, "skill_sql_optimize": 2}),
    Query("q46", "stream build logs to the dashboard over websockets and record metrics",
          "multi_intent", {"skill_websocket_realtime": 2, "skill_prometheus_monitoring": 2,
                           "skill_log_aggregation": 1}),
    Query("q47", "traditional Chinese medicine consultation service with JWT-protected REST endpoints",
          "multi_intent", {"skill_tcm_api": 2, "skill_api_auth": 2}),
    Query("q48", "clean the exported CSV then plot the monthly trends",
          "multi_intent", {"skill_pandas_cleaning": 2, "skill_data_visualization": 2}),

    # ---------------- negative (12): no relevant skill in corpus ----------------
    Query("q49", "compose a marketing email for the product launch", "negative", {}),
    Query("q50", "book a conference room for Friday's retrospective", "negative", {}),
    Query("q51", "translate this legal contract into French", "negative", {}),
    Query("q52", "design a logo for the new startup", "negative", {}),
    Query("q53", "what is the capital of Australia", "negative", {}),
    Query("q54", "plan a seven day vacation itinerary in Japan", "negative", {}),
    Query("q55", "write a poem about autumn leaves", "negative", {}),
    Query("q56", "negotiate salary for a new job offer", "negative", {}),
    Query("q57", "recommend a good science fiction novel", "negative", {}),
    Query("q58", "how to bake sourdough bread at home", "negative", {}),
    Query("q59", "summarize the meeting notes into action items", "negative", {}),
    Query("q60", "fix my bicycle brakes squeaking", "negative", {}),
]


def judged_queries() -> list[Query]:
    """Queries with at least one relevant skill (used for ranking metrics)."""
    return [q for q in QUERIES if q.qrels]


def negative_queries() -> list[Query]:
    """Queries with no relevant skill (used for false-positive analysis)."""
    return [q for q in QUERIES if not q.qrels]


def validate_dataset() -> list[str]:
    """Return a list of consistency problems (empty list = dataset is valid)."""
    problems: list[str] = []
    skill_ids = {s.skill_id for s in SKILLS}
    if len(skill_ids) != len(SKILLS):
        problems.append("duplicate skill_id in corpus")
    query_ids = {q.query_id for q in QUERIES}
    if len(query_ids) != len(QUERIES):
        problems.append("duplicate query_id")
    for q in QUERIES:
        for sid, grade in q.qrels.items():
            if sid not in skill_ids:
                problems.append(f"{q.query_id}: unknown skill_id {sid}")
            if grade not in (1, 2):
                problems.append(f"{q.query_id}: invalid grade {grade} for {sid}")
        if q.category == "negative" and q.qrels:
            problems.append(f"{q.query_id}: negative query must have empty qrels")
        if q.category != "negative" and not any(g == 2 for g in q.qrels.values()):
            problems.append(f"{q.query_id}: judged query lacks a primary (grade 2) skill")
        if q.category == "multi_intent" and sum(1 for g in q.qrels.values() if g == 2) < 2:
            problems.append(f"{q.query_id}: multi_intent query needs >= 2 primary skills")
    return problems
