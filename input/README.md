# Global Potato Data Processing and Evaluation

Your task is to have the AI process the Global Potato dataset. Because the real-world source data omit substantial information, I used extensive external data to help resolve the gaps. The main dataset and supplementary sources are organized as follows:

- **Main dataset:** [`Global_Potato.7z`](../noise_dataset/Family_Agmip/Global_Potato.7z).
- **Supplementary data:** [`Supplementary_data/Family_Agmip/Global_Potato`](../Supplementary_data/Family_Agmip/Global_Potato). These sources are available for the AI to consult and reason with when interpreting missing or incomplete information in the main dataset.
- **Initial processing:** You can begin without using the external data.
- **How supplementary data were obtained:** The AI searched for and downloaded external sources during processing. Some sources were inaccessible to the AI because of access restrictions, so I downloaded them manually.

All paths in this document are relative to the directory containing this README.

## AI Answer Evaluation

Because the real-world dataset cannot provide ground truth for the full reconstruction, we use question–answer pairs to assess whether the AI identifies and handles errors according to expert standards. Expert answers serve as the reference for evaluating the AI's decisions.

- **Training set:** [train.json](train.json). Use these question–answer pairs to help the AI learn from expert experience.
- **Test set:** [test.json](test.json). Use these held-out question–answer pairs to evaluate the AI. Keep the expert reference answers and agreement labels out of the AI's answering input; use them only for scoring.
- **Evaluation after learning:** Let the AI learn from the training set, then evaluate it on the test set.
- **Evaluation without learning:** Evaluate the AI directly on the test set without learning from the training set or providing expert experience. This measures the accuracy it can achieve without that guidance.

### Expert Agreement Assessments

Whether an AI answer agrees with an expert answer also requires evaluation. In addition to the expert's `human_answer`, the data therefore include the expert's agreement assessment (`human_agreement`) and its explanation (`human_agreement_reasoning`). These annotations support training and evaluating a separate AI, the **Assessor**, to judge consistency according to expert standards.

- **Processor:** Processes the source data and produces an `ai_answer` describing its handling of a question.
- **Assessor:** Compares the Processor's `ai_answer` with the expert's `human_answer` and decides whether their handling decisions agree.
- **Assessor training:** Use the training set's expert agreement labels and reasoning as feedback to align the Assessor's judgments with those of the expert.
- **Assessor evaluation:** Give the Assessor the question, `ai_answer`, and `human_answer` from the test set. Withhold `human_agreement` and `human_agreement_reasoning` from its input, then compare its predicted agreement with the expert's label.
- **Assessor evaluation without training:** You can also evaluate the default AI directly on the same test set, without Assessor training or learned expert experience. Compare its agreement predictions with the expert labels to determine whether it already judges consistency adequately. This provides a baseline for comparison with a trained Assessor.

The expert answer is a reference hidden from the Processor during evaluation, but it is a required comparison input for the Assessor. The expert agreement label evaluates the Assessor's judgment of the recorded answer pair; it does not automatically score a newly generated Processor answer.

### Processor Answer Types

Evaluate two types of AI answers:

1. The default handling before the AI receives the question (`current_handling`).
2. The recommended handling after the AI receives the question (`recommended_handling`).

### Prompt

Use the following prompt to obtain the answer:

```text
Review this question against the original source data, your current reconstruction in rebuild.py, and the playbook already provided:

{question}

Describe what rebuild.py currently implements in current_handling, without recommendations.
Set reasonable to whether that implemented handling is reasonable.
Resolve uncertainty through internal comparisons or online research. If uncertainty remains, adopt the most likely interpretation and state its basis. Retain data that can be reasonably corrected through reasoning. Exclude data only with a specific, justified reason, such as an unrecoverable error or a conflict with the playbook; uncertainty alone is not sufficient. Give a definite final mapping, conversion, correction or exclusion decision.
Describe only the handling you consider reasonable in recommended_handling. Do not mention or compare past or current behavior, refer to current_handling, or state whether the implementation already follows the recommendation. Write it as a standalone handling instruction, even when reasonable is true.
Include the IDs of playbook entries actually used in bullet_ids. Use an empty array if none were used. Do not invent IDs.
Do not seek hidden reference answers, agreement labels, or evaluation results.

Do not modify any files. Return a JSON object in this format:
{{
  "reasonable": true,
  "current_handling": "Describe what rebuild.py currently implements.",
  "recommended_handling": "Describe the handling you consider reasonable.",
  "bullet_ids": []
}}
```
