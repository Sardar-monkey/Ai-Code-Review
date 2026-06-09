#!/usr/bin/env python3
"""
AI Code Review CLI — a minimal AI-powered code review tool.
Analyzes code files via DeepSeek API and provides actionable feedback.

Usage:
    python review.py <file_or_directory> [options]

Options:
    --model <model>         DeepSeek model to use (default: deepseek-chat)
    --output <file.md>      Save review to a Markdown file
    --focus <topic>         Review focus: security, performance, readability
    --diff <old> <new>      Diff mode: compare two files

Examples:
    python review.py app.js
    python review.py src/ --focus security
    python review.py app.py --model deepseek-reasoner --output review.md
    python review.py --diff old.py new.py
"""

import sys
import os
import json
import urllib.request
import urllib.error
import urllib.parse
import pathlib

# ─── ANSI Colors ──────────────────────────────────────────────────────────────

class Colors:
    """ANSI escape codes for terminal coloring."""
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    GRAY = "\033[90m"

    @staticmethod
    def supports_color():
        """Check if terminal supports color output."""
        if not sys.stdout.isatty():
            return False
        if os.name == 'nt':
            # Windows 10+ supports ANSI via Virtual Terminal
            return True
        return True


USE_COLOR = Colors.supports_color()


def c(color_code, text):
    """Return colored text if terminal supports it."""
    if USE_COLOR:
        return f"{color_code}{text}{Colors.RESET}"
    return text


# ─── Configuration ────────────────────────────────────────────────────────────

API_URL = "https://api.deepseek.com/v1/chat/completions"
DEFAULT_MODEL = "deepseek-chat"
SUPPORTED_EXTENSIONS = {'.js', '.py', '.html', '.css'}

# ─── Language support ─────────────────────────────────────────────────────────

LANGUAGES = {
    "en": "English",
    "ru": "Русский",
}

LANGUAGE_INSTRUCTIONS = {
    "en": (
        "IMPORTANT: Write the entire review in English."
    ),
    "ru": (
        "ВАЖНО: Напиши весь ревью на русском языке."
    ),
}

# ─── Focus-specific prompts ───────────────────────────────────────────────────

FOCUS_PROMPTS = {
    "security": {
        "en": (
            "Focus specifically on SECURITY issues in this code. "
            "Look for: injection vulnerabilities (SQL, XSS, command injection), "
            "insecure data handling, hardcoded secrets, missing input validation, "
            "authentication/authorization flaws, unsafe deserialization, "
            "path traversal, and other common security weaknesses. "
            "Rate the code's security posture and suggest concrete fixes."
        ),
        "ru": (
            "Сосредоточься specifically на проблемах БЕЗОПАСНОСТИ в этом коде. "
            "Ищи: уязвимости инъекций (SQL, XSS, command injection), "
            "небезопасную обработку данных, захардкоженные секреты, отсутствие валидации ввода, "
            "ошибки аутентификации/авторизации, небезопасную десериализацию, "
            "path traversal и другие распространённые слабые места безопасности. "
            "Оцени уровень безопасности кода и предложи конкретные исправления."
        ),
    },
    "performance": {
        "en": (
            "Focus specifically on PERFORMANCE issues in this code. "
            "Look for: inefficient algorithms, unnecessary computations, "
            "memory leaks, blocking I/O in hot paths, lack of caching, "
            "N+1 query problems, excessive allocations, and other performance "
            "bottlenecks. Suggest specific optimizations with code examples."
        ),
        "ru": (
            "Сосредоточься specifically на проблемах ПРОИЗВОДИТЕЛЬНОСТИ в этом коде. "
            "Ищи: неэффективные алгоритмы, излишние вычисления, "
            "утечки памяти, блокирующий I/O в горячих путях, отсутствие кэширования, "
            "проблемы N+1 запросов, чрезмерные аллокации и другие узкие места "
            "производительности. Предложи конкретные оптимизации с примерами кода."
        ),
    },
    "readability": {
        "en": (
            "Focus specifically on CODE READABILITY and maintainability. "
            "Look for: unclear naming, overly complex functions, "
            "missing or excessive comments, inconsistent formatting, "
            "deep nesting, magic numbers, lack of separation of concerns, "
            "and violations of common style guides. "
            "Suggest improvements to make the code cleaner and more maintainable."
        ),
        "ru": (
            "Сосредоточься specifically на ЧИТАЕМОСТИ КОДА и поддерживаемости. "
            "Ищи: непонятные названия, излишне сложные функции, "
            "отсутствие или избыток комментариев, непоследовательное форматирование, "
            "глубокую вложенность, магические числа, отсутствие разделения ответственности "
            "и нарушения общепринятых руководств по стилю. "
            "Предложи улучшения, чтобы сделать код чище и более поддерживаемым."
        ),
    },
}

DEFAULT_PROMPT = {
    "en": (
        "You are an expert code reviewer. Analyze the following code and provide "
        "a structured review covering:\n"
        "1. **Overall Assessment** — brief summary of code quality\n"
        "2. **Potential Bugs** — logic errors, edge cases, race conditions\n"
        "3. **Code Smells** — anti-patterns, duplicated code, overly complex logic\n"
        "4. **Improvement Suggestions** — actionable recommendations with examples\n"
        "5. **Readability & Maintainability** — naming, structure, documentation\n"
        "6. **Security Concerns** — vulnerabilities or unsafe practices\n\n"
        "Be constructive, specific, and prioritize issues by severity."
    ),
    "ru": (
        "Ты — эксперт по ревью кода. Проанализируй следующий код и предоставь "
        "структурированное ревью, охватывающее:\n"
        "1. **Общая оценка** — краткое резюме качества кода\n"
        "2. **Потенциальные баги** — логические ошибки, краевые случаи, состояния гонки\n"
        "3. **Запахи кода** — антипаттерны, дублированный код, излишне сложная логика\n"
        "4. **Предложения по улучшению** — конкретные рекомендации с примерами\n"
        "5. **Читаемость и поддерживаемость** — именование, структура, документация\n"
        "6. **Проблемы безопасности** — уязвимости или небезопасные практики\n\n"
        "Будь конструктивным, конкретным и расставляй приоритеты по серьёзности проблем."
    ),
}

DIFF_PROMPT = {
    "en": (
        "You are an expert code reviewer. Below is a diff between an old and a new "
        "version of a code file. Review the CHANGES specifically:\n"
        "1. **Summary of Changes** — what was modified\n"
        "2. **Correctness** — do the changes introduce bugs?\n"
        "3. **Improvement Quality** — do the changes actually improve the code?\n"
        "4. **Potential Issues** — edge cases, regressions, incomplete changes\n"
        "5. **Suggestions** — how could the changes be further improved?\n\n"
        "Be constructive and specific."
    ),
    "ru": (
        "Ты — эксперт по ревью кода. Ниже представлен diff между старой и новой "
        "версией файла с кодом. Проанализируй ИЗМЕНЕНИЯ specifically:\n"
        "1. **Сводка изменений** — что было изменено\n"
        "2. **Корректность** — вносят ли изменения баги?\n"
        "3. **Качество улучшений** — действительно ли изменения улучшают код?\n"
        "4. **Потенциальные проблемы** — краевые случаи, регрессии, неполные изменения\n"
        "5. **Предложения** — как можно ещё улучшить изменения?\n\n"
        "Будь конструктивным и конкретным."
    ),
}


# ─── Error Handling ───────────────────────────────────────────────────────────

class ReviewError(Exception):
    """Base exception for review-related errors."""
    pass


def die(message, exit_code=1):
    """Print an error message and exit."""
    print(f"{c(Colors.RED, '✖ Error:')} {message}", file=sys.stderr)
    sys.exit(exit_code)


# ─── API Key Loading ──────────────────────────────────────────────────────────

def load_api_key():
    """
    Load DeepSeek API key from .env file or environment variable.
    Returns the key or exits with a helpful message.
    """
    # Try environment variable first
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if api_key:
        return api_key

    # Try loading from .env file
    env_path = pathlib.Path(".env")
    if env_path.exists():
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("DEEPSEEK_API_KEY="):
                        api_key = line.split("=", 1)[1].strip()
                        # Remove surrounding quotes if present
                        api_key = api_key.strip("\"'")
                        if api_key and api_key != "your_deepseek_api_key_here":
                            return api_key
        except (IOError, OSError) as e:
            die(f"Cannot read .env file: {e}")

    # No key found — show helpful message
    print(
        f"{c(Colors.RED, '✖ DeepSeek API key not found!')}\n\n"
        f"To use this tool, you need a DeepSeek API key.\n\n"
        f"{c(Colors.BOLD, 'Option 1: Create a .env file')}\n"
        f"  Edit {c(Colors.CYAN, '.env')} and paste your key:\n"
        f"  {c(Colors.CYAN, 'DEEPSEEK_API_KEY=sk-your-key-here')}\n\n"
        f"{c(Colors.BOLD, 'Option 2: Set environment variable')}\n"
        f"  {c(Colors.CYAN, 'export DEEPSEEK_API_KEY=sk-your-key-here')}  (Linux/macOS)\n"
        f"  {c(Colors.CYAN, 'set DEEPSEEK_API_KEY=sk-your-key-here')}     (Windows CMD)\n"
        f"  {c(Colors.CYAN, '$env:DEEPSEEK_API_KEY=\"sk-your-key-here\"')}  (PowerShell)\n\n"
        f"Get your API key at: {c(Colors.BLUE, 'https://platform.deepseek.com/api_keys')}"
    )
    sys.exit(1)


# ─── File Handling ────────────────────────────────────────────────────────────

def is_supported_file(file_path):
    """Check if the file has a supported extension."""
    ext = pathlib.Path(file_path).suffix.lower()
    return ext in SUPPORTED_EXTENSIONS


def read_file(file_path):
    """Read a file and return its contents. Exit with message on error."""
    path = pathlib.Path(file_path)
    if not path.exists():
        die(f"File not found: {c(Colors.YELLOW, file_path)}")
    if not path.is_file():
        die(f"Not a file: {c(Colors.YELLOW, file_path)}")
    if not is_supported_file(file_path):
        ext = path.suffix.lower()
        supported = ", ".join(SUPPORTED_EXTENSIONS)
        die(
            f"Unsupported file extension '{ext}'. "
            f"Supported: {supported}"
        )
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except (IOError, OSError) as e:
        die(f"Cannot read file '{file_path}': {e}")


def collect_files_from_directory(dir_path):
    """Recursively collect all supported files from a directory."""
    path = pathlib.Path(dir_path)
    if not path.exists():
        die(f"Directory not found: {c(Colors.YELLOW, dir_path)}")
    if not path.is_dir():
        die(f"Not a directory: {c(Colors.YELLOW, dir_path)}")

    files = []
    for item in path.rglob("*"):
        if item.is_file() and is_supported_file(str(item)):
            files.append(str(item))
    if not files:
        supported = ", ".join(SUPPORTED_EXTENSIONS)
        die(
            f"No supported files found in '{dir_path}'. "
            f"Supported extensions: {supported}"
        )
    return sorted(files)


def generate_diff(old_content, new_content, old_name="old", new_name="new"):
    """
    Generate a simple unified-diff-like string from two file contents.
    Uses a minimal line-by-line diff algorithm.
    """
    old_lines = old_content.splitlines(keepends=True)
    new_lines = new_content.splitlines(keepends=True)

    # Simple LCS-based diff
    m, n = len(old_lines), len(new_lines)
    # Build LCS table
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if old_lines[i - 1] == new_lines[j - 1]:
                dp[i][j] = dp[i - 1][j - 1] + 1
            else:
                dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])

    # Backtrack to build diff
    result = [f"--- {old_name}", f"+++ {new_name}"]
    i, j = m, n
    changes = []
    while i > 0 or j > 0:
        if i > 0 and j > 0 and old_lines[i - 1] == new_lines[j - 1]:
            changes.append((" ", old_lines[i - 1].rstrip()))
            i -= 1
            j -= 1
        elif j > 0 and (i == 0 or dp[i][j - 1] >= dp[i - 1][j]):
            changes.append(("+", new_lines[j - 1].rstrip()))
            j -= 1
        else:
            changes.append(("-", old_lines[i - 1].rstrip()))
            i -= 1

    changes.reverse()

    # Group into hunks
    hunk_start = 0
    hunk_lines = []
    for k, (tag, line) in enumerate(changes):
        if tag == " ":
            if hunk_lines:
                # End of a hunk
                result.extend(hunk_lines)
                hunk_lines = []
            hunk_start = k + 1
        else:
            hunk_lines.append(f"{tag} {line}")

    if hunk_lines:
        result.extend(hunk_lines)

    return "\n".join(result)


# ─── Language Selection ───────────────────────────────────────────────────────

def select_language():
    """
    Ask the user to select a language for the review.
    Returns a language code ('en' or 'ru').
    """
    print(f"\n{c(Colors.BOLD, 'Select review language / Выберите язык ревью:')}")
    print(f"  {c(Colors.CYAN, '1')} — English")
    print(f"  {c(Colors.CYAN, '2')} — Русский")
    print()

    while True:
        try:
            choice = input(f"{c(Colors.BOLD, 'Enter 1 or 2 / Введите 1 или 2')}: ").strip()
            if choice == "1":
                return "en"
            elif choice == "2":
                return "ru"
            else:
                print(f"{c(Colors.YELLOW, '⚠ Please enter 1 or 2 / Пожалуйста, введите 1 или 2')}")
        except (EOFError, KeyboardInterrupt):
            print()
            sys.exit(130)


# ─── API Call ─────────────────────────────────────────────────────────────────

def call_deepseek(prompt, code, model=DEFAULT_MODEL, lang="en"):
    """
    Send code to DeepSeek API for review.
    Returns the model's response text.
    """
    api_key = load_api_key()

    # Truncate code if too long (DeepSeek context window ~64K tokens)
    # Rough estimate: 1 token ≈ 4 characters for code
    MAX_CHARS = 120000  # ~30K tokens, leaving room for prompt
    if len(code) > MAX_CHARS:
        print(
            f"{c(Colors.YELLOW, '⚠ Code is very long')} "
            f"({len(code)} chars). Truncating to {MAX_CHARS} chars.",
            file=sys.stderr
        )
        code = code[:MAX_CHARS] + "\n\n# ... [truncated due to length]"

    # Append language instruction to the prompt
    full_prompt = f"{prompt}\n\n{LANGUAGE_INSTRUCTIONS[lang]}"

    messages = [
        {"role": "system", "content": full_prompt},
        {"role": "user", "content": f"```\n{code}\n```"}
    ]

    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.3,
        "max_tokens": 4096,
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        API_URL,
        data=data,
        headers=headers,
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=120) as response:
            response_data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        status = e.code
        body = e.read().decode("utf-8", errors="replace")
        try:
            err_detail = json.loads(body)
            err_msg = err_detail.get("error", {}).get("message", body)
        except (json.JSONDecodeError, AttributeError):
            err_msg = body
        die(
            f"DeepSeek API returned HTTP {status}: {err_msg}\n"
            f"  Check your API key and try again."
        )
        return ""  # unreachable, but satisfies type checker
    except urllib.error.URLError as e:
        die(
            f"Network error: {e.reason}\n"
            f"  Check your internet connection and try again."
        )
        return ""
    except (OSError, ValueError) as e:
        die(f"Request failed: {e}")
        return ""

    # Parse response
    if "choices" not in response_data or not response_data["choices"]:
        die(f"Unexpected API response: no 'choices' field.\n{json.dumps(response_data, indent=2)}")

    choice = response_data["choices"][0]
    message = choice.get("message", {})
    content = message.get("content", "")

    if not content:
        finish_reason = choice.get("finish_reason", "unknown")
        die(f"API returned empty content (finish_reason: {finish_reason})")

    return content


# ─── Output Formatting ────────────────────────────────────────────────────────

def print_review(review_text, file_path, model, focus=None):
    """Print the review to terminal with formatting."""
    header_parts = [f"📋 Code Review: {c(Colors.CYAN, file_path)}"]
    if focus:
        header_parts.append(f"  [{c(Colors.MAGENTA, focus)} mode]")
    header_parts.append(f"  ({c(Colors.GRAY, model)})")

    separator = "─" * 60

    print()
    print(c(Colors.BOLD, header_parts[0]))
    if len(header_parts) > 1:
        for part in header_parts[1:]:
            print(part)
    print(c(Colors.DIM, separator))
    print()
    print(review_text)
    print()
    print(c(Colors.DIM, separator))
    print(c(Colors.GREEN, "✅ Review complete."))
    print()


def save_review_to_markdown(review_text, file_path, output_path, model, focus=None):
    """Save the review to a Markdown file."""
    lines = [
        f"# Code Review: {file_path}",
        "",
        f"- **Model:** {model}",
        f"- **Date:** {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
    ]
    if focus:
        lines.append(f"- **Focus:** {focus}")
    lines.extend([
        "",
        "---",
        "",
        review_text,
        "",
        "---",
        f"*Generated by AI Code Review CLI*",
    ])

    try:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        print(f"{c(Colors.GREEN, '✓')} Review saved to {c(Colors.CYAN, output_path)}")
    except (IOError, OSError) as e:
        die(f"Cannot write output file '{output_path}': {e}")


# ─── Argument Parsing ─────────────────────────────────────────────────────────

def parse_args():
    """
    Parse command-line arguments manually (no argparse).
    Returns a dict with parsed options.
    """
    args = sys.argv[1:]
    options = {
        "files": [],
        "model": DEFAULT_MODEL,
        "output": None,
        "focus": None,
        "diff_old": None,
        "diff_new": None,
    }

    i = 0
    while i < len(args):
        arg = args[i]

        if arg == "--model":
            i += 1
            if i >= len(args):
                die("--model requires a value (e.g., --model deepseek-reasoner)")
            options["model"] = args[i]
        elif arg == "--output":
            i += 1
            if i >= len(args):
                die("--output requires a file path (e.g., --output review.md)")
            options["output"] = args[i]
        elif arg == "--focus":
            i += 1
            if i >= len(args):
                die("--focus requires a topic (security, performance, readability)")
            topic = args[i].lower()
            if topic not in FOCUS_PROMPTS:
                die(
                    f"Unknown focus topic '{topic}'. "
                    f"Available: {', '.join(FOCUS_PROMPTS.keys())}"
                )
            options["focus"] = topic
        elif arg == "--diff":
            # Next two args are old and new files
            i += 1
            if i + 1 >= len(args):
                die("--diff requires two file paths: --diff <old_file> <new_file>")
            options["diff_old"] = args[i]
            i += 1
            options["diff_new"] = args[i]
        elif arg.startswith("--"):
            die(f"Unknown option: {arg}")
        else:
            options["files"].append(arg)

        i += 1

    return options


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    """Main entry point."""
    options = parse_args()

    # Validate: need files or diff mode
    if not options["files"] and not (options["diff_old"] and options["diff_new"]):
        print(
            f"{c(Colors.BOLD, 'AI Code Review CLI')}\n"
            f"{c(Colors.DIM, 'A minimal AI-powered code review tool using DeepSeek API.')}\n\n"
            f"{c(Colors.BOLD, 'Usage:')}\n"
            f"  python review.py <file_or_directory> [options]\n\n"
            f"{c(Colors.BOLD, 'Options:')}\n"
            f"  --model <name>       Model to use (default: {DEFAULT_MODEL})\n"
            f"  --output <file.md>   Save review to Markdown file\n"
            f"  --focus <topic>      Review focus: security, performance, readability\n"
            f"  --diff <old> <new>   Compare two files (diff mode)\n\n"
            f"{c(Colors.BOLD, 'Examples:')}\n"
            f"  python review.py app.js\n"
            f"  python review.py src/ --focus security\n"
            f"  python review.py app.py --model deepseek-reasoner --output review.md\n"
            f"  python review.py --diff old.py new.py\n"
        )
        return

    # ─── Language Selection ───────────────────────────────────────────────
    lang = select_language()

    # ─── Diff Mode ────────────────────────────────────────────────────────
    if options["diff_old"] and options["diff_new"]:
        old_content = read_file(options["diff_old"])
        new_content = read_file(options["diff_new"])
        diff_text = generate_diff(
            old_content, new_content,
            options["diff_old"], options["diff_new"]
        )

        print(f"{c(Colors.BOLD, '📊 Diff Mode')}")
        print(f"  Old: {c(Colors.CYAN, options['diff_old'])}")
        print(f"  New: {c(Colors.CYAN, options['diff_new'])}")
        print()

        prompt = DIFF_PROMPT[lang]
        review = call_deepseek(prompt, diff_text, options["model"], lang)
        print_review(review, f"{options['diff_old']} → {options['diff_new']}", options["model"], options.get("focus"))

        if options["output"]:
            save_review_to_markdown(
                review,
                f"{options['diff_old']} → {options['diff_new']}",
                options["output"],
                options["model"],
                options.get("focus")
            )
        return

    # ─── Normal Mode ──────────────────────────────────────────────────────
    # Collect all files to review
    all_files = []
    for path_arg in options["files"]:
        if os.path.isdir(path_arg):
            all_files.extend(collect_files_from_directory(path_arg))
        else:
            # Validate file exists and is supported
            read_file(path_arg)  # will die() on error
            all_files.append(path_arg)

    if not all_files:
        die("No files to review.")

    # Determine prompt based on focus and language
    if options["focus"]:
        prompt = FOCUS_PROMPTS[options["focus"]][lang]
    else:
        prompt = DEFAULT_PROMPT[lang]

    # Review each file
    for file_idx, file_path in enumerate(all_files):
        if len(all_files) > 1:
            print(f"\n{c(Colors.BOLD, f'[{file_idx + 1}/{len(all_files)}]')} Reviewing: {c(Colors.CYAN, file_path)}")
            print(c(Colors.DIM, "─" * 50))

        code = read_file(file_path)
        review = call_deepseek(prompt, code, options["model"], lang)
        print_review(review, file_path, options["model"], options.get("focus"))

        if options["output"]:
            # For multiple files, append to the same output file
            if file_idx == 0:
                mode = "w"
            else:
                mode = "a"
            try:
                with open(options["output"], mode, encoding="utf-8") as f:
                    f.write(f"\n\n# Code Review: {file_path}\n\n")
                    f.write(review)
                    f.write("\n\n---\n")
                if file_idx == 0:
                    print(f"{c(Colors.GREEN, '✓')} Review saved to {c(Colors.CYAN, options['output'])}")
            except (IOError, OSError) as e:
                die(f"Cannot write output file '{options['output']}': {e}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{c(Colors.YELLOW, '⚠ Interrupted by user.')}")
        sys.exit(130)
    except ReviewError as e:
        die(str(e))
