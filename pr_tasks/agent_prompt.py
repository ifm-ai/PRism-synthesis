"""LLM output -> parsed task -> task text -> full prompt for a coding agent.

The agent prompt = general instructions (role, setup, workflow, verification,
honesty, response format) + the task. Both the instructions and the way the
task is rendered are varied with diversity knobs.
"""
import json
import random
import re
import textwrap

from prompt import FIELDS_BY_LEVEL

REPO_PATH = "/workspace"


# ---------------------------------------------------------------------------
# Parse the LLM output
# ---------------------------------------------------------------------------

def final_answer(generation):
    """gpt-oss replies 'analysis<thinking>assistantfinal<answer>'. Only the answer is parsed."""
    text = generation.strip()
    if not text.startswith("analysis") or "assistantfinal" not in text:
        return None
    parts = text[len("analysis"):].split("assistantfinal")
    if len(parts) - 1 > 10:
        return None
    answer = parts[-1].strip()
    if "assistantanalysis" in answer or "assistantcommentary" in answer:
        return None
    return answer


def parse_task(answer, hints_level):
    """All fields requested at this hints level must be present and non-empty."""
    m = re.search(r"<task>(.*?)</task>", answer.strip(), re.DOTALL)
    if not m:
        return None
    task = {"hints_level": hints_level, "title": "", "description": "", "environment_setup": "",
            "implementation_plan": "", "testing_hints": "", "code_hints": ""}
    for field in FIELDS_BY_LEVEL[hints_level]:
        f = re.search(rf"<{field}>(.*?)</{field}>", m.group(1), re.DOTALL)
        task[field] = textwrap.dedent(f.group(1)).strip() if f else ""
        if not task[field]:
            return None
    return task


# ---------------------------------------------------------------------------
# Task -> text
# ---------------------------------------------------------------------------

SECTION_LABELS = {
    "environment_setup": [
        "Environment Setup", "Setup", "Getting Started", "Prerequisites",
        "Dev Environment", "Before You Begin", "Setup & Installation",
        "Dependencies", "Local Setup", "Environment",
    ],
    "implementation_plan": [
        "Implementation Plan", "Steps", "Approach", "How to Implement",
        "Plan", "Implementation", "Suggested Approach", "Implementation Steps",
        "What to Do", "Task Breakdown", "Work Plan",
    ],
    "testing_hints": [
        "Testing", "How to Test", "Verification", "Checking Your Work",
        "Tests", "Test Strategy", "Acceptance Criteria", "Validation",
        "How to Verify", "Confirming Correctness",
    ],
    "code_hints": [
        "Code Hints", "Implementation Notes", "Guidance", "Key Pointers",
        "Notes", "Hints", "Technical Notes", "Code Guidance",
        "Implementation Details", "Developer Notes", "Useful Context",
    ],
}

SECTION_CONNECTORS = {
    "environment_setup": [
        "To get started,",
        "Before writing any code,",
        "First, set up the environment.",
        "You'll want to set up dependencies first.",
        "Start by setting up your local environment.",
        "Here's where to look for project setup info:",
        "Before diving in, get the environment ready.",
        "For setup instructions,",
        "To get the project running,",
    ],
    "implementation_plan": [
        "Here's a suggested approach:",
        "You can tackle this as follows:",
        "A reasonable implementation plan:",
        "Consider the following steps:",
        "Here's how to break down the work:",
        "One way to approach this:",
        "A step-by-step plan:",
        "Here's a rough implementation order:",
        "To get this done:",
        "Work through it like this:",
    ],
    "testing_hints": [
        "To verify your implementation:",
        "You can check correctness by:",
        "Make sure to test:",
        "Run the following to confirm things work:",
        "Here's how to know you're done:",
        "Your implementation is correct when:",
        "Validate your changes with:",
        "Confirm it works by:",
        "A few things to check:",
        "After implementing, verify with:",
    ],
    "code_hints": [
        "A few pointers on the code:",
        "Some implementation notes:",
        "Useful context for implementation:",
        "Keep in mind:",
        "A few things worth knowing:",
        "Some hints before you start:",
        "Relevant code context:",
        "Worth noting:",
        "A few technical details that may help:",
        "Some guidance on the codebase:",
    ],
}

SEPARATORS = {"blank_line": "\n\n", "dashes": "\n\n---\n\n", "equals": "\n\n===\n\n"}


def header(label, style, level):
    if style == "atx":
        return f"{'#' * level} {label}"
    if style == "underline":
        return f"{label}\n{('=' if level == 1 else '-') * len(label)}"
    if style == "bold":
        return f"**{label}**"
    if style == "upper":
        return label.upper()
    return ""


def task_to_text(task):
    fmt = random.choice(["markdown", "plain", "conversational"])
    if fmt == "markdown":
        header_style, sep = random.choice(["atx", "underline", "bold"]), random.choice(["blank_line", "dashes"])
    elif fmt == "plain":
        header_style, sep = random.choice(["upper", "none"]), random.choice(["blank_line", "equals", "dashes"])
    else:
        header_style, sep = "none", "blank_line"
    title_as_heading = random.random() < 0.75

    if task["hints_level"] == "bare":           # just the conversational request
        return task["description"].strip()

    title, description = task["title"], task["description"]
    if title_as_heading:
        h = header(title, header_style, 1)
        parts = [h, description] if h else [f"{title}\n\n{description}"]
    else:
        parts = [f"**Task:** {title}\n\n{description}" if fmt == "markdown" else f"Task: {title}\n\n{description}"]

    for field in ("environment_setup", "implementation_plan", "testing_hints", "code_hints"):
        if not task[field]:
            continue
        label = random.choice(SECTION_LABELS[field])
        if fmt == "conversational":
            parts.append(f"{random.choice(SECTION_CONNECTORS[field])}\n\n{task[field]}")
        else:
            h = header(label, header_style, 2)
            parts.append(f"{h}\n\n{task[field]}" if h else task[field])
    return SEPARATORS[sep].join(parts).strip()


# ---------------------------------------------------------------------------
# Agent instructions: diversity knobs
# ---------------------------------------------------------------------------

def sample_instruction_config(hints_level):
    # Less detailed tasks get more detailed instructions and stricter verification.
    verbosity_weights = {"bare": [5, 35, 60], "concise": [10, 45, 45], "standard": [25, 50, 25],
                         "guided": [40, 45, 15], "detailed": [55, 35, 10]}
    verification_weights = {"bare": [10, 30, 60], "concise": [15, 40, 45], "standard": [25, 50, 25],
                            "guided": [40, 40, 20], "detailed": [50, 35, 15]}
    return {
        "verbosity": random.choices(["minimal", "standard", "detailed"], weights=verbosity_weights[hints_level])[0],
        "workflow_style": random.choices(["phased", "checklist", "freeform"], weights=[40, 35, 25])[0],
        "verification": random.choices(["light", "standard", "strict"], weights=verification_weights[hints_level])[0],
        "honesty": random.choices(["explicit", "exit_ramps", "neutral"], weights=[15, 65, 20])[0],
        "outcome_format": random.choices(["structured", "freeform"], weights=[40, 60])[0],
        "language_hints": random.random() < 0.75,
        "include_response_format": random.random() < 0.70,
    }


# ---------------------------------------------------------------------------
# Agent instructions: sections
# ---------------------------------------------------------------------------

# language: (config files, install hint, test hint, build hint or None)
LANGUAGE_HINTS = {
    "Python": (
        "`pyproject.toml`, `setup.py`, `setup.cfg`, `requirements*.txt`",
        "Create a virtual environment (`python3 -m venv venv && source venv/bin/activate`) "
        "and install dependencies, e.g. `pip install -e '.[dev,test]'` or `pip install -r requirements.txt`.",
        "Run tests with `pytest` (or check `tox.ini` / `Makefile` for the project's preferred runner).",
        None,
    ),
    "JavaScript": (
        "`package.json`, `package-lock.json`, `yarn.lock`",
        "Install dependencies with `npm install` or `yarn install`.",
        "Run tests with `npm test` or `yarn test` (check `package.json` scripts).",
        None,
    ),
    "TypeScript": (
        "`package.json`, `tsconfig.json`, `tsconfig*.json`",
        "Install dependencies with `npm install` or `yarn install`.",
        "Run tests with `npm test` or `yarn test`. Build with `npx tsc` or the configured build script.",
        "`npx tsc` or `npm run build`",
    ),
    "Java": (
        "`pom.xml` (Maven), `build.gradle` or `build.gradle.kts` (Gradle)",
        "Install dependencies via the build tool: `mvn install -DskipTests` or `./gradlew build -x test`.",
        "Run tests with `mvn test` or `./gradlew test`.",
        "`mvn compile` or `./gradlew build`",
    ),
    "Kotlin": (
        "`build.gradle.kts`, `pom.xml`",
        "Use Gradle (`./gradlew build -x test`) or Maven (`mvn install -DskipTests`).",
        "Run tests with `./gradlew test` or `mvn test`.",
        "`./gradlew build`",
    ),
    "Scala": (
        "`build.sbt`, `project/`",
        "Use `sbt compile` to fetch dependencies and build.",
        "Run tests with `sbt test`.",
        "`sbt compile`",
    ),
    "Go": (
        "`go.mod`, `go.sum`",
        "Dependencies are managed automatically; run `go mod download` to pre-fetch.",
        "Run tests with `go test ./...`.",
        "`go build ./...`",
    ),
    "Rust": (
        "`Cargo.toml`, `Cargo.lock`",
        "Build and fetch dependencies with `cargo build`.",
        "Run tests with `cargo test`.",
        "`cargo build`",
    ),
    "C": (
        "`Makefile`, `CMakeLists.txt`, `configure`, `meson.build`",
        "Install build dependencies (`build-essential`, project-specific libs), "
        "then configure and build (e.g. `mkdir build && cd build && cmake .. && make`).",
        "Run tests with `make test`, `ctest`, or the project's test target.",
        "`make` or `cmake --build .`",
    ),
    "C++": (
        "`CMakeLists.txt`, `Makefile`, `meson.build`, `conanfile.txt`",
        "Install build dependencies, then configure and build "
        "(e.g. `mkdir build && cd build && cmake .. && make`).",
        "Run tests with `make test`, `ctest`, or the project's test target.",
        "`make` or `cmake --build .`",
    ),
    "C#": (
        "`.csproj`, `.sln`, `nuget.config`",
        "Restore dependencies with `dotnet restore`.",
        "Run tests with `dotnet test`.",
        "`dotnet build`",
    ),
    "Ruby": (
        "`Gemfile`, `Gemfile.lock`, `Rakefile`, `.gemspec`",
        "Install dependencies with `bundle install`.",
        "Run tests with `bundle exec rake test` or `bundle exec rspec`.",
        None,
    ),
    "PHP": (
        "`composer.json`, `composer.lock`",
        "Install dependencies with `composer install`.",
        "Run tests with `vendor/bin/phpunit` or `composer test`.",
        None,
    ),
    "Swift": (
        "`Package.swift`",
        "Resolve dependencies with `swift package resolve`.",
        "Run tests with `swift test`.",
        "`swift build`",
    ),
    "Objective-C": (
        "`Podfile`, `.xcodeproj`, `Makefile`",
        "Install dependencies with `pod install` if using CocoaPods, or use `xcodebuild`.",
        "Run tests with `xcodebuild test` or the project's test target.",
        "`xcodebuild build`",
    ),
    "R": (
        "`DESCRIPTION`, `NAMESPACE`, `renv.lock`",
        "Install dependencies with `Rscript -e 'install.packages(\"devtools\"); devtools::install_deps()'`.",
        "Run tests with `Rscript -e 'devtools::test()'` or `R CMD check .`.",
        None,
    ),
    "Julia": (
        "`Project.toml`, `Manifest.toml`",
        "Instantiate the project environment with `julia -e 'using Pkg; Pkg.instantiate()'`.",
        "Run tests with `julia -e 'using Pkg; Pkg.test()'`.",
        None,
    ),
    "Lua": (
        "`rockspec` files, `Makefile`",
        "Install dependencies with `luarocks install` or the project's setup instructions.",
        "Run tests with `busted` or the project's test runner.",
        None,
    ),
    "Perl": (
        "`Makefile.PL`, `cpanfile`, `Build.PL`",
        "Install dependencies with `cpanm --installdeps .` or `perl Makefile.PL && make`.",
        "Run tests with `prove -l t/` or `make test`.",
        None,
    ),
    "Haskell": (
        "`*.cabal`, `stack.yaml`, `cabal.project`",
        "Build and install dependencies with `stack build` or `cabal build`.",
        "Run tests with `stack test` or `cabal test`.",
        "`stack build` or `cabal build`",
    ),
    "Elixir": (
        "`mix.exs`",
        "Fetch dependencies with `mix deps.get`.",
        "Run tests with `mix test`.",
        "`mix compile`",
    ),
    "Erlang": (
        "`rebar.config`, `Makefile`",
        "Fetch dependencies with `rebar3 get-deps` or `rebar3 compile`.",
        "Run tests with `rebar3 eunit` or `rebar3 ct`.",
        "`rebar3 compile`",
    ),
    "Clojure": (
        "`project.clj` (Leiningen), `deps.edn` (tools.deps)",
        "Fetch dependencies with `lein deps` or `clojure -P`.",
        "Run tests with `lein test` or `clojure -M:test`.",
        None,
    ),
    "Dart": (
        "`pubspec.yaml`",
        "Fetch dependencies with `dart pub get`.",
        "Run tests with `dart test`.",
        None,
    ),
    "Zig": (
        "`build.zig`, `build.zig.zon`",
        "Build with `zig build`.",
        "Run tests with `zig build test`.",
        "`zig build`",
    ),
    "V": (
        "`v.mod`",
        "Build with `v .`.",
        "Run tests with `v test .`.",
        "`v .`",
    ),
    "Nim": (
        "`*.nimble`",
        "Install dependencies with `nimble install -d`.",
        "Run tests with `nimble test`.",
        "`nimble build`",
    ),
    "OCaml": (
        "`dune-project`, `*.opam`, `Makefile`",
        "Install dependencies with `opam install . --deps-only` and build with `dune build`.",
        "Run tests with `dune test`.",
        "`dune build`",
    ),
    "F#": (
        "`.fsproj`, `.sln`",
        "Restore dependencies with `dotnet restore`.",
        "Run tests with `dotnet test`.",
        "`dotnet build`",
    ),
    "Shell": (
        "`Makefile`, `configure`",
        "Install any system dependencies noted in the README. Shell scripts generally "
        "don't need a build step.",
        "Run tests with `make test`, `bats`, or the project's test framework.",
        None,
    ),
}


def language_hint(lang, verbosity):
    if lang not in LANGUAGE_HINTS:
        return ""
    config_files, install, test, build = LANGUAGE_HINTS[lang]
    if verbosity == "minimal":
        return f"This is a {lang} project." + (f" Build: {build}." if build else "") + f" Tests: {test.split('.')[0]}."
    if verbosity == "standard":
        lines = [f"This is a **{lang}** project. Look for {config_files} for project configuration.",
                 f"- **Install:** {install}", f"- **Test:** {test}"]
        return "\n".join(lines + ([f"- **Build:** {build}"] if build else []))
    lines = [f"This is a **{lang}** project.", "", f"**Configuration files:** {config_files}", "",
             f"**Installing dependencies:** {install}", "", f"**Running tests:** {test}"]
    return "\n".join(lines + (["", f"**Building:** {build}"] if build else []))


def role(verbosity):
    if verbosity == "minimal":
        return (
            f"You are a software developer working in a repository at `{REPO_PATH}`. "
            "You have root access to a Linux environment with internet connectivity."
        )
    if verbosity == "standard":
        return (
            f"You are an experienced software developer tasked with making changes to "
            f"a codebase in `{REPO_PATH}`. You are working in a Linux (Debian/Ubuntu) "
            f"environment with root permissions and full internet access for installing "
            f"dependencies."
        )
    return (
        f"You are an experienced software developer working inside a Linux Docker "
        f"container (Debian/Ubuntu based). The repository you need to work on is "
        f"located at `{REPO_PATH}`. You have root privileges and full internet access, "
        f"so you can install any system packages or language-specific dependencies "
        f"as needed."
    )


def setup(verbosity, lang, language_hints, task_has_env_setup):
    if task_has_env_setup and verbosity == "minimal":   # the task already says what to do
        return ""
    if task_has_env_setup:
        parts = [
            "The task description includes setup guidance. Follow those instructions "
            "to get the project into a runnable state. If anything is unclear, inspect "
            "the project's configuration files to fill in the gaps."
        ]
    elif verbosity == "minimal":
        parts = [
            "Start by identifying the project's build system and installing "
            "dependencies. Run a quick sanity check (e.g. run --help on the test "
            "runner) before making changes."
        ]
    elif verbosity == "standard":
        parts = [
            "Before making changes, get the project into a working state:\n"
            "1. Examine the project root to identify the language, build system, "
            "and dependency files.\n"
            "2. Install dependencies (both system-level and language-specific).\n"
            "3. Run a quick sanity check — e.g. execute the test runner with "
            "`--help` or run a single existing test — to confirm the environment "
            "is healthy."
        ]
    else:
        parts = [
            "Before making any changes, you need to get the project into a "
            "working state.\n\n"
            "1. **Examine the project root** to identify the language, framework, "
            "and build system. Look for configuration files that describe "
            "dependencies and how to build/test the project.\n"
            "2. **Install system-level dependencies** if needed (e.g. "
            "`apt-get install -y <package>` for native libraries).\n"
            "3. **Install project dependencies** using the appropriate package "
            "manager.\n"
            "4. **Sanity check** — run a trivial command to verify the "
            "environment works (e.g. the test runner's `--help`, or a single "
            "existing unit test). If something fails, diagnose and fix it before "
            "proceeding."
        ]
    if language_hints and lang and language_hint(lang, verbosity):
        parts.append(language_hint(lang, verbosity))
    return "\n\n".join(parts)


def workflow_phased(verbosity, verification, honesty, has_plan, has_testing):
    # 1. Understand
    if verbosity == "minimal":
        understand = "**1. Understand the task** — Read the task carefully before writing code."
    elif verbosity == "standard":
        understand = (
            "**1. Understand the task**\n"
            "Read the task description carefully. Identify what needs to change "
            "and what the expected outcome looks like."
        )
    else:
        understand = (
            "**1. Understand the task**\n"
            "Read the task description carefully. Determine whether this is a "
            "bug fix, a new feature, or a refactor. Identify the key files and "
            "components involved. If the task is unclear, explore the codebase "
            "to build context before writing code."
        )
    if honesty == "exit_ramps":
        understand += (
            "\n\n> If the task requirements are ambiguous or contradictory, "
            "note your interpretation and proceed with your best understanding."
        )

    # 2. Implement
    if has_plan and verbosity != "detailed":
        implement = (
            "**2. Implement**\n"
            "Follow the implementation plan from the task. Keep changes focused "
            "and consistent with the existing code style."
        )
    elif verbosity == "minimal":
        implement = (
            "**2. Implement** — Locate the relevant code, make the changes, and "
            "fix any build errors."
        )
    elif verbosity == "standard":
        implement = (
            "**2. Implement**\n"
            "Locate the specific files and functions that need modification. "
            "Make your changes, keeping them minimal and consistent with the "
            "existing code style. If your changes break the build, fix them "
            "before moving on."
        )
    else:
        implement = (
            "**2. Implement**\n"
            "Locate the specific files and functions that need modification. "
            "Apply your changes, following the existing code style and "
            "conventions. Keep the changeset focused — avoid unrelated "
            "refactoring. After editing, check that the project still builds "
            "cleanly."
        )
    if honesty == "exit_ramps":
        implement += (
            "\n\n> If you encounter a fundamental issue that prevents implementation "
            "(e.g. a missing dependency that can't be installed, or the codebase "
            "is structured very differently than expected), report what you found "
            "rather than forcing a broken solution."
        )

    # 3. Verify
    if verification == "light":
        if has_testing:
            verify = (
                "**3. Verify** — Run the tests mentioned in the task to confirm "
                "your changes work."
            )
        else:
            verify = (
                "**3. Verify** — Run the project's test suite (or the relevant "
                "subset) to confirm your changes work and nothing is broken."
            )
    elif verification == "standard":
        if has_testing:
            run = (
                "Run the tests described in the task. Also run any other tests "
                "in the area you modified to check for regressions."
            )
        else:
            run = (
                "Run the project's test suite to verify your changes work and "
                "no existing functionality is broken. If the full suite is too "
                "large, focus on the tests most relevant to your changes."
            )
        verify = "\n".join([
            "**3. Verify**",
            run,
            "If tests fail, read the output carefully, fix the issue, and "
            "re-run until they pass.",
        ])
    else:
        verify = "\n".join([
            "**3. Verify**",
            "Before implementing, identify how you'll know the change is correct. "
            "If there's an existing test that covers the behavior, note it. "
            "If not, consider writing a small test or reproduction script.",
            "",
            "After implementing, run the relevant tests. Then run a broader "
            "set of tests to check for regressions. Read test output carefully — "
            "if tests fail, diagnose and fix the problem.",
        ])
    if honesty == "exit_ramps":
        verify += (
            "\n\n> If tests fail and you cannot determine why, report the "
            "failing tests and your analysis. Partial progress with honest "
            "reporting is more useful than a claim of success that doesn't "
            "hold up."
        )
    return "\n\n".join([understand, implement, verify])


def workflow_checklist(verbosity, verification, honesty, has_plan, has_testing):
    items = ["- [ ] Read and understand the task requirements"]
    if verbosity != "minimal":
        items.append("- [ ] Explore the relevant parts of the codebase")
    items.append("- [ ] Set up the development environment (if not already done)")
    items.append("- [ ] Implement the required changes")
    if verbosity == "detailed":
        items.append("- [ ] Confirm the project builds cleanly after your changes")
    if verification == "strict":
        items.append("- [ ] Identify or write a test that validates the change")
    if has_testing:
        items.append("- [ ] Run the recommended tests from the task")
    items.append("- [ ] Run the relevant test suite to check for regressions")
    if verification == "strict" and verbosity != "minimal":
        items.append("- [ ] Review test output — all relevant tests should pass")
    if honesty == "exit_ramps":
        items.append("")
        items.append(
            "If any step above is blocked by an issue you cannot resolve, stop "
            "and report what you've accomplished so far and what the blocker is."
        )
    return "\n".join(items)


def workflow_freeform(verbosity, verification, honesty, has_plan, has_testing):
    if verbosity == "minimal":
        parts = [
            "Read the task, explore the code to understand the context, "
            "implement the changes, and verify they work by running relevant "
            "tests."
        ]
    elif verbosity == "standard":
        parts = [
            "Start by reading the task and understanding what needs to change. "
            "Explore the relevant code to build context — look at the files "
            "involved, understand the existing patterns, and identify where "
            "your changes fit.",

            "The task includes an implementation plan you can follow. "
            "Adapt it as needed based on what you find in the code."
            if has_plan else
            "Plan your approach before editing. Think about what files need "
            "to change and in what order.",

            "After implementing, verify your work by running tests. "
            + ("Focus on the tests the task calls out, then check for broader regressions. "
               if has_testing else
               "Run the test suite (or the relevant subset) to make sure everything works. ")
            + "If something fails, diagnose and fix it.",
        ]
    else:
        parts = [
            "Take time to understand the task before writing any code. Read the "
            "description carefully, then explore the relevant parts of the "
            "codebase. Look at the files that will be affected, understand the "
            "existing patterns and conventions, and build a mental model of how "
            "your changes will fit.",

            "The task provides an implementation plan. Use it as a guide, "
            "but don't follow it blindly — adapt based on what you observe "
            "in the code. The plan may not account for every edge case."
            if has_plan else
            "Before editing, think through your approach. Which files need "
            "to change? Are there related tests? Is there anything that "
            "might break as a side effect?",

            "After implementing your changes, verify them. "
            + ("The task includes specific testing advice — start there, then "
               "run a broader set of tests to catch regressions. "
               if has_testing else
               "Run the project's test suite, or at least the tests most "
               "relevant to your changes. ")
            + "Read test output carefully. If tests fail, understand why before "
            "attempting a fix.",
        ]
    if honesty == "exit_ramps":
        parts.append(
            "If at any point you're stuck on something you can't resolve — "
            "whether it's an environment issue, an unclear requirement, or "
            "failing tests you can't diagnose — it's better to report where "
            "you are and what the problem is than to push forward with an "
            "incomplete or incorrect solution."
        )
    return "\n\n".join(parts)


WORKFLOWS = {"phased": (workflow_phased, "Workflow"),
             "checklist": (workflow_checklist, "Checklist"),
             "freeform": (workflow_freeform, "Approach")}


def honesty_note(verbosity):
    """Only used when honesty == 'explicit' (exit_ramps are woven into the workflow instead)."""
    if verbosity == "minimal":
        return (
            "If you get stuck or something doesn't work as expected, say so. "
            "An honest report of a problem is more useful than a workaround "
            "that hides it."
        )
    if verbosity == "standard":
        return (
            "If you encounter problems you can't resolve — setup failures, "
            "ambiguous requirements, or tests you can't get to pass — report "
            "them honestly. Describe what you tried and where things stand. "
            "Partial progress with clear reporting is a perfectly valid outcome, "
            "and more useful than a success claim that doesn't hold up."
        )
    return (
        "Honesty about problems is important. During this task, you may "
        "encounter issues: the environment might not set up cleanly, tests "
        "might fail in ways you don't expect, or requirements might be "
        "unclear.\n\n"
        "When this happens, describe the problem, what you tried, and where "
        "things stand. Possible outcomes include:\n"
        "- **Solved**: Everything works, tests pass.\n"
        "- **Partial**: You made progress but some aspects aren't working yet.\n"
        "- **Stuck**: You hit a blocker you couldn't resolve.\n\n"
        "All of these are valid and useful. What's not useful is reporting "
        "success when the situation is actually partial or stuck."
    )


def response_format(outcome_format, verbosity):
    if outcome_format == "structured":
        if verbosity == "minimal":
            return (
                "When done, report:\n"
                "- **Status**: solved / partial / stuck\n"
                "- **Changes**: files modified\n"
                "- **Verification**: test results"
            )
        return (
            "When you're finished, provide a summary:\n"
            "- **Status**: `solved` (everything works), `partial` (some aspects "
            "incomplete), or `stuck` (hit a blocker)\n"
            "- **Changes**: which files you modified and why\n"
            "- **Verification**: what tests you ran and their results"
        )
    if verbosity == "minimal":
        return "When done, briefly summarize what you changed and how you verified it."
    return (
        "When you're finished, summarize what you did: what you changed, "
        "how you verified it, and whether there are any loose ends or "
        "caveats to be aware of."
    )


TASK_TRANSITIONS = {
    "bare":     ["Here's what needs to be done:", "The request:", "Task:"],
    "concise":  ["Here's the task:", "Task:", "Your assignment:"],
    "standard": ["## Task", "## Assignment", "## What to Do"],
    "guided":   ["## Task", "## Assignment"],
    "detailed": ["## Task", "## Task Description"],
}


def build_agent_prompt(task, config):
    ic = sample_instruction_config(task["hints_level"])
    v = ic["verbosity"]

    def section(title, text):                  # minimal instructions have no headers
        return text if v == "minimal" else f"## {title}\n{text}"

    sections = [section("Role", role(v))]
    setup_text = setup(v, config["primary_language"], ic["language_hints"], bool(task["environment_setup"]))
    if setup_text:
        sections.append(section("Setup", setup_text))
    build_workflow, title = WORKFLOWS[ic["workflow_style"]]
    sections.append(section(title, build_workflow(v, ic["verification"], ic["honesty"],
                                                  bool(task["implementation_plan"]), bool(task["testing_hints"]))))
    if ic["honesty"] == "explicit":
        sections.append(section("Important", honesty_note(v)))
    if ic["include_response_format"]:
        sections.append(section("Response Format", response_format(ic["outcome_format"], v)))

    transition = random.choice(TASK_TRANSITIONS[task["hints_level"]])
    task_text = task_to_text(task)
    if task["hints_level"] != "bare" and not transition.startswith("##"):
        transition = f"**{transition}**"
    sections.append(f"{transition}\n\n{task_text}")
    return "\n\n".join(sections)


if __name__ == "__main__":
    with open("data/generation.jsonl") as fin, open("data/final.jsonl", "w") as fout:
        for line in fin:
            g = json.loads(line)
            answer = final_answer(g["generation"])
            task = parse_task(answer, g["config"]["hints_level"]) if answer else None
            if task is None:
                continue
            fout.write(json.dumps({"repo_id": g["repo_id"], "pr_number": g["pr_number"], "task": task,
                                   "task_text": task_to_text(task),
                                   "agent_prompt": build_agent_prompt(task, g["config"])}) + "\n")
