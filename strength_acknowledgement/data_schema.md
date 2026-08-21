# CoGrader Text/Feedback Generation 'ablation_stripped_scored.csv' - Data Schema

| Field                                         | Description                                                                                                                                       |
| --------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| `grade_level`                                 | The target grade level of the generated text (e.g., 9th grade)                                                                                    |
| `topic_subject`                               | High level subject of the topic (e.g., ELA)                                                                                                       |
| `text_type`                                   | Type of text specified to be generated (e.g.,argumentative)                                                                                       |
| `topic_category`                              | Question of topic that the generated essay will argue about (e.g., School Uniforms, Cell Phone Ban)                                               |
| `quality_tier`                                | Holistic quality level of each generated text: Strong, Developing, or Weak                                                                        |
| `replicate_number`                            | Identify which genereated version of a sample it represents (e.g., w1.1 (Weak essay for topic 1, stance 1))                                       |
| `topic_description`                           | Description of stance the argumentative essay takes                                                                                               |
| `prompt_used`                                 | Prompt provided to Claude Sonnet 5 to generate text                                                                                               |
| `generated_text`                              | Output from Claude Sonnet 5 Generator                                                                                                             |
| `GBT 5.5_teacher_Validator`                   | Independent teacher_validator for genereated prompt that assigns holistic quality label and letter grade                                          |
| `cograder_feedback_stripped`                  | CoGrader's feedback after removing praise targeted by the ablation                                                                                |
| `cograder_grade`                              | Grade assigned to generated essay by Cograder out of 10                                                                                           |
| `eval_presence_of_praise_stripped`            | Evaluate whether the stripped CoGrader feedback contains praise or positive acknowledgement                                                       |
| `eval_specificity_stripped`                   | Evaluate whether stripped CoGrader feedback strength acknowledgement is specific to the writing                                                   |
| `eval_anchoring_to_evidence_stripped`         | Evaluate whether stripped CoGrader feedback strength acknowledgement is evident in writing                                                        |
| `eval_process_vs_trait_framing_stripped`      | Evaluate whether stripped CoGrader feedback strength acknowledgment are framed as controllable writing process/behaviors rather than fixed traits |
| `eval_warranted_acknowledgement_stripped`     | Evaluate whether stripped CoGrader feednack strength acknowledgement is present and accurate in students writing                                  |
| `eval_strength_acknowledged_overall_stripped` | Overall determination of whether stripped CoGrader feedback acnknowledges student strength                                                        |
| `eval_strength_acknowledged_overall_original` | Overall determination of whether original, non-stripped CoGrader feedback acnknowledges student strength                                          |
| `eval_reasoning_stripped`                     | Reasoning supporting the evaluator's assessment of the stripped CoGrader feedback                                                                 |
