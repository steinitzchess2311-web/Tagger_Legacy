# Golden cases workflow

1. **Generate JSON from text fixtures**

   All editable content lives in `tests/golden_cases/*.txt`. Convert them into
   runnable JSON (including `current_tags`) via:

   ```bash
   python3 scripts/compile_golden_cases.py --engine /usr/local/bin/stockfish
   ```

   The script writes `tests/golden_cases/cases.json`. Fill in `expected_tags`
   manually inside that file when you want to lock expectations.

2. **Run golden regression**

   ```bash
   CONTROL_ENABLED=0 CONTROL_STRICT_MODE=0 \
   python3 scripts/run_golden_regression.py --engine /usr/local/bin/stockfish \
       --cases tests/golden_cases/cases.json
   ```

3. **Optional utilities**

   - `scripts/update_current_tags.py` still works, but defaults to
     `tests/golden_cases/cases.json`.
   - `scripts/split_golden_expected.py` can redistribute empty `expected_tags`
     entries if needed.
