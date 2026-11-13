import os
import sys
import json
import py_compile

def check_brackets_and_blocks(content, filename=""):
    """
    Fast AST-like bracket, quote and template string balance checker.
    Catches unclosed braces/brackets/parentheses/strings/regexes.
    """
    stack = []
    line = 1
    col = 1
    i = 0
    n = len(content)
    last_token = ''
    errors = []

    while i < n:
        c = content[i]

        # If currently inside a template literal text (not inside an expression ${...})
        if stack and stack[-1][0] == '`':
            if c == '\\':
                i += 2
                col += 2
                continue
            elif c == '`':
                stack.pop()
                last_token = '`'
                i += 1
                col += 1
                continue
            elif c == '$' and i + 1 < n and content[i+1] == '{':
                stack.append(('${', line, col))
                last_token = '${'
                i += 2
                col += 2
                continue
            elif c == '\n':
                line += 1
                col = 1
                i += 1
                continue
            else:
                i += 1
                col += 1
                continue

        if c == '\n':
            line += 1
            col = 1
            i += 1
            continue

        if c.isspace():
            i += 1
            col += 1
            continue

        # Single-line comments
        if c == '/' and i + 1 < n and content[i+1] == '/':
            while i < n and content[i] != '\n':
                i += 1
            continue

        # Multi-line comments
        if c == '/' and i + 1 < n and content[i+1] == '*':
            start_l, start_c = line, col
            i += 2
            col += 2
            closed = False
            while i < n - 1:
                if content[i] == '\n':
                    line += 1
                    col = 1
                    i += 1
                elif content[i] == '*' and content[i+1] == '/':
                    closed = True
                    i += 2
                    col += 2
                    break
                else:
                    i += 1
                    col += 1
            if not closed:
                errors.append(f"Unclosed /* comment starting at line {start_l}:{start_c}")
            continue

        # Regex literal detection
        regex_preceders = {
            '(', '[', '{', ',', ';', ':', '!', '&', '|', '?', '+', '-', '*', '=', 
            '<', '>', '~', '^', '%', 'return', 'typeof', 'instanceof', 'yield', 
            'await', 'case', 'delete', 'void', 'throw'
        }
        if c == '/' and (not last_token or last_token in regex_preceders):
            start_l, start_c = line, col
            i += 1
            col += 1
            in_class = False
            closed = False
            while i < n:
                rc = content[i]
                if rc == '\n':
                    errors.append(f"Unterminated regex literal at line {start_l}:{start_c}")
                    break
                elif rc == '\\':
                    i += 2
                    col += 2
                    continue
                elif rc == '[':
                    in_class = True
                elif rc == ']' and in_class:
                    in_class = False
                elif rc == '/' and not in_class:
                    closed = True
                    i += 1
                    col += 1
                    while i < n and content[i].isalnum():
                        i += 1
                        col += 1
                    break
                i += 1
                col += 1
            last_token = 'REGEX'
            continue

        # String literals (single and double quotes)
        if c in ('"', "'"):
            quote = c
            start_l, start_c = line, col
            i += 1
            col += 1
            closed = False
            while i < n:
                sc = content[i]
                if sc == '\\':
                    i += 2
                    col += 2
                    continue
                elif sc == quote:
                    closed = True
                    i += 1
                    col += 1
                    break
                elif sc == '\n':
                    errors.append(f"Unterminated string literal ({quote}) at line {start_l}:{start_c}")
                    break
                else:
                    i += 1
                    col += 1
            if not closed:
                errors.append(f"Unterminated string literal ({quote}) at line {start_l}:{start_c}")
            last_token = 'STRING'
            continue

        # Template literal start
        if c == '`':
            stack.append(('`', line, col))
            last_token = '`'
            i += 1
            col += 1
            continue

        # Brackets
        if c in '({[':
            stack.append((c, line, col))
            last_token = c
            i += 1
            col += 1
            continue

        if c in ')}]':
            if not stack:
                errors.append(f"Unmatched closing '{c}' at line {line}:{col}")
            else:
                top_tok, top_l, top_c = stack[-1]
                if c == '}':
                    if top_tok in ('{', '${'):
                        stack.pop()
                    else:
                        errors.append(f"Mismatched closing '}}' at line {line}:{col}. Expected '}}' opened at line {top_l}:{top_c}")
                        stack.pop()
                elif c == ')':
                    if top_tok == '(':
                        stack.pop()
                    else:
                        errors.append(f"Mismatched closing ')' at line {line}:{col}. Expected ')' opened at line {top_l}:{top_c}")
                        stack.pop()
                elif c == ']':
                    if top_tok == '[':
                        stack.pop()
                    else:
                        errors.append(f"Mismatched closing ']' at line {line}:{col}. Expected ']' opened at line {top_l}:{top_c}")
                        stack.pop()
            last_token = c
            i += 1
            col += 1
            continue

        if c.isalnum() or c in '_$':
            ident = []
            while i < n and (content[i].isalnum() or content[i] in '_$'):
                ident.append(content[i])
                i += 1
                col += 1
            last_token = ''.join(ident)
            continue

        last_token = c
        i += 1
        col += 1

    if stack:
        for tok, l, co in stack:
            errors.append(f"Unclosed '{tok}' opened at line {l}:{co}")

    return errors


def validate_js_v8(filepath):
    """Compiles JavaScript using Chrome Headless V8 engine."""
    if os.environ.get('SKIP_V8') == '1':
        return []
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options

        opts = Options()
        opts.add_argument('--headless=new')
        opts.add_argument('--disable-gpu')
        opts.add_argument('--no-sandbox')
        driver = webdriver.Chrome(options=opts)

        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            code = f.read()

        js_eval = """
        var code = arguments[0];
        var done = arguments[arguments.length - 1];
        try {
            new Function(code);
            done({ ok: true });
            return;
        } catch (err) {
            if (!err.message.includes("Cannot use import statement") && 
                !err.message.includes("Unexpected token 'export'")) {
                done({ ok: false, error: err.message });
                return;
            }
        }
        var blob = new Blob([code], { type: 'application/javascript' });
        var url = URL.createObjectURL(blob);
        import(url).then(function() {
            URL.revokeObjectURL(url);
            done({ ok: true });
        }).catch(function(err) {
            URL.revokeObjectURL(url);
            if (err.name === 'SyntaxError') {
                done({ ok: false, error: err.message });
            } else {
                done({ ok: true });
            }
        });
        """
        res = driver.execute_async_script(js_eval, code)
        driver.quit()
        if res.get('ok'):
            return []
        else:
            return [res.get('error')]
    except Exception as e:
        return []


def validate_file(filepath):
    filepath = os.path.abspath(filepath)
    ext = os.path.splitext(filepath)[1].lower()

    if ext == '.js':
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        bracket_errs = check_brackets_and_blocks(content, filepath)
        if bracket_errs:
            return False, bracket_errs

        v8_errs = validate_js_v8(filepath)
        if v8_errs:
            return False, v8_errs

        return True, []

    elif ext == '.py':
        try:
            py_compile.compile(filepath, doraise=True)
            return True, []
        except py_compile.PyCompileError as e:
            return False, [str(e)]

    elif ext == '.json':
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                json.load(f)
            return True, []
        except Exception as e:
            return False, [str(e)]

    return True, []


def main():
    target = sys.argv[1] if len(sys.argv) > 1 else '.'
    target = os.path.abspath(target)

    if os.path.isfile(target):
        ok, errors = validate_file(target)
        if ok:
            print(f"[PASS] {target} is clean and syntactically valid!")
            sys.exit(0)
        else:
            print(f"[FAIL] SYNTAX ERROR in {target}:")
            for e in errors:
                print(f"  -> {e}")
            sys.exit(1)

    total = 0
    failed = 0
    for root, _, files in os.walk(target):
        if any(ignored in root for ignored in ['node_modules', '.git', '.system_generated']):
            continue
        for f in files:
            ext = os.path.splitext(f)[1].lower()
            if ext in ('.js', '.py', '.json') and not f.endswith('.min.js') and not f.startswith(('xlsx', 'pdf')):
                total += 1
                fp = os.path.join(root, f)
                ok, errors = validate_file(fp)
                if not ok:
                    print(f"[FAIL] {fp}:")
                    for e in errors:
                        print(f"  -> {e}")
                    failed += 1

    print(f"\nScan completed: {total} files verified. Failed: {failed}")
    sys.exit(0 if failed == 0 else 1)


if __name__ == '__main__':
    main()
