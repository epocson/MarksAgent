# MarksAgent Core Logic

## Input/Output Protocol
- **Input:** JSON via Redis Pub/Sub
- **Keys:**
  - `marks` (dict with `green`, `yellow`, `red` int arrays)
  - `total_fragments` (int)
  - `ground_truth_errors` (optional, array of ints)

## Mathematical Constraints
- `green_ratio` = `green_count` / `total_fragments`
- `uncertainty_index` = (`yellow_count` + `red_count`) / `total_fragments`
- **Metrics (ONLY if `ground_truth_errors` is provided):**
  - Precision, Recall, F1-score
  - Handle division by zero (return 0.0)
  - Round floats to 3 decimal places

## Cognitive Pattern Classification Rules
Evaluate top to bottom:
1. If F1 > 0.8 -> return "точный детектив"
2. Elif `yellow_ratio` > 0.4 -> return "осторожный сомневающийся"
3. Elif `green_ratio` > 0.7 AND false_negatives > 0.3 -> return "самоуверенный (пропускает ошибки)"
4. Elif `red_ratio` < 0.1 AND false_negatives > 0.5 -> return "пассивный наблюдатель"
5. Else -> return "смешанный"

## XAI (Explainable AI) Strings
Strictly use these Russian phrases:
- **Green:** "Студент уверен в правильности выделенных фрагментов."
- **Yellow:** "Зоны сомнения — индикатор повышенной когнитивной нагрузки."
- **Red:** "Фрагменты идентифицированы как содержащие концептуальные или фактические ошибки."
