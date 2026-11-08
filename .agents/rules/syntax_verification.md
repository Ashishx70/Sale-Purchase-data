---
description: Mandatory syntax and bracket verification after every code update
trigger: always_on
---

# Mandatory Syntax & Bracket Verification Rule

Whenever ANY file or code section in this project is updated, modified, or added:

1. **Immediate Structural & Syntax Inspection**:
   - The agent MUST carefully inspect the modified section and surrounding context.
   - Ensure every opening curly brace `{`, bracket `[`, and parenthesis `(` has its exact corresponding closing partner `}`, `]`, `)`.
   - Ensure every control block (`if`, `else`, `for`, `while`, `function`, `try`, `catch`) is strictly and properly closed.
   - Ensure strings, template literals (`` `...` ``), and regular expressions are never left unterminated.

2. **Automated Syntax Check Execution**:
   - Before finishing any turn or presenting completed code to the user, the agent MUST run:
     ```bash
     python verify_syntax.py "<path_to_modified_file>"
     ```
   - If ANY error is reported, it MUST be fixed immediately before responding to the user.

3. **Zero Tolerance for Syntax Errors**:
   - Under no circumstances should an update be delivered with unclosed brackets, missing braces, or syntax errors like `Unexpected token` or `Unexpected end of input`.
