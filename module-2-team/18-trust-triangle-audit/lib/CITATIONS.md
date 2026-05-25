# Trust Triangle Audit -- Citations

The Trust Triangle audit in `vstack.trust_triangle` is grounded in
five literature anchors.

## Primary anchor

1. **Frei, F. X., & Morriss, A. (2020)** "Begin with Trust."
   *Harvard Business Review*, May-June 2020.
   The three-leg triangle (Logic, Authenticity, Empathy) and the
   "wobble" diagnostic posture -- most leaders (and agents) consistently
   wobble on exactly one leg. Source for the entire diagnostic frame
   and the dominant-wobble decision rule in `_dominant_wobble`.

## Supporting anchors

2. **Edmondson, A. C. (1999)** "Psychological safety and learning
   behavior in work teams." *Administrative Science Quarterly*,
   44(2), 350-383.
   Used as upstream composition: psychological safety in the *team*
   surrounding an agent shapes whether authenticity wobbles get
   surfaced or hidden.

3. **Goleman, D. (1995)** *Emotional Intelligence.* Bantam Books.
   Source for the empathy-leg failure mode "missed_emotional_cues"
   in `_playbooks.py` -- pairs with `vstack.goleman_ei` downstream.

4. **Lewis, P., et al. (2020)** "Retrieval-Augmented Generation for
   Knowledge-Intensive NLP Tasks." *NeurIPS 2020*.
   Source for the logic-leg failure mode "hallucinated_facts" and the
   `retrieval_augmentation` intervention type.

5. **Sharma, M., et al. (2023)** "Towards Understanding Sycophancy in
   Language Models." *arXiv:2310.13548*.
   Source for the authenticity-leg failure mode "sycophancy" and the
   `sycophancy_filter` intervention type.

## How citations are surfaced

- Every `AttachedPlaybook` carries an `anchor_citation` field.
- The system prompt (`TRUST_SYSTEM_PROMPT`) anchors the LLM in Frei
  & Morriss 2020 verbatim.
- The README's "Why this pattern matters" section cites Frei & Morriss
  2020 explicitly.

## License & attribution

Citations point to published works owned by their respective authors
and publishers. The `vstack.trust_triangle` implementation is a
derivative work applying the Trust Triangle to AI agents; no
copyrighted text is reproduced here.
